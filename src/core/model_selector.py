"""模型选择器 — 根据任务类型自动选择 Pro/Flash 模型

用于后台任务（记忆压缩、角色切换摘要、RAG 检索摘要等）自动降级到 Flash 模型，
节省 Pro 模型的推理能力和 Token 开销。

同时提供 Auto 路由：根据消息内容和开关状态自动选择 Pro/Flash。
"""

import re
from typing import Any

from src.utils.config import get_all_model_configs

# ── Auto 路由：复杂任务关键词列表 ──
COMPLEX_KEYWORDS = [
    # 推理分析
    "分析", "比较", "评估", "推理", "论证", "辩证",
    "为什么", "原因", "逻辑", "原理", "机制",
    # 技术开发
    "代码", "编程", "函数", "算法", "debug", "调试",
    "修复", "bug", "实现", "开发", "部署",
    "sql", "api", "json", "html", "css",
    # 写作创作
    "写一篇", "撰写", "起草", "总结", "概括",
    "翻译", "润色", "改写", "扩写",
    # 计算
    "计算", "公式", "数学", "统计",
    # 规划
    "规划", "方案", "设计", "架构",
]

# 代码块/结构化内容检测模式
_CODE_BLOCK_PATTERN = re.compile(r"```|\n    \w", re.IGNORECASE)


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


def select_model_auto(
    user_message: str,
    toggles: dict,
    has_mcp_tools: bool,
    user_model_config: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    """Auto路由：根据消息内容和开关状态自动选择Pro/Flash

    核心原则：Pro兜底，Flash只在明确简单时才用。宁可多花一点，不要答错。

    Args:
        user_message: 用户发送的原始消息
        toggles: 开关状态 {"thinking": bool, "rag": bool, "memory": bool}
        has_mcp_tools: 当前是否有启用的MCP工具
        user_model_config: 用户当前模型配置（用于兜底）

    Returns:
        (model_config, reason) — 选中的模型配置 + 路由原因
    """
    models = get_all_model_configs()
    pro_model = None
    flash_model = None

    for m in models:
        if m.get("tier") == "pro":
            pro_model = m
        elif m.get("tier") == "flash":
            flash_model = m

    # 没有Flash模型时，全走Pro（兜底）
    if not flash_model:
        return user_model_config, "无Flash模型"

    # ── 规则1：深度思考 → Pro ──
    if toggles.get("thinking"):
        return pro_model or user_model_config, "深度思考"

    # ── 规则2：MCP工具调用 → Pro ──
    if has_mcp_tools:
        return pro_model or user_model_config, "工具调用"

    # ── 规则3：RAG检索 → Pro ──
    if toggles.get("rag"):
        return pro_model or user_model_config, "RAG检索"

    # ── 规则4：复杂关键词 → Pro ──
    msg_lower = user_message.lower()
    for kw in COMPLEX_KEYWORDS:
        if kw in msg_lower:
            return pro_model or user_model_config, "复杂任务"

    # ── 规则5：消息长度 > 300字 → Pro ──
    if len(user_message) > 300:
        return pro_model or user_model_config, "复杂任务"

    # ── 规则6：包含代码块 → Pro ──
    if _CODE_BLOCK_PATTERN.search(user_message):
        return pro_model or user_model_config, "复杂任务"

    # ── 规则7：多问题结构 → Pro ──
    if user_message.count("？") + user_message.count("?") >= 2:
        return pro_model or user_model_config, "复杂任务"

    # ── 全部未命中 → Flash（确认简单） ──
    return flash_model, "简单问答"
