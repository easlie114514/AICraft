---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_DeepSeek_Integration.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782099046246
    ReservedCode2: ""
---
# AICraft DeepSeek 接入规范与模型切换方案

> 目标：用最少的配置接入 DeepSeek，支持 Pro/Flash 自动切换，用户可手动选模型
> 日期：2026-06-22

---

## 1. 当前状态

搜索重构和双协议路由已完成：
- ✅ Bing/DDG 爬虫已删除
- ✅ DeepSeek 走 Anthropic SDK 直连 `api.deepseek.com/anthropic`
- ✅ server-side `web_search_20250305` 已接入
- ✅ agent_loop.py 双协议路由（Anthropic SDK / litellm）
- ✅ 快捷数据源（天气/金价/汇率/热搜）作为客户端 function calling 工具
- ✅ thinking 参数已对齐 DeepSeek 官方规范（`reasoning_effort: "max"`）

**待做**：定制通道 UI + Pro/Flash 自动切换 + Key 联动

---

## 2. 定制通道方案

### 2.1 用户操作流程

```
添加模型 → 选择通道类型
┌──────────────────────────────┐
│  选择模型通道                  │
│                              │
│  ○ DeepSeek 定制通道  ← 选这个 │
│  ○ OpenAI 标准通道            │
│  ○ Anthropic 标准通道         │
│  ○ 自定义（手动填写端点）       │
│                              │
│          [下一步]              │
└──────────────────────────────┘

填入 API Key
┌──────────────────────────────┐
│  DeepSeek 定制通道             │
│                              │
│  API Key: [sk-81dea...     ] │
│                              │
│  将自动创建以下模型：           │
│  ☑ DeepSeek V4 Pro（主力）    │
│  ☑ DeepSeek V4 Flash（轻量）  │
│                              │
│  端点: api.deepseek.com/     │  ← 只读展示
│        anthropic              │
│  协议: Anthropic               │  ← 只读展示
│                              │
│          [保存]                │
└──────────────────────────────┘

→ 自动生成两个 models/*.json
→ 输入框右侧下拉立即出现 Pro / Flash 选项
```

**用户只需填1项：API Key。** 端点、协议、模型列表全部内置。

### 2.2 后端实现

"DeepSeek 定制通道" = 预设模板，保存时自动生成多个 `models/*.json`，与现有配置格式完全一致：

```python
# backend/api/models.py — 添加模型接口

CHANNEL_PRESETS = {
    "deepseek": {
        "name": "DeepSeek 定制通道",
        "base_url": "https://api.deepseek.com/anthropic",
        "protocol": "anthropic",
        "models": [
            {
                "filename": "dsv4pro.json",
                "name": "DeepSeek V4 Pro",
                "model_id": "deepseek-v4-pro",
                "tier": "pro",
                "supports_thinking": True,
                "supports_web_search": True,
                "is_default": True,
            },
            {
                "filename": "dsv4flash.json",
                "name": "DeepSeek V4 Flash",
                "model_id": "deepseek-v4-flash",
                "tier": "flash",
                "supports_thinking": True,
                "supports_web_search": True,
                "is_default": False,
            },
        ],
    },
    # 后续可加 openai / anthropic 等通道预设
}

async def add_channel(channel_type: str, api_key: str):
    """通过通道预设批量创建模型配置"""
    preset = CHANNEL_PRESETS.get(channel_type)
    if not preset:
        raise ValueError(f"未知通道类型: {channel_type}")

    for model_def in preset["models"]:
        config = {
            "name": model_def["name"],
            "provider": channel_type,
            "model_id": model_def["model_id"],
            "api_key": api_key,
            "api_base": preset["base_url"],
            "protocol": preset["protocol"],
            "tier": model_def["tier"],
            "supports_thinking": model_def["supports_thinking"],
            "supports_web_search": model_def["supports_web_search"],
            "is_default": model_def["is_default"],
        }
        save_json(MODELS_DIR / model_def["filename"], config)
```

生成的配置文件示例：

