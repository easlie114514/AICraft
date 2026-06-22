---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_Context_Budget.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782109234039
    ReservedCode2: ""
---
# AICraft 统一上下文管理方案

> 版本：v1.0 | 日期：2026-06-22

---

## 一、现状诊断

当前上下文管理是**4个模块各自为政**，没有一个统筹者：

| 模块 | 管什么 | 预算控制 | 问题 |
|---|---|---|---|
| 会话历史裁剪 | `_trim_history()` 按50000字符裁剪 | ✅ 有字符上限 | 只管自己，不看全局 |
| 记忆注入 | `load_memory_for_inject()` 按4000字符注入 | ✅ 有字符上限 | 不知道system里还塞了多少 |
| 跨会话记忆 | `get_recent_messages()` 注入10条 | ❌ 无上限 | 10条消息可能几千字符 |
| system prompt拼接 | 角色+Skill+RAG+记忆+约束+搜索指引 | ❌ 无上限 | 所有模块往里塞，总长度不可控 |

**核心问题**：每块有自己的"小账本"，但没有人算总账。4块加起来可能占掉模型context window的30-50%，但系统不知道。

---

## 二、设计目标

1. **总预算可控**：知道模型context window多大，所有注入内容总占比不超阈值
2. **优先级裁剪**：超预算时，按优先级砍低价值的部分
3. **透明可观测**：用户能在界面上看到每条消息的context消耗分布
4. **对现有代码改动最小**：不推翻重构，加一个统筹层

---

## 三、ContextBudget 架构

### 3.1 核心思路

```
模型 context window（如 128K tokens）
  ├─ 预留输出空间（20%）
  └─ 可用输入预算（80% = ~102K tokens）
       ├─ system prompt 优先级1（角色+约束）  → 不裁剪
       ├─ Skill prompt 优先级2               → 超预算时缩短
       ├─ RAG检索结果 优先级3                → 超预算时截断
       ├─ 记忆注入 优先级4                   → 超预算时减少
       ├─ 跨会话记忆 优先级5                 → 超预算时砍掉
       └─ 会话历史 优先级6（最低）            → 超预算时从旧到新裁剪
```

### 3.2 Token估算

不引入tiktoken等重依赖，用轻量估算：

```python
def estimate_tokens(text: str) -> int:
    """粗略估算token数
    
    中文：1 token ≈ 1.5 字符
    英文/代码：1 token ≈ 3.5 字符
    混合内容取中间值 2.0
    """
    if not text:
        return 0
    # 统计中文字符占比
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    ratio = chinese_chars / max(len(text), 1)
    # 中文字符用1.5，其余用3.5，加权平均
    chars_per_token = 1.5 * ratio + 3.5 * (1 - ratio)
    return int(len(text) / chars_per_token)
```

精度够用——上下文管理不需要精确到个位数token，±10%完全可接受。

### 3.3 模型Context Window表

```python
# 常见模型的context window（tokens）
MODEL_CONTEXT_WINDOWS = {
    # DeepSeek
    "deepseek-chat": 128000,
    "deepseek-reasoner": 128000,
    "deepseek/deepseek-chat": 128000,
    "deepseek/deepseek-reasoner": 128000,
    # Claude
    "claude-sonnet-4-20250514": 200000,
    "claude-3-5-sonnet": 200000,
    "claude-3-5-haiku": 200000,
    # OpenAI
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    # Qwen
    "qwen-max": 32000,
    "qwen-plus": 131072,
    "qwen-turbo": 131072,
}

DEFAULT_CONTEXT_WINDOW = 128000  # 未识别模型默认128K
```

model.json配置中新增可选字段 `context_window`，用户可手动覆盖。

---

## 四、ContextBudget 实现方案

### 4.1 新文件 `src/core/context_budget.py`

```python
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
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
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
    
    # 切片列表（按注入顺序）
    slices: list[ContextSlice] = field(default_factory=list)
    
    # 计算属性
    @property
    def total_window(self) -> int:
        return get_model_context_window(self.model_config)
    
    @property
    def input_budget(self) -> int:
        """可用输入预算 = 总window × (1 - 输出预留比例)"""
        return int(self.total_window * (1 - OUTPUT_RESERVE_RATIO))
    
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
        """裁剪会话历史切片：从旧到新砍，保留最近的"""
        lines = slice_.content.split("\n")
        # 每次砍掉1/4，直到预算够或只剩1/4
        while len(lines) > len(lines) // 4 and self.total_tokens > self.input_budget:
            remove_count = max(len(lines) // 4, 1)
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
```

### 4.2 集成到 `backend/chat_ws.py`

在组装 system prompt 的位置，用 ContextBudget 统筹所有注入：

