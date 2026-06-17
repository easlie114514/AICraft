"""LLM调用模块 - 基于litellm的统一调用接口"""

from typing import AsyncGenerator

import litellm

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
) -> AsyncGenerator[str | dict, None]:
    """调用LLM，支持流式输出和工具调用

    Args:
        messages: 消息列表 [{"role": "user", "content": "..."}, ...]
        tools: MCP工具列表（可选）
        model_config: 模型配置dict，不传则用当前模型
        stream: 是否流式输出

    Yields:
        str: 文本增量内容
        dict: 工具调用 {"type": "tool_call", "data": ...}
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
    }

    if api_key:
        kwargs["api_key"] = api_key
    if api_base:
        kwargs["api_base"] = api_base
    if tools:
        kwargs["tools"] = tools

    if stream:
        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
            # 处理工具调用（Phase 2 集成）
            if delta.tool_calls:
                yield {"type": "tool_call", "data": delta.tool_calls}
    else:
        response = await litellm.acompletion(**kwargs)
        content = response.choices[0].message.content
        yield content


async def test_connection(model_config: dict) -> tuple[bool, str]:
    """测试模型API连通性"""
    try:
        api_key = model_config.get("api_key", "")
        api_base = model_config.get("api_base", "")
        kwargs: dict = {
            "model": model_config["model_id"],
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if api_base:
            kwargs["api_base"] = api_base

        response = await litellm.acompletion(**kwargs)
        return True, f"连接成功，模型响应: {response.choices[0].message.content[:50]}"
    except Exception as e:
        return False, f"连接失败: {str(e)[:150]}"
