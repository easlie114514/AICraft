"""LLM调用模块 - 基于 httpx 的统一调用接口"""

from typing import Any, AsyncGenerator

from src.core.openai_client import acompletion as openai_completion
from src.utils.config import (
    get_all_model_configs,
    get_current_model_id,
    get_model_config,
)


def get_current_model_config() -> dict:
    """获取当前使用的模型完整配置

    优先使用profile中指定的model_id，否则使用标记为默认的模型，
    都没有则返回第一个可用模型。
    """
    models = get_all_model_configs()
    if not models:
        return {}

    current_model_id = get_current_model_id()

    # 按profile指定的model_id查找
    if current_model_id:
        cfg = get_model_config(current_model_id)
        if cfg:
            return cfg

    # 查找默认模型
    for m in models:
        if m.get("is_default"):
            return m

    # 返回第一个可用的
    return models[0]


def get_available_models() -> list[dict]:
    """获取所有已配置的模型"""
    return get_all_model_configs()


async def chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
    model_config: dict | None = None,
    stream: bool = True,
) -> AsyncGenerator[dict[str, Any], None]:
    """调用LLM，支持流式输出和工具调用（自动累积 tool_call delta）

    Args:
        messages: 消息列表 [{"role": "user", "content": "..."}, ...]
        tools: MCP工具列表（OpenAI function-calling 格式），None 表示无工具
        model_config: 模型配置dict，不传则用当前模型
        stream: 是否流式输出

    Yields:
        {"type": "text", "content": "..."}
            — 流式文本增量（可能 yield 多次）
        {"type": "tool_calls", "tool_calls": [...], "text": "..."}
            — 累积完成的工具调用列表（仅在流结束时 yield 一次，如果有工具调用）
             tool_calls 格式: [{"id": "...", "function_name": "...", "function_arguments": "..."}, ...]
             text 字段是 LLM 在工具调用之前的文本内容（可能为空字符串）
    """
    if model_config is None:
        model_config = get_current_model_config()

    if not model_config or not model_config.get("model_id"):
        raise ValueError("未配置任何模型，请先在模型页面添加API配置")

    api_key = model_config.get("api_key", "")
    api_base = model_config.get("api_base", "")

    kwargs: dict = {
        "model": model_config["model_id"],
        "messages": messages,
        "stream": stream,
        "api_key": api_key,
        "api_base": api_base or "https://api.openai.com/v1",
    }
    if tools:
        kwargs["tools"] = tools

    if stream:
        response = await openai_completion(**kwargs)

        full_text = ""
        tool_call_deltas: dict[int, dict[str, str]] = {}

        async for chunk in response:
            delta = chunk.choices[0].delta

            # 文本增量 → 实时 yield
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

        # 流结束 — yield 累积完成的工具调用（如果有）
        if tool_call_deltas:
            yield {
                "type": "tool_calls",
                "tool_calls": list(tool_call_deltas.values()),
                "text": full_text,
            }
    else:
        response = await openai_completion(**kwargs)
        msg = response  # 非流式直接返回 OpenAIMessage
        content = msg.content or ""
        yield {"type": "text", "content": content}

        # 非流式模式也可能有 tool_calls
        if msg.tool_calls:
            yield {
                "type": "tool_calls",
                "tool_calls": [
                    {
                        "id": tc.id or "",
                        "function_name": tc.function.name,
                        "function_arguments": tc.function.arguments,
                    }
                    for tc in msg.tool_calls
                ],
                "text": content,
            }


async def test_connection(model_config: dict) -> tuple[bool, str]:
    """测试模型API连通性"""
    try:
        content = await simple_completion(
            model_config=model_config,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=10,
        )
        return True, f"连接成功，模型响应: {content[:50]}"
    except Exception as e:
        return False, f"连接失败: {str(e)[:150]}"


async def simple_completion(
    model_config: dict,
    messages: list[dict],
    max_tokens: int = 500,
) -> str:
    """协议感知的非流式简单完成 — 根据 protocol 自动选择 Anthropic SDK 或 openai_completion

    Args:
        model_config: 模型配置 dict
        messages: 消息列表
        max_tokens: 最大 token 数

    Returns:
        模型返回的文本内容
    """
    protocol = model_config.get("protocol", "").lower()
    api_key = model_config.get("api_key", "")
    api_base = model_config.get("api_base", "")
    model_id = model_config.get("model_id", "")

    # ── Anthropic 协议（DeepSeek / Claude）──
    if protocol == "anthropic":
        from anthropic import AsyncAnthropic

        if api_base:
            base_url = api_base
        else:
            provider = model_config.get("provider", "").lower()
            if provider == "deepseek":
                base_url = "https://api.deepseek.com/anthropic"
            else:
                base_url = "https://api.anthropic.com"

        actual_model = model_id.split("/", 1)[1] if "/" in model_id else model_id

        client = AsyncAnthropic(api_key=api_key, base_url=base_url)
        response = await client.messages.create(
            model=actual_model,
            max_tokens=max_tokens,
            messages=messages,
            thinking={"type": "disabled"},  # 简单调用不需要思考
        )
        # 过滤出 TextBlock（跳过 ThinkingBlock 等）
        for block in response.content:
            if getattr(block, 'type', None) == "text":
                return block.text
        return ""

    # ── httpx 路径（OpenAI 兼容等）──
    response = await openai_completion(
        model=model_id,
        messages=messages,
        max_tokens=max_tokens,
        api_key=api_key or "",
        api_base=api_base or "https://api.openai.com/v1",
        stream=False,
    )
    return response.content or ""
