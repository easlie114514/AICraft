"""统一上下文预算管理 — 统筹所有注入内容，确保不超模型context window"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.utils.config import get_all_model_configs


# ── Token估算 ──


def estimate_tokens(text: str) -> int:
    """粗略估算token数（中文1.5字符/token，英文3.5字符/token）"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
    ratio = chinese_chars / max(len(text), 1)
    chars_per_token = 1.5 * ratio + 3.5 * (1 - ratio)
    return max(int(len(text) / chars_per_token), 1)


# ── 模型Context Window ──

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "deepseek-chat": 128000,
    "deepseek-reasoner": 128000,
    "deepseek/deepseek-chat": 128000,
    "deepseek/deepseek-reasoner": 128000,
    "claude-sonnet-4-20250514": 200000,
    "claude-3-5-sonnet": 200000,
    "claude-3-5-haiku": 200000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "qwen-max": 32000,
    "qwen-plus": 131072,
    "qwen-turbo": 131072,
}

DEFAULT_CONTEXT_WINDOW = 128000
OUTPUT_RESERVE_RATIO = 0.20  # 预留20%给模型输出


def get_model_context_window(model_config: dict[str, Any]) -> int:
    """获取模型的context window大小（tokens）"""
    # 1. 用户配置优先
    user_setting = model_config.get("context_window")
    if user_setting and isinstance(user_setting, int) and user_setting > 0:
        return user_setting
    # 2. 模型ID匹配
    model_id = model_config.get("model_id", "")
    # 去掉provider前缀匹配
    for key, window in MODEL_CONTEXT_WINDOWS.items():
        if model_id == key or model_id.endswith("/" + key):
            return window
    # 3. 兜底
    return DEFAULT_CONTEXT_WINDOW


# ── 预算分配 ──


@dataclass
class ContextSlice:
    """上下文的一个切片"""
    name: str           # 切片名称
    content: str        # 原始内容
    tokens: int         # 估算token数
    priority: int       # 优先级（1=最高，6=最低），超预算时先砍低优先级
    trimmed: bool = False  # 是否被裁剪过


@dataclass
class ContextBudget:
    """上下文预算管理器"""
    model_config: dict[str, Any]
    output_reserve_ratio: float = OUTPUT_RESERVE_RATIO

    # 切片列表（按注入顺序）
    slices: list[ContextSlice] = field(default_factory=list)

    # 计算属性
    @property
    def total_window(self) -> int:
        return get_model_context_window(self.model_config)

    @property
    def input_budget(self) -> int:
        """可用输入预算 = 总window × (1 - 输出预留比例)"""
        return int(self.total_window * (1 - self.output_reserve_ratio))

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens for s in self.slices)

    @property
    def remaining_tokens(self) -> int:
        return self.input_budget - self.total_tokens

    @property
    def usage_ratio(self) -> float:
        """当前使用率 0.0 ~ 1.0+"""
        return self.total_tokens / self.input_budget if self.input_budget > 0 else 0.0

    def add_slice(self, name: str, content: str, priority: int) -> ContextSlice:
        """添加一个上下文切片"""
        tokens = estimate_tokens(content)
        slice_ = ContextSlice(name=name, content=content, tokens=tokens, priority=priority)
        self.slices.append(slice_)
        return slice_

    def enforce_budget(self) -> list[str]:
        """执行预算约束：超预算时按优先级从低到高裁剪

        Returns:
            被裁剪的切片名称列表
        """
        trimmed = []

        if self.total_tokens <= self.input_budget:
            return trimmed

        # 按优先级从低到高排序（先砍低优先级）
        sorted_slices = sorted(self.slices, key=lambda s: -s.priority)

        for slice_ in sorted_slices:
            if self.total_tokens <= self.input_budget:
                break

            # 优先级1（角色+约束）不裁剪
            if slice_.priority == 1:
                continue

            # 裁剪策略：按优先级不同处理
            if slice_.priority == 6:
                # 会话历史：从旧到新裁剪，保留最近的
                self._trim_history_slice(slice_)
            elif slice_.priority == 5:
                # 跨会话记忆：直接砍掉
                slice_.content = ""
                slice_.tokens = 0
                slice_.trimmed = True
            elif slice_.priority == 4:
                # 记忆注入：减半
                half_len = len(slice_.content) // 2
                slice_.content = slice_.content[:half_len] + "\n...(预算裁剪)"
                slice_.tokens = estimate_tokens(slice_.content)
                slice_.trimmed = True
            elif slice_.priority == 3:
                # RAG：截断到一半
                half_len = len(slice_.content) // 2
                slice_.content = slice_.content[:half_len] + "\n...(RAG结果已截断)"
                slice_.tokens = estimate_tokens(slice_.content)
                slice_.trimmed = True
            elif slice_.priority == 2:
                # Skill：截断到1/3
                third_len = len(slice_.content) // 3
                slice_.content = slice_.content[:third_len] + "\n...(Skill已精简)"
                slice_.tokens = estimate_tokens(slice_.content)
                slice_.trimmed = True

            trimmed.append(f"{slice_.name}(优先级{slice_.priority})")

        return trimmed

    def _trim_history_slice(self, slice_: ContextSlice) -> None:
        """裁剪会话历史切片：从旧到新砍，保留最近的，对齐消息边界避免截断"""
        lines = slice_.content.split("\n")
        # 每次砍掉约1/4，直到预算够或只剩1/4
        while len(lines) > len(lines) // 4 and self.total_tokens > self.input_budget:
            remove_count = max(len(lines) // 4, 1)
            # 调整到下一个消息边界（行首为 '['），避免从消息中间截断
            while remove_count < len(lines) and not lines[remove_count].startswith("["):
                remove_count += 1
            lines = lines[remove_count:]
            slice_.content = "\n".join(lines)
            slice_.tokens = estimate_tokens(slice_.content)
            slice_.trimmed = True

    def get_budget_report(self) -> dict:
        """生成预算使用报告"""
        return {
            "model": self.model_config.get("model_id", "unknown"),
            "total_window": self.total_window,
            "input_budget": self.input_budget,
            "total_tokens": self.total_tokens,
            "usage_ratio": round(self.usage_ratio, 3),
            "remaining_tokens": self.remaining_tokens,
            "slices": [
                {
                    "name": s.name,
                    "tokens": s.tokens,
                    "priority": s.priority,
                    "trimmed": s.trimmed,
                }
                for s in self.slices
            ],
        }
