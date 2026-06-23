"""OpenAI 兼容 API 客户端 — 替代 litellm

所有 OpenAI 兼容格式的 LLM 调用都通过此模块完成。
包括：DeepSeek OpenAI 端点、硅基流动、Ollama、OpenAI 官方等。
"""

import json
from typing import Any, AsyncGenerator

import httpx


# ═══════════════════════════════════════════════════════════
# 数据结构 — 与 litellm ModelResponse 属性对齐
# ═══════════════════════════════════════════════════════════

class OpenAIFunctionDelta:
    """delta.tool_calls[i].function"""

    def __init__(self, data: dict):
        self.name = data.get("name") or None
        self.arguments = data.get("arguments") or None


class OpenAIToolCallDelta:
    """delta.tool_calls[i]"""

    def __init__(self, data: dict):
        self.index = data.get("index", 0)
        self.id = data.get("id") or ""
        self.function = OpenAIFunctionDelta(data.get("function", {}))


class OpenAIDelta:
    """chunk.choices[0].delta"""

    def __init__(self, data: dict):
        self.content = data.get("content") or None
        self.reasoning_content = data.get("reasoning_content") or None  # DeepSeek thinking
        self.tool_calls = None
        raw_tc = data.get("tool_calls")
        if raw_tc:
            self.tool_calls = [OpenAIToolCallDelta(tc) for tc in raw_tc]


class OpenAIChoice:
    """chunk.choices[0]"""

    def __init__(self, data: dict):
        self.delta = OpenAIDelta(data.get("delta", {}))
        self.index = data.get("index", 0)


class OpenAIStreamChunk:
    """SSE 解析后的流式 chunk"""

    def __init__(self, data: dict):
        self.choices = [OpenAIChoice(c) for c in data.get("choices", [])]
        self.usage = data.get("usage")  # streaming 最后一个 chunk 可能携带 usage


class OpenAIFunction:
    """非流式 message.tool_calls[i].function"""

    def __init__(self, data: dict):
        self.name = data.get("name") or ""
        self.arguments = data.get("arguments") or ""


class OpenAIToolCall:
    """非流式 message.tool_calls[i]"""

    def __init__(self, data: dict):
        self.id = data.get("id") or ""
        self.function = OpenAIFunction(data.get("function", {}))


class OpenAIMessage:
    """非流式响应的 message"""

    def __init__(self, data: dict, usage: dict | None = None):
        self.content = data.get("content") or ""
        self.tool_calls = None
        self.usage = usage
        raw_tc = data.get("tool_calls")
        if raw_tc:
            self.tool_calls = [OpenAIToolCall(tc) for tc in raw_tc]


# ═══════════════════════════════════════════════════════════
# 公开 API — 签名与 litellm.acompletion 兼容
# ═══════════════════════════════════════════════════════════

async def acompletion(
    model: str,
    messages: list[dict],
    api_key: str = "",
    api_base: str = "https://api.openai.com/v1",
    stream: bool = True,
    tools: list[dict] | None = None,
    max_tokens: int | None = None,
    **kwargs,
) -> AsyncGenerator[OpenAIStreamChunk, None] | OpenAIMessage:
    """替代 litellm.acompletion

    stream=True  → 返回 AsyncGenerator[OpenAIStreamChunk, None]
    stream=False → 返回 OpenAIMessage
    """
    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
    if max_tokens:
        payload["max_tokens"] = max_tokens
    payload.update(kwargs)  # 透传 temperature 等其他参数

    if stream:
        payload["stream_options"] = {"include_usage": True}
        return _stream_response(url, headers, payload)
    else:
        return await _non_stream_response(url, headers, payload)


# ═══════════════════════════════════════════════════════════
# 内部实现
# ═══════════════════════════════════════════════════════════

async def _stream_response(
    url: str, headers: dict, payload: dict
) -> AsyncGenerator[OpenAIStreamChunk, None]:
    """流式 SSE 读取并解析"""
    timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise httpx.HTTPStatusError(
                    f"API 返回 {resp.status_code}: {body.decode(errors='replace')[:500]}",
                    request=resp.request,
                    response=resp,
                )

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(data)
                    yield OpenAIStreamChunk(chunk_data)
                except json.JSONDecodeError:
                    continue  # 跳过无法解析的行


async def _non_stream_response(
    url: str, headers: dict, payload: dict
) -> OpenAIMessage:
    """非流式完整响应"""
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return OpenAIMessage(data["choices"][0]["message"], usage=data.get("usage"))
