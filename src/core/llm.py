"""LLM调用模块 - 基于litellm的统一调用接口"""

import asyncio
from typing import AsyncGenerator

import litellm

from src.utils.config import load_json, MODELS_DIR, get_current_profile


def get_current_model_config() -> dict:
    """获取当前使用的模型配置"""
    profile = get_current_profile()
    profile_dir = MODELS_DIR.parent / "config" / "profiles" / profile
    model_config = load_json(profile_dir / "model.json")
    if model_config and "model_id" in model_config:
        # 从models目录找完整配置
        for f in MODELS_DIR.glob("*.json"):
            cfg = load_json(f)
            if cfg.get("model_id") == model_config["model_id"]:
                return cfg
    # 返回第一个可用的
    for f in MODELS_DIR.glob("*.json"):
        cfg = load_json(f)
        if cfg.get("is_default"):
            return cfg
    return {}


def get_available_models() -> list[dict]:
    """获取所有已配置的模型"""
    models = []
    for f in MODELS_DIR.glob("*.json"):
        cfg = load_json(f)
        if cfg.get("model_id"):
            models.append(cfg)
    return models


async def chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
    model_config: dict | None = None,
    stream: bool = True,
) -> AsyncGenerator[str, None] | dict:
    """调用LLM，支持流式输出和工具调用"""

    if model_config is None:
        model_config = get_current_model_config()

    if not model_config:
        raise ValueError("未配置任何模型，请先在模型页面添加API配置")

    kwargs = {
        "model": model_config["model_id"],
        "messages": messages,
        "api_key": model_config.get("api_key", ""),
        "stream": stream,
    }

    # 自定义API端点
    if model_config.get("api_base"):
        kwargs["api_base"] = model_config["api_base"]

    # 工具列表
    if tools:
        kwargs["tools"] = tools

    if stream:
        response = await litellm.acompletion(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
            # 处理工具调用
            if delta.tool_calls:
                yield {"type": "tool_call", "data": delta.tool_calls}
    else:
        response = await litellm.acompletion(**kwargs)
        return response.choices[0].message


async def test_connection(model_config: dict) -> tuple[bool, str]:
    """测试模型API连通性"""
    try:
        response = await litellm.acompletion(
            model=model_config["model_id"],
            messages=[{"role": "user", "content": "Hi"}],
            api_key=model_config.get("api_key", ""),
            api_base=model_config.get("api_base"),
            max_tokens=10,
        )
        return True, f"连接成功，模型响应: {response.choices[0].message.content[:50]}"
    except Exception as e:
        return False, f"连接失败: {str(e)[:100]}"
