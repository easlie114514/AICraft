---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_WebSearch_Refactor.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782096743142
    ReservedCode2: ""
---
# AICraft 联网搜索重构方案

> 目标：废弃Bing HTML爬虫 + DDG降级方案，改用各模型原生的 server-side web_search 能力
> 日期：2026-06-22

---

## 1. 当前问题

Bing HTML爬虫已彻底废了：
- 搜"英雄联盟 上单 兵线"返回的是百度百科"英雄"（张艺谋电影）和豆瓣影评
- `<li class="b_algo">` 正则匹配到了侧边栏/知识面板，而非有机搜索结果
- cn.bing.com 页面结构变了，正则不可靠

DDG降级也不可用：
- 国内被墙，无代理无法连接
- 违反"通用方案优先，不依赖代理"原则
- Python库 `duckduckgo_search` 反爬频繁失效

**结论：HTML爬虫路线天然不可靠，必须走API路线。**

---

## 2. 新方案：模型原生 web_search

三大模型提供商都支持 server-side web_search：

| Provider | 工具类型 | 端点 | 额外Key | 国内直连 |
|---|---|---|---|---|
| **DeepSeek** | `web_search_20250305` | `api.deepseek.com/anthropic` | 不需要 | ✅ |
| **Anthropic Claude** | `web_search_20250305` | `api.anthropic.com` | 不需要 | ❌ 需代理 |
| **OpenAI** | `web_search` | Responses API `api.openai.com` | 不需要 | ❌ 需代理 |

### 核心原理

Server-side web_search 是**模型平台执行搜索**，而非客户端自己爬：
1. 客户端在请求的 `tools` 数组中声明 `web_search` 工具
2. 模型自主判断是否需要搜索，自动调用
3. 平台在服务端执行搜索，将结果注入模型上下文
4. 模型基于搜索结果生成带来源引用的回答

**客户端不需要自己实现搜索逻辑，不需要爬虫，不需要第三方搜索API。**

---

## 3. 各 Provider 接入细节

### 3.1 DeepSeek（主力，国内直连）

**端点**：`https://api.deepseek.com/anthropic`（Anthropic兼容端点）

**工具声明**：
```json
{
  "type": "web_search_20250305",
  "name": "web_search",
  "max_uses": 5
}
```

**请求示例**（Anthropic协议）：
```python
from anthropic import Anthropic

client = Anthropic(
    api_key="YOUR_DEEPSEEK_API_KEY",
    base_url="https://api.deepseek.com/anthropic",
)

response = client.messages.create(
    model="deepseek-v4-flash",
    max_tokens=4096,
    tools=[
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }
    ],
    messages=[
        {"role": "user", "content": "英雄联盟上单兵线管理技巧"}
    ],
)
```

**响应结构**：
```json
{
  "content": [
    {
      "type": "text",
      "text": "我来搜索一下相关信息。"
    },
    {
      "type": "server_tool_use",
      "id": "srvtoolu_xxx",
      "name": "web_search",
      "input": {"query": "英雄联盟上单兵线管理技巧"}
    },
    {
      "type": "web_search_tool_result",
      "tool_use_id": "srvtoolu_xxx",
      "content": [
        {
          "type": "web_search_result",
          "url": "https://...",
          "title": "...",
          "encrypted_content": "...",
          "page_age": "..."
        }
      ]
    },
    {
      "type": "text",
      "text": "基于搜索结果，以下是英雄联盟上单兵线管理技巧..."
    }
  ]
}
```

**流式响应**：
- `content_block_start` type=`server_tool_use` → 模型决定搜索
- `content_block_start` type=`web_search_tool_result` → 搜索结果返回
- `content_block_start` type=`text` → 基于搜索结果的回答

**注意事项**：
- DeepSeek OpenAI端点 (`api.deepseek.com`) **不支持** web_search，必须走 Anthropic 端点
- `max_uses` 限制单次请求搜索次数，默认可不设
- 搜索结果中的 `encrypted_content` 是加密的，客户端无法直接读取原文，但模型可以理解

### 3.2 Anthropic Claude（需代理）

**端点**：`https://api.anthropic.com`

**工具声明**（与DeepSeek完全相同）：
```json
{
  "type": "web_search_20250305",
  "name": "web_search",
  "max_uses": 5,
  "allowed_domains": ["example.com"],
  "blocked_domains": ["untrusted.com"],
  "user_location": {
    "type": "approximate",
    "city": "Beijing",
    "country": "CN",
    "timezone": "Asia/Shanghai"
  }
}
```

**额外参数**（DeepSeek也支持）：
- `allowed_domains`：只搜索指定域名
- `blocked_domains`：排除指定域名
- `user_location`：本地化搜索结果（城市/地区/国家/时区）