```json
// models/dsv4pro.json
{
  "name": "DeepSeek V4 Pro",
  "provider": "deepseek",
  "model_id": "deepseek-v4-pro",
  "api_key": "sk-81dea3e778bb49488de2b28b4e60cbfe",
  "api_base": "https://api.deepseek.com/anthropic",
  "protocol": "anthropic",
  "tier": "pro",
  "supports_thinking": true,
  "supports_web_search": true,
  "is_default": true
}

// models/dsv4flash.json
{
  "name": "DeepSeek V4 Flash",
  "provider": "deepseek",
  "model_id": "deepseek-v4-flash",
  "api_key": "sk-81dea3e778bb49488de2b28b4e60cbfe",
  "api_base": "https://api.deepseek.com/anthropic",
  "protocol": "anthropic",
  "tier": "flash",
  "supports_thinking": true,
  "supports_web_search": true,
  "is_default": false
}
```

与现有架构完全兼容——`models/` 目录下多几个 JSON，`get_all_model_configs()` 自动读到，输入框右侧下拉自动列出。

### 2.3 Key 更新联动

同一个 provider 下的模型共享 Key，修改时联动：

```python
async def update_model_config(model_name: str, updates: dict):
    """更新模型配置，同 provider 的 api_key 自动联动"""
    config = load_json(MODELS_DIR / f"{model_name}.json")
    for k, v in updates.items():
        config[k] = v
    save_json(MODELS_DIR / f"{model_name}.json", config)

    # 如果修改了 api_key，同 provider 的其他模型也同步
    if "api_key" in updates:
        provider = config.get("provider", "")
        for f in MODELS_DIR.glob("*.json"):
            other = load_json(f)
            if other.get("provider") == provider and other.get("name") != config["name"]:
                other["api_key"] = updates["api_key"]
                save_json(f, other)
```

---

## 3. Pro/Flash 自动切换

### 3.1 场景

| 场景 | 用什么模型 | 为什么 |
|---|---|---|
| 主对话 | 用户选的模型 | 尊重用户选择 |
| 记忆压缩 | Flash | 摘要不需要 Pro 推理能力 |
| 角色切换摘要 | Flash | 提取事实信息，轻量活 |
| RAG 检索摘要 | Flash | 整理检索片段 |

### 3.2 实现

```python
# src/core/model_selector.py（新文件）

def get_flash_model_config() -> dict | None:
    """获取当前 provider 的 Flash 模型配置，用于后台降级"""
    models = get_all_model_configs()
    for m in models:
        if m.get("tier") == "flash":
            return m
    return None


def select_model_for_task(task: str, user_model_config: dict) -> dict:
    """根据任务类型选择模型配置"""
    if task == "chat":
        return user_model_config

    if task in ("memory_compact", "role_switch_summary", "rag_summary"):
        if user_model_config.get("tier") == "flash":
            return user_model_config
        flash = get_flash_model_config()
        if flash:
            return flash

    return user_model_config
```

### 3.3 chat_ws.py 改动

```python
# 记忆压缩
# 当前：model_config=model_config
# 改为：model_config=select_model_for_task("memory_compact", model_config)

# 角色切换摘要
# 当前：model=model_config.get("model_id", "")
# 改为：从 select_model_for_task("role_switch_summary", model_config) 取 model_id
```

---

## 4. 完整改动清单

### 新增文件
| 文件 | 说明 |
|---|---|
| `src/core/model_selector.py` | 自动模型选择（后台任务降级到Flash） |

### 修改文件
| 文件 | 改动 |
|---|---|
| `backend/api/models.py` | 新增通道预设 + 批量创建接口 + Key联动更新 |
| `backend/chat_ws.py` | 后台任务（记忆压缩/角色摘要）模型降级到Flash |
| `src/utils/config.py` | model_config 读取兼容新字段（protocol/tier/supports_web_search） |
| `models/dsv4pro.json` | 定制通道生成（替代旧的 dpv4p.json） |
| `models/dsv4flash.json` | 定制通道生成（新增） |

### 删除文件
| 文件 | 原因 |
|---|---|
| `models/dpv4p.json` | 被定制通道自动生成的 dsv4pro.json + dsv4flash.json 替代 |

---

## 5. 实施优先级

### P0：定制通道 UI
1. 添加模型页面增加"通道类型"选择
2. 选"DeepSeek 定制通道" → 填 Key → 自动创建 Pro + Flash
3. Key 联动更新
4. 删除旧的 `models/dpv4p.json`

### P1：Pro/Flash 自动切换
1. 创建 `model_selector.py`
2. chat_ws.py 后台任务降级到 Flash

### P2：多通道预设
1. OpenAI 标准通道（GPT-5.5 / GPT-4o-mini）
2. Anthropic 标准通道（Claude Sonnet / Haiku）
3. 自定义通道（填 base_url + protocol + model_id）

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
