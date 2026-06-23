"""Token用量追踪器"""
import time
from collections import defaultdict
from typing import Optional

# 主流模型定价（美元/百万Token），按model名称前缀匹配
# 格式: "模型名前缀": {"input_cache_miss", "input_cache_hit", "output"}
# input_cache_hit为None表示该模型不支持缓存
PRICING = {
    # DeepSeek（匹配多种命名：v4-pro / deepseek-reasoner 等）
    "deepseek-v4-pro": {
        "input_cache_miss": 0.435,
        "input_cache_hit": 0.003625,
        "output": 0.87,
    },
    "deepseek-v4-flash": {
        "input_cache_miss": 0.14,
        "input_cache_hit": 0.0028,
        "output": 0.28,
    },
    "deepseek-reasoner": {  # 兼容旧命名
        "input_cache_miss": 0.435,
        "input_cache_hit": 0.003625,
        "output": 0.87,
    },
    "deepseek-chat": {  # 兼容旧命名
        "input_cache_miss": 0.14,
        "input_cache_hit": 0.0028,
        "output": 0.28,
    },
    # OpenAI
    "gpt-4o": {
        "input_cache_miss": 2.50,
        "input_cache_hit": 1.25,
        "output": 10.00,
    },
    "gpt-4o-mini": {
        "input_cache_miss": 0.15,
        "input_cache_hit": 0.075,
        "output": 0.60,
    },
    "gpt-4.1": {
        "input_cache_miss": 2.00,
        "input_cache_hit": 0.50,
        "output": 8.00,
    },
    "gpt-4.1-mini": {
        "input_cache_miss": 0.40,
        "input_cache_hit": 0.10,
        "output": 1.60,
    },
    "gpt-4.1-nano": {
        "input_cache_miss": 0.10,
        "input_cache_hit": 0.025,
        "output": 0.40,
    },
    # Claude（硅基流动等中转可能用anthropic前缀）
    "claude-sonnet-4": {
        "input_cache_miss": 3.00,
        "input_cache_hit": 0.30,
        "output": 15.00,
    },
    "claude-3.5-sonnet": {
        "input_cache_miss": 3.00,
        "input_cache_hit": 0.30,
        "output": 15.00,
    },
    "claude-3.5-haiku": {
        "input_cache_miss": 0.80,
        "input_cache_hit": 0.08,
        "output": 4.00,
    },
    # Qwen（硅基流动/阿里云）
    "qwen2.5-72b": {
        "input_cache_miss": 0.40,
        "input_cache_hit": None,
        "output": 0.40,
    },
    "qwen2.5-7b": {
        "input_cache_miss": 0.05,
        "input_cache_hit": None,
        "output": 0.05,
    },
    # GLM
    "glm-4": {
        "input_cache_miss": 0.75,
        "input_cache_hit": None,
        "output": 0.75,
    },
    "glm-4-flash": {
        "input_cache_miss": 0.0,
        "input_cache_hit": None,
        "output": 0.0,
    },
}


def get_pricing(model: str) -> dict | None:
    """按前缀匹配模型定价"""
    for key, pricing in PRICING.items():
        if model.startswith(key) or model.endswith(key):
            return pricing
    return None  # 未知模型，面板显示"--"


class TokenTracker:
    def __init__(self):
        # 当前场景统计
        self.current: dict = {
            "input_tokens": 0,
            "input_cache_hit_tokens": 0,
            "input_cache_miss_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "request_count": 0,
        }
        # 历史累计（所有场景汇总）
        self.lifetime: dict = {
            "input_tokens": 0,
            "input_cache_hit_tokens": 0,
            "input_cache_miss_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "request_count": 0,
        }
        # 当前场景ID
        self.scene_id: Optional[str] = None

    def update(self, usage: dict, model: str):
        """从API响应的usage字段更新统计"""
        if not usage:
            return

        prompt_tokens = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
        # DeepSeek返回的prompt_tokens_details / Anthropic返回的cache_read_input_tokens
        prompt_details = usage.get("prompt_tokens_details", {}) or usage.get("input_token_details", {})
        cache_hit = prompt_details.get("cached_tokens", 0) or usage.get("cache_read_input_tokens", 0) or usage.get("cache_creation_input_tokens", 0)
        cache_miss = prompt_tokens - cache_hit

        # 费用计算：已知模型正常计费，未知模型 cost=0（面板显示"--"）
        pricing = get_pricing(model)
        if pricing is not None:
            cache_hit_price = pricing.get("input_cache_hit") if pricing.get("input_cache_hit") is not None else pricing["input_cache_miss"]
            cost = (cache_miss * pricing["input_cache_miss"]
                    + cache_hit * cache_hit_price
                    + completion_tokens * pricing["output"]) / 1_000_000
        else:
            cost = 0.0

        for stats in (self.current, self.lifetime):
            stats["input_tokens"] += prompt_tokens
            stats["input_cache_hit_tokens"] += cache_hit
            stats["input_cache_miss_tokens"] += cache_miss
            stats["output_tokens"] += completion_tokens
            stats["total_cost"] += cost
            stats["request_count"] += 1

    def reset_current(self):
        """切换场景时重置当前统计"""
        self.current = {
            "input_tokens": 0,
            "input_cache_hit_tokens": 0,
            "input_cache_miss_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "request_count": 0,
        }

    def get_stats(self) -> dict:
        """返回当前+历史统计"""
        return {
            "current": dict(self.current),
            "lifetime": dict(self.lifetime),
        }


# 全局单例
token_tracker = TokenTracker()