**支持模型**：Claude Sonnet 4.5, Sonnet 4, Haiku 4.5, Haiku 3.5, Opus 4.1, Opus 4

### 3.3 OpenAI（需代理，Responses API）

**端点**：`https://api.openai.com/v1/responses`（不是Chat Completions！）

**工具声明**：
```json
{
  "type": "web_search",
  "search_content_types": ["text"],
  "user_location": {
    "type": "approximate",
    "city": "Beijing",
    "country": "CN"
  }
}
```

**请求示例**（Python SDK）：
```python
from openai import OpenAI

client = OpenAI(api_key="YOUR_OPENAI_API_KEY")

response = client.responses.create(
    model="gpt-5.5",
    tools=[{"type": "web_search"}],
    input="英雄联盟上单兵线管理技巧",
)
```

**注意事项**：
- OpenAI的web_search走Responses API，不是Chat Completions
- Chat Completions端点不支持server-side web_search
- AICraft当前用的是OpenAI兼容协议（litellm），如果要支持OpenAI web_search，需要切换到Responses API
- `search_content_types` 支持 `["text"]`、`["image"]`、`["image", "text"]`

---

## 4. AICraft 重构设计

### 4.1 架构变更

**当前架构**：
```
agent_loop → 工具调用 web_search → web_search.py（Bing爬虫/DDG/快捷源）→ 返回结果
```

**新架构**：
```
agent_loop → 请求携带 tools=[web_search] → 模型平台执行搜索 → 返回带搜索结果的回答
```

**关键区别**：web_search 不再是客户端工具（client-side tool），而是服务端工具（server-side tool）。模型自己决定搜不搜、搜什么，搜索在服务端执行，结果直接注入模型上下文。

### 4.2 文件改动清单

#### 4.2.1 `src/core/web_search.py` — 重构

**删除**：
- `_search_bing()` — Bing HTML爬虫，彻底废弃
- `_search_duckduckgo()` — DDG搜索，国内不可用
- `WEB_SEARCH_TOOL` — 客户端工具定义（不再需要，改为服务端工具声明）
- `web_search()` 主入口函数
- `duckduckgo_search` 依赖

**保留**：
- 快捷数据源（天气/金价/汇率/热搜）— 这些直接请求权威API，质量可靠
- `_strip_html()` 辅助函数（快捷源仍在用）

**新增**：
- `get_server_search_tools(provider: str) -> list[dict]` — 根据模型provider返回对应的server-side搜索工具声明
- `parse_search_events(event)` — 解析流式响应中的搜索相关事件（`server_tool_use` / `web_search_tool_result`），提取搜索状态和来源链接供前端展示

```python
def get_server_search_tools(provider: str) -> list[dict]:
    """根据模型provider返回server-side web_search工具声明"""
    if provider == "deepseek":
        return [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }]
    elif provider == "anthropic":
        return [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
            "user_location": {
                "type": "approximate",
                "city": "Beijing",
                "country": "CN",
                "timezone": "Asia/Shanghai",
            },
        }]
    elif provider == "openai":
        return [{
            "type": "web_search",
            "search_content_types": ["text"],
        }]
    else:
        # 不支持server-side搜索的provider，返回空（无搜索能力）
        return []
```

#### 4.2.2 `src/core/agent_loop.py` — 修改

**改动点**：

1. **构建请求时注入server-side工具**：

在 `_build_llm_kwargs` 中，当搜索开关开启时，将 `get_server_search_tools(provider)` 的结果合并到 `tools` 参数中。

注意：server-side tools 和 client-side tools（如自定义function calling工具）可以共存，合并在同一个 `tools` 数组里。

2. **DeepSeek必须走Anthropic端点**：

当前 AICraft 的 DeepSeek 走的是 `api.deepseek.com`（OpenAI兼容端点），但 web_search 只在 `api.deepseek.com/anthropic` 端点可用。

**方案**：当 DeepSeek 且搜索开启时，切换 base_url 到 `api.deepseek.com/anthropic`，使用 Anthropic 协议发请求。这意味着 DeepSeek + 搜索开启 时，需要用 Anthropic SDK 而非 OpenAI SDK。

**替代方案**：如果不想在运行时切换SDK，可以始终让 DeepSeek 走 Anthropic 端点（不搜索时也走Anthropic端点），这样代码更简洁，但需要将整个 DeepSeek 请求路径从 litellm/OpenAI 切换到 Anthropic SDK。

3. **流式响应解析**：

