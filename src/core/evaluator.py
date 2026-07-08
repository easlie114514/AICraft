"""Harness 评估器 — Agent 回复前的计算型质量检查

基于 Martin Fowler 的 Feedforward/Feedback 框架：
- 计算型（Computational）: 确定性规则，毫秒级，检查空回复/错误/截断等
- 推理型（Inferential）: 概率性判断，慢且贵，未来可用 Flash 模型实现

设计原则：
- 非阻塞：评估结果作为建议，不阻断用户看到回复
- 轻量级：全部是字符串/正则匹配，无 LLM 调用
- 可观测：问题通过 inject_info 通知用户和记录日志
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════

@dataclass
class EvalIssue:
    """单一质量问题"""
    code: str           # 问题代码，如 EMPTY_RESPONSE
    severity: str       # "info" | "warning" | "error"
    message: str        # 人类可读描述
    detail: str = ""    # 补充细节


@dataclass
class EvalResult:
    """评估结果"""
    passed: bool = True
    score: float = 1.0        # 0.0 ~ 1.0
    issues: list[EvalIssue] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def add_issue(self, code: str, severity: str, message: str, detail: str = "", penalty: float = 0.0):
        self.issues.append(EvalIssue(code=code, severity=severity, message=message, detail=detail))
        self.score = max(0.0, self.score - penalty)
        if severity == "error":
            self.passed = False


# ═══════════════════════════════════════════════════════════
# 检查规则
# ═══════════════════════════════════════════════════════════

# 错误/异常关键词 — 回复中出现这些说明任务可能失败了
_ERROR_PATTERNS = [
    (r"\[权限拒绝\]", "PERMISSION_DENIED", "warning", "回复包含权限拒绝信息", 0.1),
    (r"已达到最大工具调用轮次", "MAX_ROUNDS", "warning", "工具调用达到上限被截断", 0.15),
    (r"(?i)(error|exception|traceback|failed|failure)[\s:]", "ERROR_IN_RESPONSE", "warning", "回复包含异常/错误信息", 0.1),
    (r"(?i)(抱歉|对不起).{0,20}(无法|不能|没办法)", "UNABLE_TO_COMPLETE", "info", "Agent 表示无法完成任务", 0.05),
]

# 截断/不完整检测
_TRUNCATION_PATTERNS = [
    (r"(\.\.\.|…)\s*$", "ENDS_WITH_ELLIPSIS", "warning", "回复以省略号结尾，可能被截断", 0.1),
    (r"(?i)(continues?|to be continued|未完待续)", "EXPLICIT_CONTINUATION", "info", "回复显示未完成", 0.05),
    (r"[)\]}]\s*$", "BRACKET_END", "info", "回复以括号结尾，检查是否代码块未闭合", 0.02),
]


def evaluate_response(
    text: str,
    user_message: str = "",
    tool_rounds: int = 0,
    max_rounds: int = 25,
) -> EvalResult:
    """对 Agent 最终回复做计算型质量评估

    Args:
        text: Agent 的最终回复文本
        user_message: 原始用户消息（用于判断问题复杂度）
        tool_rounds: 实际使用的工具调用轮次
        max_rounds: 最大工具调用轮次

    Returns:
        EvalResult 包含通过/失败、评分、问题列表
    """
    result = EvalResult()
    result.context = {
        "response_length": len(text),
        "tool_rounds": tool_rounds,
        "max_rounds": max_rounds,
    }

    # ── 1. 空回复检查 ──
    if not text or not text.strip():
        result.add_issue("EMPTY_RESPONSE", "error", "Agent 返回了空回复", penalty=0.5)
        return result  # 空回复是最严重的，后续检查无意义

    stripped = text.strip()

    # ── 2. 过短回复检查（用户问了很多但回复很少） ──
    if len(user_message) > 100 and len(stripped) < 20:
        result.add_issue(
            "TOO_SHORT", "warning",
            f"回复过短（{len(stripped)}字），用户问题较长（{len(user_message)}字），可能未充分回答",
            penalty=0.1,
        )

    # ── 3. 错误/异常模式检查 ──
    for pattern, code, severity, message, penalty in _ERROR_PATTERNS:
        if re.search(pattern, stripped):
            result.add_issue(code, severity, message, penalty=penalty)

    # ── 4. 截断检查 ──
    for pattern, code, severity, message, penalty in _TRUNCATION_PATTERNS:
        if re.search(pattern, stripped):
            result.add_issue(code, severity, message, penalty=penalty)

    # ── 5. 工具轮次耗尽检查 ──
    if tool_rounds >= max_rounds:
        result.add_issue(
            "MAX_ROUNDS_REACHED", "warning",
            f"工具调用达到上限（{max_rounds}轮），回复可能不完整",
            penalty=0.15,
        )

    # ── 6. 纯英文检测（中文场景下可能不对） ──
    chinese_chars = sum(1 for c in stripped if '一' <= c <= '鿿')
    total_chars = len(stripped.replace(" ", "").replace("\n", ""))
    if total_chars > 50 and chinese_chars == 0:
        result.add_issue(
            "NO_CHINESE", "info",
            "回复为纯英文，如用户期望中文回答可忽略此提示",
            penalty=0.0,
        )

    return result


def format_eval_for_user(result: EvalResult) -> list[str]:
    """将评估结果格式化为前端 inject_info 提示列表"""
    if result.passed and not result.issues:
        return []

    items: list[str] = []

    # 评分摘要
    if result.score < 0.6:
        items.append(f"🔴 回复质量评分: {int(result.score * 100)} — 建议重新提问或补充信息")
    elif result.score < 0.8:
        items.append(f"🟡 回复质量评分: {int(result.score * 100)}")

    # 具体问题（只展示 warning 及以上级别）
    for issue in result.issues:
        if issue.severity in ("warning", "error"):
            icon = "❌" if issue.severity == "error" else "⚠️"
            items.append(f"{icon} {issue.message}")

    return items
