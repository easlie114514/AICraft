"""Agent工具调用循环 — 让LLM能调用MCP工具、执行操作、拿到结果后继续回复

设计参考: docs/AGENT_LOOP.md

核心流程:
  用户输入 → 拼装上下文 → 调 LLM
                              ↓
                      LLM 返回 tool_call？
                        ↙          ↘
                     是              否
                      ↓              ↓
              执行工具           返回最终回复给用户
                      ↓
              工具结果回传 LLM
                      ↓
              LLM 继续回复（可能再次 tool_call）
                      ↓
              循环直到 LLM 不再调工具

DeepSeek: 使用 Anthropic SDK 直连 api.deepseek.com/anthropic 端点，支持 server-side web_search
其他模型: 继续使用 litellm
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator

import litellm
from anthropic import AsyncAnthropic

from src.core.llm import get_current_model_config
from src.core.web_search import (
    QUICK_SOURCE_TOOLS_ANTHROPIC,
    QUICK_SOURCE_TOOLS_OPENAI,
    execute_quick_source,
    get_server_search_tools,
)


# ═══════════════════════════════════════════════════════════
# 工具格式转换
# ═══════════════════════════════════════════════════════════

def _convert_openai_tool_to_anthropic(tool: dict) -> dict:
    """将 OpenAI function-calling 格式的工具转换为 Anthropic 格式"""
    func = tool.get("function", {})
    params = func.get("parameters", {})
    return {
        "name": func.get("name", ""),
        "description": func.get("description", ""),
        "input_schema": {
            "type": params.get("type", "object"),
            "properties": params.get("properties", {}),
            "required": params.get("required", []),
        },
    }


# ═══════════════════════════════════════════════════════════
# 消息格式转换（OpenAI → Anthropic）
# ═══════════════════════════════════════════════════════════

def _convert_messages_to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    """将 OpenAI 格式消息列表转换为 Anthropic 格式

    Returns:
        (system_text, anthropic_messages)
    """
    system_text = ""
    anthropic_messages: list[dict] = []

    for msg in messages:
        role = msg.get("role", "")

        if role == "system":
            system_text += msg.get("content", "") + "\n"
            continue

        if role == "user":
            anthropic_messages.append({"role": "user", "content": msg.get("content", "")})

        elif role == "assistant":
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []

            if tool_calls:
                blocks: list[dict] = []
                if content:
                    blocks.append({"type": "text", "text": content})
                for tc in tool_calls:
                    func = tc.get("function", {})
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        args = {}
                    blocks.append({
                        "type": "tool_use",
                        "id": tc.get("id", ""),
                        "name": func.get("name", ""),
                        "input": args,
                    })
                anthropic_messages.append({"role": "assistant", "content": blocks})
            else:
                anthropic_messages.append({"role": "assistant", "content": content})

        elif role == "tool":
            anthropic_messages.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id", ""),
                    "content": msg.get("content", ""),
                }],
            })

    return system_text.strip(), anthropic_messages


# ═══════════════════════════════════════════════════════════
# Anthropic SDK 流式调用（DeepSeek / Claude）
# ═══════════════════════════════════════════════════════════

async def _stream_via_anthropic(
    messages: list[dict],
    anthropic_tools: list[dict] | None,
    model_config: dict,
    thinking_enabled: bool = False,
    search_enabled: bool = True,
) -> AsyncGenerator[dict[str, Any], None]:
    """使用 Anthropic SDK 调用 DeepSeek/Claude 的 Anthropic 兼容端点

    Yields 与 litellm 路径相同的事件类型，外加 search_status。
    """
    model_id = model_config.get("model_id", "")
    provider = model_config.get("provider", "").lower()
    api_key = model_config.get("api_key", "")
    api_base = model_config.get("api_base", "")

    # ── 确定 base_url ──
    if provider == "deepseek":
        base_url = "https://api.deepseek.com/anthropic"
        actual_model = model_id.split("/", 1)[1] if "/" in model_id else model_id
    elif provider == "anthropic":
        base_url = api_base or "https://api.anthropic.com"
        actual_model = model_id.split("/", 1)[1] if "/" in model_id else model_id
    else:
        actual_model = model_id
        base_url = api_base or "https://api.anthropic.com"

    # ── 转换消息格式 ──
    system_text, anthropic_messages = _convert_messages_to_anthropic(messages)

    # ── 构建 tools 列表 ──
    tools: list[dict] = []
    tools.extend(QUICK_SOURCE_TOOLS_ANTHROPIC)
    tools.extend(get_server_search_tools(provider, search_enabled))
    if anthropic_tools:
        tools.extend(anthropic_tools)
    if not tools:
        tools = None

    # ── 构建请求参数 ──
    kwargs: dict = {
        "model": actual_model,
        "max_tokens": 8192,
        "messages": anthropic_messages,
    }
    if system_text:
        kwargs["system"] = system_text
    if tools:
        kwargs["tools"] = tools
    if thinking_enabled:
        if provider == "deepseek":
            kwargs["thinking"] = {"type": "enabled"}
        else:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 10000}
    else:
        # 显式禁用思考，避免模型默认启用思考
        kwargs["thinking"] = {"type": "disabled"}

    # ── 创建 client 并发起流式请求 ──
    client = AsyncAnthropic(
        api_key=api_key,
        base_url=base_url,
    )

    thinking_start_time: float | None = None
    full_text = ""
    tool_use_blocks: dict[int, dict[str, Any]] = {}

    async with client.messages.stream(**kwargs) as stream:
        async for event in stream:
            event_type = getattr(event, 'type', None)

            # ── content_block_start ──
            if event_type == "content_block_start":
                block = event.content_block
                block_type = getattr(block, 'type', None)
                idx = getattr(event, 'index', 0)

                if block_type == "thinking":
                    if thinking_start_time is None:
                        thinking_start_time = time.time()

                elif block_type == "server_tool_use":
                    yield {"type": "search_status", "status": "searching"}

                elif block_type == "tool_use":
                    tool_use_blocks[idx] = {
                        "id": getattr(block, 'id', ''),
                        "name": getattr(block, 'name', ''),
                        "input_json": "",
                    }

            # ── content_block_delta ──
            elif event_type == "content_block_delta":
                delta = event.delta
                delta_type = getattr(delta, 'type', None)
                idx = getattr(event, 'index', 0)

                if delta_type == "thinking_delta":
                    thinking_text = getattr(delta, 'thinking', '')
                    if thinking_text:
                        if thinking_start_time is None:
                            thinking_start_time = time.time()
                        yield {"type": "thinking", "content": thinking_text}

                elif delta_type == "text_delta":
                    text = getattr(delta, 'text', '')
                    if text:
                        if thinking_start_time is not None:
                            duration_ms = int((time.time() - thinking_start_time) * 1000)
                            yield {"type": "thinking_end", "duration_ms": duration_ms}
                            thinking_start_time = None
                        full_text += text
                        yield {"type": "text", "content": text}

                elif delta_type == "input_json_delta":
                    partial = getattr(delta, 'partial_json', '')
                    if idx in tool_use_blocks:
                        tool_use_blocks[idx]["input_json"] += partial

    # ── 流结束后处理 ──
    if thinking_start_time is not None:
        duration_ms = int((time.time() - thinking_start_time) * 1000)
        yield {"type": "thinking_end", "duration_ms": duration_ms}

    # ── 流结束：总是 yield _stream_end 携带累积的 full_text ──
    yield {"type": "_stream_end", "full_text": full_text}

    # 如果有客户端 tool_use，yield 出来让 agent_loop 执行
    for idx in sorted(tool_use_blocks.keys()):
        tc = tool_use_blocks[idx]
        tool_name = tc["name"]
        try:
            tool_args = json.loads(tc["input_json"]) if tc["input_json"] else {}
        except json.JSONDecodeError:
            tool_args = {}

        yield {
            "type": "tool_call",
            "name": tool_name,
            "args": tool_args,
            "_tool_use_id": tc["id"],
        }


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
        tool_names = {t["name"] for t in conn.tools}
        if tool_name not in tool_names:
            continue
        try:
            return await mcp_manager.call_tool(conn.name, tool_name, tool_args)
        except Exception as e:
            return f"工具执行失败: {str(e)}"

    return f"未找到可执行工具 '{tool_name}' 的 MCP 服务器"


async def _build_llm_kwargs(
    messages: list[dict],
    tools: list[dict] | None,
    model_config: dict,
    thinking_enabled: bool = False,
) -> dict:
    """构建 litellm.completion 的 kwargs（非 DeepSeek/Claude 模型使用）"""
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

    if thinking_enabled:
        model_id = model_config.get("model_id", "").lower()
        if "claude" in model_id:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 10000}

    return kwargs


def _is_anthropic_provider(model_config: dict) -> bool:
    """判断模型是否应走 Anthropic SDK 路径"""
    provider = model_config.get("provider", "").lower()
    return provider in ("deepseek", "anthropic")


async def agent_loop(
    messages: list[dict],
    tools: list[dict] | None,
    model_config: dict | None = None,
    mcp_manager: Any | None = None,
    max_rounds: int = 10,
    thinking_enabled: bool = False,
    search_enabled: bool = True,
) -> AsyncGenerator[dict[str, Any], None]:
    """Agent 主循环 — 支持多轮工具调用

    Args:
        messages: 完整对话消息列表（包含 system prompt + 历史 + 当前用户输入）
        tools: MCP 工具列表（OpenAI function-calling 格式），None 表示无工具
        model_config: 模型配置 dict，不传则用当前模型
        mcp_manager: MCPManager 实例，用于执行工具（无工具时可为 None）
        max_rounds: 最大工具调用轮次，防止无限循环
        thinking_enabled: 是否启用深度思考
        search_enabled: 是否启用 server-side 联网搜索

    Yields:
        {"type": "thinking", "content": "..."}                — 思考过程增量
        {"type": "thinking_end", "duration_ms": 3500}         — 思考结束
        {"type": "search_status", "status": "searching"}      — 搜索状态
        {"type": "text", "content": "..."}                    — 流式文本增量
        {"type": "tool_call", "name": "...", "args": {...}}   — 工具调用
        {"type": "tool_result", "name": "...", "result": "..."}  — 工具结果
    """
    if model_config is None:
        model_config = get_current_model_config()

    if not model_config or not model_config.get("model_id"):
        yield {"type": "text", "content": "⚠️ 未配置模型，请先在模型页添加API配置。"}
        return

    provider = model_config.get("provider", "").lower()
    use_anthropic = _is_anthropic_provider(model_config)

    # ── 准备工具 ──
    if use_anthropic:
        # Anthropic 路径：MCP tools 转换为 Anthropic 格式
        # quick sources + server search tools 在 _stream_via_anthropic 内部添加
        anthropic_tools = None
        if tools:
            anthropic_tools = [_convert_openai_tool_to_anthropic(t) for t in tools]
    else:
        # litellm 路径：合并 quick sources (OpenAI 格式) + MCP tools
        litellm_tools = list(QUICK_SOURCE_TOOLS_OPENAI)
        if tools:
            litellm_tools.extend(tools)
        tools = litellm_tools if litellm_tools else None

    for round_num in range(max_rounds):
        if use_anthropic:
            # ── Anthropic SDK 路径（DeepSeek / Claude）──
            tool_call_events: list[dict] = []
            full_text = ""

            async for event in _stream_via_anthropic(
                messages=messages,
                anthropic_tools=anthropic_tools,
                model_config=model_config,
                thinking_enabled=thinking_enabled,
                search_enabled=search_enabled,
            ):
                if event.get("type") == "_stream_end":
                    full_text = event.get("full_text", "")
                elif event.get("type") == "tool_call":
                    tool_call_events.append(event)
                else:
                    yield event

            # 流结束，无客户端 tool_use → 保存 assistant 消息并结束
            if not tool_call_events:
                messages.append({"role": "assistant", "content": full_text})
                break

            # 有客户端工具调用 → 构建 assistant 消息（含 tool_calls）并执行工具
            tool_calls_for_msg = []
            for ev in tool_call_events:
                tool_calls_for_msg.append({
                    "id": ev["_tool_use_id"],
                    "type": "function",
                    "function": {
                        "name": ev["name"],
                        "arguments": json.dumps(ev["args"], ensure_ascii=False),
                    },
                })

            messages.append({
                "role": "assistant",
                "content": full_text or None,
                "tool_calls": tool_calls_for_msg,
            })

            # 逐个执行工具
            for ev in tool_call_events:
                tool_name = ev["name"]
                tool_args = ev["args"]
                tool_use_id = ev["_tool_use_id"]

                yield {
                    "type": "tool_call",
                    "name": tool_name,
                    "args": tool_args,
                }

                # 快捷数据源
                if tool_name in _QUICK_SOURCE_NAMES:
                    result = execute_quick_source(tool_name, tool_args)
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

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_use_id,
                    "content": str(result),
                })

        else:
            # ── litellm 路径（其他模型）──
            thinking_start_time: float | None = None

            kwargs = await _build_llm_kwargs(messages, tools, model_config, thinking_enabled)

            response = await litellm.acompletion(**kwargs)

            full_text = ""
            tool_call_deltas: dict[int, dict[str, str]] = {}

            async for chunk in response:
                delta = chunk.choices[0].delta

                # ── Thinking 增量 ──
                if thinking_enabled:
                    reasoning = (
                        getattr(delta, 'reasoning_content', None)
                        or getattr(delta, 'thinking', None)
                    )
                    if reasoning:
                        if thinking_start_time is None:
                            thinking_start_time = time.time()
                        yield {"type": "thinking", "content": reasoning}

                # ── 工具调用增量 ──
                if delta.tool_calls:
                    if thinking_start_time is not None:
                        duration_ms = int((time.time() - thinking_start_time) * 1000)
                        yield {"type": "thinking_end", "duration_ms": duration_ms}
                        thinking_start_time = None

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

                # 文本增量
                if delta.content:
                    if thinking_start_time is not None:
                        duration_ms = int((time.time() - thinking_start_time) * 1000)
                        yield {"type": "thinking_end", "duration_ms": duration_ms}
                        thinking_start_time = None
                    full_text += delta.content
                    yield {"type": "text", "content": delta.content}

            # ── 无工具调用 → 循环结束 ──
            if not tool_call_deltas:
                messages.append({"role": "assistant", "content": full_text})
                break

            # ── 有工具调用 → 执行 ──
            tool_calls_list = list(tool_call_deltas.values())

            for i, tc in enumerate(tool_calls_list):
                if not tc["id"]:
                    tc["id"] = f"call_{round_num}_{i}"

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

                if tool_name in _QUICK_SOURCE_NAMES:
                    result = execute_quick_source(tool_name, tool_args)
                elif tool_name == "web_search":
                    from src.core.web_search import web_search as _ws, format_search_results as _fmt
                    try:
                        results = await asyncio.get_event_loop().run_in_executor(
                            None, _ws, tool_args.get("query", ""), tool_args.get("max_results", 5)
                        )
                        result = _fmt(results)
                    except Exception as e:
                        result = f"联网搜索失败: {str(e)}"
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

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result),
                })

    else:
        yield {
            "type": "text",
            "content": "\n\n[已达到最大工具调用轮次（10轮），停止执行]",
        }


# 快捷数据源工具名称集合（用于识别）
_QUICK_SOURCE_NAMES = {"quick_weather", "quick_gold_price", "quick_exchange_rate", "quick_hot_news"}