Anthropic协议的流式响应中，搜索相关事件类型：
- `content_block_start` + `type: "server_tool_use"` → 模型决定搜索
- `content_block_start` + `type: "web_search_tool_result"` → 搜索结果返回
- 在 `text` 类型的 content_block 中，模型会基于搜索结果生成回答

需要在前端WebSocket推送中增加搜索状态事件，让前端能展示"正在搜索..."状态和来源链接。

#### 4.2.3 `backend/chat_ws.py` — 修改

1. 删除当前注入客户端 `WEB_SEARCH_TOOL` 到 tools 列表的逻辑
2. 搜索开关改为控制是否在请求中注入 server-side `web_search` 工具
3. 流式推送中增加搜索状态事件类型

#### 4.2.4 `models/dpv4p.json` — 可能修改

如果决定让 DeepSeek 始终走 Anthropic 端点，需要在模型配置中增加：
```json
{
  "anthropic_base_url": "https://api.deepseek.com/anthropic",
  "protocol": "anthropic"
}
```

#### 4.2.5 `requirements.txt` — 修改

- 删除 `duckduckgo-search`
- 可能需要增加 `anthropic` SDK（如果 DeepSeek 要走 Anthropic 协议）

### 4.3 快捷数据源保留策略

快捷数据源（天气/金价/汇率/热搜）仍然保留为客户端工具（function calling）：
- 这些是精确API调用，不需要搜索引擎
- 质量比搜索更可靠（直接请求权威源）
- 模型通过 function calling 调用它们，和 server-side web_search 不冲突

所以重构后的工具列表是：
```
tools = [
    # 客户端工具（function calling）
    quick_weather_tool,
    quick_gold_price_tool,
    quick_exchange_rate_tool,
    quick_hot_news_tool,
    # 服务端工具（模型平台执行）
    web_search_20250305,  # DeepSeek/Claude
    # 或
    web_search,           # OpenAI
]
```

### 4.4 搜索结果展示

Server-side web_search 的搜索结果直接融入模型的回答中（带来源引用），不需要客户端单独解析搜索结果再拼装。

但前端可以额外展示：
1. **搜索状态**：解析 `server_tool_use` 事件，显示"正在搜索..."
2. **来源列表**：解析 `web_search_tool_result` 事件，提取 URL 和 title，展示为引用来源

---

## 5. 实施优先级

### P0：DeepSeek web_search 可用（最小改动）

1. 让 DeepSeek 搜索请求走 Anthropic 端点
2. 注入 `web_search_20250305` 工具声明
3. 解析流式响应中的搜索事件
4. 删除 Bing 爬虫和 DDG 代码

### P1：前端搜索状态展示

1. WebSocket 推送搜索状态事件
2. 前端显示"正在搜索..."和来源链接

### P2：多Provider统一

1. Claude 原生 Anthropic 端点的 web_search
2. OpenAI Responses API 的 web_search（需切换到 Responses API）

---

## 6. 关键决策点（需确认）

### 6.1 DeepSeek 是否始终走 Anthropic 端点？

**选项A**：DeepSeek 始终走 `api.deepseek.com/anthropic`（无论是否搜索）
- 优点：代码简洁，不需要运行时切换协议
- 缺点：需要从 litellm/OpenAI SDK 切换到 Anthropic SDK 处理 DeepSeek
- 影响：这是 P0-1（DeepSeek走原生SDK替代litellm）的一部分

**选项B**：DeepSeek 默认走 OpenAI 端点，搜索开启时切换到 Anthropic 端点
- 优点：改动最小，只改搜索相关的代码路径
- 缺点：两套协议共存，复杂度高，litellm 转换层仍然存在

**推荐选项A**：这与之前规划的 P0-1（DeepSeek走原生SDK替代litellm）目标一致，一步到位。

### 6.2 不支持 server-side 搜索的模型怎么办？

当前 AICraft 只用 DeepSeek，所以 P0 只需支持 DeepSeek。
后续如果接入不支持 server-side 搜索的模型（如本地部署的开源模型），有两个选择：
1. 该模型无搜索能力（简单直接）
2. 保留一个简化版Bing爬虫作为降级（增加维护负担）

**推荐**：先选方案1，无搜索能力就不搜，后续按需加。

---

## 7. 参考资源

- [Anthropic Web Search Tool 文档](https://claude.yourdocs.dev/docs/agents-and-tools/tool-use/web-search-tool)
- [deepseek-kit webSearch 封装](https://github.com/FliPPeDround/deepseek-kit) — 开源MIT，DeepSeek Anthropic端点 web_search 的参考实现
- [DeepSeek Anthropic 兼容端点](https://api.deepseek.com/anthropic)
- [OpenAI Responses API Web Search](https://platform.openai.com/docs/api-reference/responses)

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
