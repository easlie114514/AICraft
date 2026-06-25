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
其他模型: 使用 httpx 直连 OpenAI 兼容 API
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator

from anthropic import AsyncAnthropic

from src.core.llm import get_current_model_config
from src.core.openai_client import acompletion as openai_completion
from src.core.permission_guard import PermissionGuard
from src.core.token_tracker import token_tracker
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
            # 如果有 anthropic_content（直接来自 API 响应的完整 content blocks），
            # 直接使用它，以保证 thinking block 的 signature 等字段原样传回
            if msg.get("anthropic_content"):
                anthropic_messages.append({
                    "role": "assistant",
                    "content": msg["anthropic_content"],
                })
                continue

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

    Yields 与 openai_completion 路径相同的事件类型，外加 search_status。
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
    # 追踪所有 Anthropic content blocks（保留顺序，用于传回 API）
    # 深度思考模式下，thinking block 的 signature 必须在后续请求中传回
    content_blocks: dict[int, dict[str, Any]] = {}

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
                    content_blocks[idx] = {
                        "type": "thinking",
                        "thinking": "",
                        "signature": getattr(block, 'signature', ''),
                    }

                elif block_type == "text":
                    content_blocks[idx] = {
                        "type": "text",
                        "text": "",
                    }

                elif block_type == "server_tool_use":
                    yield {"type": "search_status", "status": "searching"}

                elif block_type == "tool_use":
                    tool_use_blocks[idx] = {
                        "type": "tool_use",
                        "id": getattr(block, 'id', ''),
                        "name": getattr(block, 'name', ''),
                        "input_json": "",
                    }
                    content_blocks[idx] = tool_use_blocks[idx]

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
                        if idx in content_blocks:
                            content_blocks[idx]["thinking"] += thinking_text

                elif delta_type == "text_delta":
                    text = getattr(delta, 'text', '')
                    if text:
                        if thinking_start_time is not None:
                            duration_ms = int((time.time() - thinking_start_time) * 1000)
                            yield {"type": "thinking_end", "duration_ms": duration_ms}
                            thinking_start_time = None
                        full_text += text
                        yield {"type": "text", "content": text}
                        if idx in content_blocks:
                            content_blocks[idx]["text"] += text

                elif delta_type == "input_json_delta":
                    partial = getattr(delta, 'partial_json', '')
                    if idx in tool_use_blocks:
                        tool_use_blocks[idx]["input_json"] += partial

        # ── 流结束后获取 usage（Anthropic SDK）──
        try:
            # 方式1：get_final_message()（标准方式）
            final_message = await stream.get_final_message()
            if final_message and hasattr(final_message, 'usage') and final_message.usage:
                usage_dict = {
                    "input_tokens": getattr(final_message.usage, 'input_tokens', 0) or 0,
                    "output_tokens": getattr(final_message.usage, 'output_tokens', 0) or 0,
                    "cache_read_input_tokens": getattr(final_message.usage, 'cache_read_input_tokens', 0) or 0,
                    "cache_creation_input_tokens": getattr(final_message.usage, 'cache_creation_input_tokens', 0) or 0,
                }
                yield {"type": "_usage", "usage": usage_dict, "model": actual_model}
        except Exception as e:
            import logging
            logging.getLogger("aicraft").warning(f"token_tracker: get_final_message() failed: {e}")
            # 方式2：尝试 current_message_snapshot（SDK 内部快照）
            try:
                snap = stream.current_message_snapshot
                if snap and hasattr(snap, 'usage') and snap.usage:
                    usage_dict = {
                        "input_tokens": getattr(snap.usage, 'input_tokens', 0) or 0,
                        "output_tokens": getattr(snap.usage, 'output_tokens', 0) or 0,
                        "cache_read_input_tokens": getattr(snap.usage, 'cache_read_input_tokens', 0) or 0,
                        "cache_creation_input_tokens": getattr(snap.usage, 'cache_creation_input_tokens', 0) or 0,
                    }
                    yield {"type": "_usage", "usage": usage_dict, "model": actual_model}
            except Exception:
                pass

    # ── 流结束后处理 ──
    if thinking_start_time is not None:
        duration_ms = int((time.time() - thinking_start_time) * 1000)
        yield {"type": "thinking_end", "duration_ms": duration_ms}

    # ── 构建 anthropic_content：保留完整的 content blocks 用于传回 API ──
    # 深度思考模式下，thinking block 的 signature 必须原样传回
    anthropic_content: list[dict[str, Any]] = []
    for idx in sorted(content_blocks.keys()):
        block = content_blocks[idx]
        if block["type"] == "tool_use":
            json_str = block.get("input_json", "")
            try:
                input_data = json.loads(json_str) if json_str else {}
            except json.JSONDecodeError:
                input_data = {}
            anthropic_content.append({
                "type": "tool_use",
                "id": block["id"],
                "name": block["name"],
                "input": input_data,
            })
        else:
            anthropic_content.append(dict(block))

    # ── 流结束：总是 yield _stream_end 携带累积的 full_text 和 anthropic_content ──
    yield {
        "type": "_stream_end",
        "full_text": full_text,
        "anthropic_content": anthropic_content,
    }

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
    permission_guard: PermissionGuard | None = None,
) -> str:
    """执行 MCP 工具调用

    遍历所有已连接的 MCP 服务器，找到拥有该工具的服务器并通过 MCPManager.call_tool 调用。
    call_tool 会自动处理 SSE（短连接）和 Stdio（长连接）两种模式。

    如果传入 permission_guard，会在执行前检查文件操作权限和代码执行审批。

    Args:
        tool_name: 工具名称
        tool_args: 工具参数
        mcp_manager: MCPManager 实例
        permission_guard: 可选的权限守卫

    Returns:
        工具执行结果的文本表示
    """
    # 找到持有该工具的连接
    conn = None
    for c in mcp_manager.connections:
        if not (c.enabled and c.status == "connected"):
            continue
        tool_names = {t["name"] for t in c.tools}
        if tool_name in tool_names:
            conn = c
            break

    if conn is None:
        return f"未找到可执行工具 '{tool_name}' 的 MCP 服务器"

    # ── 权限检查 ──
    if permission_guard is not None and permission_guard.needs_guard(tool_name):
        # 自动授予权限开启 → 跳过所有权限检查
        if conn.auto_grant:
            pass
        # 代码执行工具：始终需要用户确认（除非会话已批准）
        elif tool_name in ("execute_python", "execute_shell"):
            if permission_guard.is_session_approved(tool_name, conn.name):
                pass  # 本次会话已批准此类操作
            else:
                preview = str(tool_args.get("code") or tool_args.get("command", ""))
                perm = await permission_guard.check(tool_name, tool_args, preview, conn.name)
                if not perm.allowed:
                    return f"[权限拒绝] {perm.reason}"
        else:
            # 文件操作：走路径规则检查（信任路径自动放行，其他弹窗确认）
            preview = ""
            if tool_name in ("write_file", "edit_file"):
                preview = str(tool_args.get("content", "") or tool_args.get("new_string", ""))
            elif tool_name == "delete_file":
                preview = f"DELETE: {tool_args.get('path', '')}"
            elif tool_name == "move_file":
                preview = f"MOVE: {tool_args.get('source', '')} → {tool_args.get('destination', '')}"

            perm = await permission_guard.check(tool_name, tool_args, preview)
            if not perm.allowed:
                return f"[权限拒绝] {perm.reason}"

    # ── 执行工具 ──
    try:
        return await mcp_manager.call_tool(conn.name, tool_name, tool_args)
    except Exception as e:
        return f"工具执行失败: {str(e)}"


