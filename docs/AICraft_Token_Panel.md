---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_Token_Panel.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782219064421
    ReservedCode2: ""
---
# AICraft Token计费面板 实现指令

## 目标
在对话界面添加实时Token计费面板，显示当前场景的Token用量和费用，切换场景时清零当前面板但保留历史累计。

---

## 后端

### Step 1: 新建 `src/core/token_tracker.py`

```python
"""Token用量追踪器"""
import time
from collections import defaultdict
from typing import Optional

# 主流模型定价（美元/百万Token），按model名称前缀匹配
# 格式: "模型名前缀": {"input_cache_miss", "input_cache_hit", "output"}
# input_cache_hit为None表示该模型不支持缓存
PRICING = {
    # DeepSeek
    "deepseek-chat": {  # v4-flash
        "input_cache_miss": 0.14,
        "input_cache_hit": 0.0028,
        "output": 0.28,
    },
    "deepseek-reasoner": {  # v4-pro
        "input_cache_miss": 0.435,
        "input_cache_hit": 0.003625,
        "output": 0.87,
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

def get_pricing(model: str) -> dict:
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

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        # DeepSeek返回的prompt_tokens_details
        prompt_details = usage.get("prompt_tokens_details", {})
        cache_hit = prompt_details.get("cached_tokens", 0)
        cache_miss = prompt_tokens - cache_hit

        pricing = get_pricing(model)
        if pricing is None:
            return  # 未知模型不计费
        cache_hit_price = pricing.get("input_cache_hit") or pricing["input_cache_miss"]
        cost = (cache_miss * pricing["input_cache_miss"]
                + cache_hit * cache_hit_price
                + completion_tokens * pricing["output"]) / 1_000_000

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
```

### Step 2: 修改 `src/core/openai_client.py`

在收到API响应后提取usage并调用tracker。找到处理streaming和非streaming响应的位置：

**非streaming响应**（`complete`方法内）：
```python
# 在返回result之前
if response_data.get("usage"):
    from src.core.token_tracker import token_tracker
    token_tracker.update(response_data["usage"], model)
```

**Streaming响应**（`stream_complete`方法内）：
streaming响应的usage在最后一个chunk的`usage`字段中（当`stream_options={"include_usage": True}`时返回）：
```python
# 在处理stream chunk的循环中
if chunk.get("usage"):
    from src.core.token_tracker import token_tracker
    token_tracker.update(chunk["usage"], model)
```

同时，在streaming请求时加上`stream_options`参数：
```python
payload["stream_options"] = {"include_usage": True}
```

### Step 3: 新增WebSocket事件

在 `src/api/chat_ws.py` 中：

1. 新增事件类型 `token_stats`，每次token_tracker.update后通过websocket推送：
```python
from src.core.token_tracker import token_tracker

# 在update之后
stats = token_tracker.get_stats()
await websocket.send_json({"type": "token_stats", "data": stats})
```

2. 新增请求类型 `get_token_stats`，前端主动查询：
```python
if request_type == "get_token_stats":
    stats = token_tracker.get_stats()
    await websocket.send_json({"type": "token_stats", "data": stats})
```

3. 新增请求类型 `reset_token_stats`，切换场景时调用：
```python
if request_type == "reset_token_stats":
    token_tracker.reset_current()
    stats = token_tracker.get_stats()
    await websocket.send_json({"type": "token_stats", "data": stats})
```

### Step 4: 场景切换联动

在新建对话/切换对话的处理逻辑中，调用 `token_tracker.reset_current()` 重置当前统计。

---

## 前端

### Step 5: 新建 `src/components/TokenPanel.tsx`

面板布局（从上到下）：

```
┌─────────────────────────────┐
│  Token 用量    [本次/累计]   │  ← 切换标签
├─────────────────────────────┤
│  输入    1,234 tokens       │
│  ├ 缓存命中   890 tokens    │  ← 缩进，绿色小字
│  └ 缓存未命中  344 tokens   │  ← 缩进，灰色小字
│  输出    567 tokens         │
│  ─────────────────────────  │
│  请求次数   5               │
│  费用      $0.0012         │  ← 蓝色加粗
└─────────────────────────────┘
```

样式要求：
- 面板宽度固定240px
- 背景#FFFFFF，圆角8px，边框1px solid #E5E6EB
- 标签切换：本次（当前场景）/ 累计（历史全部）
- 缓存命中行用颜色#00B42A（ArcoDesign绿）
- 缓存未命中行用颜色#86909C（灰色）
- 费用数字用#165DFF加粗
- Token数用千分位格式化
- 费用显示：<$0.01时显示<$0.01，否则精确到小数点后4位

### Step 6: 集成到主界面

在对话页面右侧或底栏添加Token面板入口：
- 入口：一个图标按钮（Lucide的`Activity`图标），点击展开/收起TokenPanel
- 位置：消息输入框右上角，与发送按钮同行
- 面板以popover/drawer形式弹出，不占用聊天区域

### Step 7: WebSocket监听

在前端WebSocket处理中：
1. 监听 `token_stats` 事件，更新面板数据
2. 切换对话时发送 `reset_token_stats` 请求
3. 进入已有对话时发送 `get_token_stats` 请求获取当前状态

---

## 注意事项
- 支持DeepSeek/OpenAI/Claude/Qwen/GLM主流模型定价，按模型名前缀自动匹配
- 不支持缓存的模型（input_cache_hit为None），缓存命中按cache_miss价格计
- 未知模型不计费，面板费用显示"--"
- 本地模型（Ollama等）不返回usage，面板Token显示"--"
- streaming必须加`stream_options`才能拿到usage，否则usage为null
- 费用单位为美元，前端不做人民币转换（汇率波动）

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
