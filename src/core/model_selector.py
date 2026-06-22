"""模型选择器 — 根据任务类型自动选择 Pro/Flash 模型

用于后台任务（记忆压缩、角色切换摘要、RAG 检索摘要等）自动降级到 Flash 模型，
节省 Pro 模型的推理能力和 Token 开销。
"""

from typing import Any

from src.utils.config import get_all_model_configs


def get_flash_model_config() -> dict[str, Any] | None:
    """获取当前 provider 的 Flash 模型配置，用于后台降级

    遍历所有已配置模型，返回第一个 tier="flash" 的模型配置。
    如果当前 provider 没有 Flash 模型，返回 None。
    """
    models = get_all_model_configs()
    for m in models:
        if m.get("tier") == "flash":
            return m
    return None


def select_model_for_task(task: str, user_model_config: dict[str, Any]) -> dict[str, Any]:
    """根据任务类型选择模型配置

    Args:
        task: 任务类型
            - "chat": 主对话，使用用户选择的模型
            - "memory_compact": 记忆压缩，优先使用 Flash
            - "role_switch_summary": 角色切换摘要，优先使用 Flash
            - "rag_summary": RAG 检索摘要，优先使用 Flash
        user_model_config: 用户当前使用的模型配置

    Returns:
        适合该任务的模型配置 dict
    """
    # 主对话：始终使用用户选择的模型
    if task == "chat":
        return user_model_config

    # 后台摘要任务：优先降级到 Flash
    if task in ("memory_compact", "role_switch_summary", "rag_summary"):
        # 如果用户当前已经在用 Flash，直接用
        if user_model_config.get("tier") == "flash":
            return user_model_config

        # 尝试找到同 provider 的 Flash 模型
        flash = get_flash_model_config()
        if flash:
            return flash

    # 兜底：返回用户当前模型
    return user_model_config
