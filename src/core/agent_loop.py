"""Agent工具调用循环 — 让LLM能调用MCP工具、执行操作、拿到结果后继续回复

设计参考: docs/AGENT_LOOP.md

核心流程:
  用户输入 → 拼装上下文 → 调 LLM
                              ↓
                      LLM 返回 tool_call？
                        ↙          ↘
                     是              否
                      ↓              ↓
              执行 MCP 工具      返回最终回复给用户
                      ↓
              工具结果回传 LLM
                      ↓
              LLM 继续回复（可能再次 tool_call）
                      ↓
              循环直到 LLM 不再调工具
"""

import asyncio
import json
from typing import Any, AsyncGenerator

import litellm

from src.core.llm import get_current_model_config


async def execute_mcp_tool(
    tool_name: str,
    tool_args: dict[str, Any],
    mcp_manager: Any,
) -> str:
    """执行 MCP 工具调用

    遍历所有已连接的 MCP 服务器，找到拥有该工具的服务器并通过 MCPManager.call_tool 调用。
    call_tool 会自动处理 SSE（短连接）和 Stdio（长连接）两种模式。

    Args:
        tool_name: 工具名称
        tool_args: 工具参数
        mcp_manager: MCPManager 实例

    Returns:
        工具执行结果的文本表示
    """
    for conn in mcp_manager.connections:
        if not (conn.enabled and conn.status == "connected"):
            continue
        # 检查该连接是否拥有目标工具
        tool_names = {t["name"] for t in conn.tools}
        if tool_name not in tool_names:
            continue

        # 委托给 MCPManager.call_tool（自动路由 SSE / Stdio）
        try:
            return await mcp_manager.call_tool(conn.name, tool_name, tool_args)
        except Exception as e:
            return f"工具执行失败: {str(e)}"

    return f"未找到可执行工具 '{tool_name}' 的 MCP 服务器"


async def _build_llm_kwargs(
    messages: list[dict],
    tools: list[dict] | None,
    model_config: dict,
) -> dict:
    """构建 litellm.completion 的 kwargs"""
    kwargs: dict = {
        "model": model_config.get("model_id", ""),
        "messages": messages,
        "stream": True,
    }
    for key in ("api_key", "api_base"):
        val = model_config.get(key, "")
        if val:
            kwargs[key] = val
    if tools:
        kwargs["tools"] = tools
    return kwargs


async def agent_loop(
    messages: list[dict],
    tools: list[dict] | None,
    model_config: dict | None = None,
    mcp_manager: Any | None = None,
    max_rounds: int = 10,
) -> AsyncGenerator[dict[str, Any], None]:
    """Agent 主循环 — 支持多轮工具调用

    Args:
        messages: 完整对话消息列表（包含 system prompt + 历史 + 当前用户输入）
        tools: MCP 工具列表（litellm function-calling 格式），None 表示无工具
        model_config: 模型配置 dict，不传则用当前模型
        mcp_manager: MCPManager 实例，用于执行工具（无工具时可为 None）
        max_rounds: 最大工具调用轮次，防止无限循环

    Yields:
        {"type": "text", "content": "..."}           — 流式文本增量
        {"type": "tool_call", "name": "...", "args": {...}}  — 工具调用
        {"type": "tool_result", "name": "...", "result": "..."}  — 工具结果
    """
    if model_config is None:
        model_config = get_current_model_config()

    if not model_config or not model_config.get("model_id"):
        yield {"type": "text", "content": "⚠️ 未配置模型，请先在模型页添加API配置。"}
        return

    for round_num in range(max_rounds):
        kwargs = await _build_llm_kwargs(messages, tools, model_config)

        response = await litellm.acompletion(**kwargs)

        # ── 收集流式输出 ──
        full_text = ""
        tool_call_deltas: dict[int, dict[str, str]] = {}

        async for chunk in response:
            delta = chunk.choices[0].delta

            # 文本增量 → 实时 yield 给 UI
            if delta.content:
                full_text += delta.content
                yield {"type": "text", "content": delta.content}

            # 工具调用增量 → 按 index 累加
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_deltas:
                        tool_call_deltas[idx] = {
                            "id": tc.id or "",
                            "function_name": "",
                            "function_arguments": "",
                        }
                    if tc.function and tc.function.name:
                        tool_call_deltas[idx]["function_name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_call_deltas[idx]["function_arguments"] += tc.function.arguments

        # ── 无工具调用 → 循环结束 ──
        if not tool_call_deltas:
            messages.append({"role": "assistant", "content": full_text})
            break

        # ── 有工具调用 → 执行 ──
        tool_calls_list = list(tool_call_deltas.values())

        # 补全 tool_call_id（某些模型流式返回时 id 可能为空）
        for i, tc in enumerate(tool_calls_list):
            if not tc["id"]:
                tc["id"] = f"call_{round_num}_{i}"

        # 构建 assistant 消息（含 tool_calls）
        messages.append({
            "role": "assistant",
            "content": full_text or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function_name"],
                        "arguments": tc["function_arguments"],
                    },
                }
                for tc in tool_calls_list
            ],
        })

        # 逐个执行工具
        for tc in tool_calls_list:
            tool_name = tc["function_name"]
            try:
                tool_args = json.loads(tc["function_arguments"])
            except json.JSONDecodeError:
                tool_args = {}

            yield {
                "type": "tool_call",
                "name": tool_name,
                "args": tool_args,
            }

            # 内置工具: web_search
            if tool_name == "web_search":
                from src.core.web_search import web_search as _ws, format_search_results as _fmt
                try:
                    results = await asyncio.get_event_loop().run_in_executor(
                        None, _ws, tool_args.get("query", ""), tool_args.get("max_results", 5)
                    )
                    result = _fmt(results)
                except Exception as e:
                    result = f"联网搜索失败: {str(e)}"

            # MCP 工具
            elif mcp_manager is not None:
                try:
                    result = await execute_mcp_tool(tool_name, tool_args, mcp_manager)
                except Exception as e:
                    result = f"工具执行异常: {str(e)}"
            else:
                result = f"未找到可执行工具 '{tool_name}'"

            yield {
                "type": "tool_result",
                "name": tool_name,
                "result": result,
            }

            # 工具结果加入消息历史
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": str(result),
            })

        # 继续下一轮循环，让 LLM 基于工具结果回复

    else:
        # 超过最大轮次（for 循环正常结束，未被 break）
        yield {
            "type": "text",
            "content": "\n\n[已达到最大工具调用轮次（10轮），停止执行]",
        }