async def _build_llm_kwargs(
    messages: list[dict],
    tools: list[dict] | None,
    model_config: dict,
    thinking_enabled: bool = False,
) -> dict:
    """构建 openai_completion 的 kwargs（非 DeepSeek/Claude 模型使用）"""
    kwargs: dict = {
        "model": model_config.get("model_id", ""),
        "messages": messages,
        "stream": True,
        "api_key": model_config.get("api_key", ""),
        "api_base": model_config.get("api_base", "") or "https://api.openai.com/v1",
    }
    if tools:
        kwargs["tools"] = tools
    # 注意：thinking 参数不是 OpenAI 兼容 API 的标准参数
    # DeepSeek/Claude 走 Anthropic SDK 路径，不会进入此函数
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
    permission_guard: PermissionGuard | None = None,
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
        # openai_completion 路径：合并 quick sources (OpenAI 格式) + MCP tools
        openai_tools = list(QUICK_SOURCE_TOOLS_OPENAI)
        if tools:
            openai_tools.extend(tools)
        tools = openai_tools if openai_tools else None

    for round_num in range(max_rounds):
        if use_anthropic:
            # ── Anthropic SDK 路径（DeepSeek / Claude）──
            tool_call_events: list[dict] = []
            full_text = ""
            anthropic_content: list[dict[str, Any]] | None = None
            stream_usage: dict | None = None
            stream_model: str = ""

            async for event in _stream_via_anthropic(
                messages=messages,
                anthropic_tools=anthropic_tools,
                model_config=model_config,
                thinking_enabled=thinking_enabled,
                search_enabled=search_enabled,
            ):
                if event.get("type") == "_stream_end":
                    full_text = event.get("full_text", "")
                    anthropic_content = event.get("anthropic_content")
                elif event.get("type") == "_usage":
                    stream_usage = event.get("usage")
                    stream_model = event.get("model", "")
                elif event.get("type") == "tool_call":
                    tool_call_events.append(event)
                else:
                    yield event

            # ── 追踪 token 用量 ──
            if stream_usage:
                token_tracker.update(stream_usage, stream_model)
                yield {"type": "token_stats", "data": token_tracker.get_stats()}

            # 流结束，无客户端 tool_use → 保存 assistant 消息并结束
            if not tool_call_events:
                msg: dict[str, Any] = {"role": "assistant", "content": full_text}
                if anthropic_content:
                    msg["anthropic_content"] = anthropic_content
                messages.append(msg)
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

            msg = {
                "role": "assistant",
                "content": full_text or None,
                "tool_calls": tool_calls_for_msg,
            }
            if anthropic_content:
                msg["anthropic_content"] = anthropic_content
            messages.append(msg)

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
                        result = await execute_mcp_tool(
                            tool_name, tool_args, mcp_manager, permission_guard
                        )
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
            # ── openai_completion 路径（其他模型）──
            thinking_start_time: float | None = None

            kwargs = await _build_llm_kwargs(messages, tools, model_config, thinking_enabled)

            response = await openai_completion(**kwargs)

            full_text = ""
            tool_call_deltas: dict[int, dict[str, str]] = {}
            stream_usage: dict | None = None

            async for chunk in response:
                delta = chunk.choices[0].delta

                # ── 捕获 usage（streaming 最后一个 chunk 携带）──
                if chunk.usage:
                    stream_usage = dict(chunk.usage)

                # ── Thinking 增量 ──
                if thinking_enabled:
                    reasoning = delta.reasoning_content
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

            # ── 追踪 token 用量 ──
            if stream_usage:
                token_tracker.update(stream_usage, model_config.get("model_id", ""))
                yield {"type": "token_stats", "data": token_tracker.get_stats()}

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
                        result = await execute_mcp_tool(
                            tool_name, tool_args, mcp_manager, permission_guard
                        )
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