```python
from src.core.context_budget import ContextBudget

# ── 构建上下文预算 ──
budget = ContextBudget(model_config=model_config)

# 优先级1：角色 + 行为约束（不裁剪）
budget.add_slice("role_prompt", system_content, priority=1)

# 优先级2：Skill prompt
if skill_prompt:
    budget.add_slice("skill_prompt", skill_prompt, priority=2)

# 优先级3：RAG检索结果
if rag_text:
    budget.add_slice("rag_results", rag_text, priority=3)

# 优先级4：记忆注入
if notes:
    budget.add_slice("memory_notes", notes, priority=4)

# 优先级5：跨会话记忆
if unique_memories:
    budget.add_slice("cross_session", mem_text, priority=5)

# 优先级6：会话历史（最低）
history_text = "\n".join(
    f"[{m.get('role', '?')}]: {m.get('content', '')}" 
    for m in session_history
)
budget.add_slice("session_history", history_text, priority=6)

# ── 执行预算约束 ──
trimmed_items = budget.enforce_budget()

# ── 用裁剪后的内容重新组装 ──
# （从budget.slices中取裁剪后的content，替换原来的注入内容）
if trimmed_items:
    inject_items.append(f"⚠ 上下文预算裁剪: {', '.join(trimmed_items)}")
```

### 4.3 用户可见的context消耗

在 `inject_info` 中增加预算报告：

```python
# 每次对话返回时附带预算信息
report = budget.get_budget_report()
if report["usage_ratio"] > 0.5:  # 使用率超50%时提示
    pct = int(report["usage_ratio"] * 100)
    inject_items.append(
        f"📊 上下文: {pct}% ({report['total_tokens']:,}/{report['input_budget']:,} tokens)"
    )
```

### 4.4 前端展示（MemoryPage或ChatPage）

在对话页底部状态栏可选择性展示：

```
📊 Context: 23% (29K/128K) | Pro | 记忆:3条
```

超75%时变黄，超90%时变红。

---

## 五、优先级设计详解

### 为什么这么排优先级

| 优先级 | 模块 | 理由 |
|---|---|---|
| 1 | 角色+约束 | 不给角色定义AI就不知道自己是谁，不裁剪 |
| 2 | Skill | 是AI的专业知识，比RAG和记忆更有针对性 |
| 3 | RAG | 用户主动开的检索，有明确意图，比记忆有价值 |
| 4 | 记忆注入 | 历史压缩的精华，比跨会话更有上下文价值 |
| 5 | 跨会话记忆 | 其他对话的消息，相关性最低，先砍 |
| 6 | 会话历史 | 占比最大，从旧到新裁剪，保留最近对话 |

### 裁剪策略

| 模块 | 超预算时怎么砍 |
|---|---|
| 角色+约束 | **不砍**（优先级1不可裁剪） |
| Skill | 截断到1/3 |
| RAG | 截断到1/2 |
| 记忆注入 | 截断到1/2 |
| 跨会话记忆 | 整块砍掉 |
| 会话历史 | 从旧到新，每次砍1/4直到够用 |

---

## 六、配置项

在 `model.json` 的 `context` 中新增：

```json
{
  "context": {
    "context_budget_enabled": true,
    "context_window_override": 0,
    "output_reserve_ratio": 0.20,
    "budget_alert_threshold": 0.75
  }
}
```

| 配置项 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `context_budget_enabled` | bool | true | 是否启用统一预算管理 |
| `context_window_override` | int | 0 | 手动指定context window，0=自动识别 |
| `output_reserve_ratio` | float | 0.20 | 输出预留比例 |
| `budget_alert_threshold` | float | 0.75 | 超过此比例时前端显示警告 |

---

## 七、改动清单

| 文件 | 改动 |
|---|---|
| **新增** `src/core/context_budget.py` | ContextBudget 类 + token估算 + 模型window表 |
| `backend/chat_ws.py` | 用 ContextBudget 替代原来的逐块拼接，执行预算约束 |
| `src/utils/config.py` | `get_context_config()` 新增4个配置字段 |
| `config/profiles/default/model.json` | context中新增4个字段 |
| `frontend/src/pages/ChatPage.tsx` | 底部状态栏显示context使用率（可选） |
| `frontend/src/pages/MemoryPage.tsx` | 设置面板中增加预算相关配置（可选） |

**不改动**：`memory.py`、`chat_history.py`、`llm.py`、`agent_loop.py`——这些模块的内部逻辑不变，只是它们的产出在组装时被ContextBudget统筹。

---

## 八、与现有功能的关系

```
                    ┌─────────────────────┐
                    │   ContextBudget     │ ← 新增统筹层
                    │  (算总账 + 裁剪)     │
                    └──────────┬──────────┘
                               │ 统筹
        ┌──────────┬───────────┼───────────┬──────────┐
        ▼          ▼           ▼           ▼          ▼
   角色约束    Skill注入    RAG检索    记忆注入    会话历史
   (P1)       (P2)        (P3)       (P4)       (P6)
                                      ▲
                                      │
                               跨会话记忆(P5)
```

ContextBudget 不替代任何现有模块，而是在所有模块产出后、送入LLM前，做一次"总账检查+按需裁剪"。现有模块各管各的逻辑不变，只是最终拼接时多了一层统筹。

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
