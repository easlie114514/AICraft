---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_Litellm_To_Httpx.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782178944894
    ReservedCode2: ""
---
# AICraft litellm → httpx 替换方案

> 目标：去掉 litellm 依赖（~80MB），用 httpx 直接调 OpenAI 兼容 API，功能零损失
> 前提：当前版本 RAG 正常工作（onnx 本地 embedding），此文档只管 litellm 替换，不动 RAG
> 基线：commit 47527d3（develop_new 分支）

---

## 一、litellm 在项目中的使用位置

| 文件 | 用途 | 调用方式 |
|------|------|---------|
| `src/core/llm.py` L1 | `import litellm` | 模块级导入 |
| `src/core/llm.py` `chat_completion()` | 流式聊天 + 工具调用 | `await litellm.acompletion(**kwargs)` |
| `src/core/llm.py` `chat_completion()` 非流式分支 | 非流式完整响应 | `await litellm.acompletion(**kwargs)` |
| `src/core/llm.py` `simple_completion()` litellm 分支 | 非 Anthropic 协议的简单调用 | `await litellm.acompletion(**kwargs)` |
| `src/core/agent_loop.py` L12 | `import litellm` | 模块级导入 |
| `src/core/agent_loop.py` `_build_llm_kwargs()` | 构建 litellm 请求参数 | 返回 dict 给 `litellm.acompletion` |
| `src/core/agent_loop.py` `agent_loop()` litellm 分支 | 非 DeepSeek/Claude 模型的流式调用 | `await litellm.acompletion(**kwargs)` |

**关键理解**：项目有两条 LLM 调用路径——
1. **Anthropic SDK 路径**（DeepSeek/Claude）→ 已用 `anthropic` SDK 直连，**不走 litellm**，不需改动
2. **litellm 路径**（其他 OpenAI 兼容模型）→ 本次替换的目标

---

## 二、新建文件：`src/core/openai_client.py`

这是替代 litellm 的核心模块，实现 OpenAI 兼容 API 的流式/非流式调用。

设计原则：**返回对象的属性结构与 litellm 的 ModelResponse 对齐**，让调用方代码改动最小。

```python
"""OpenAI 兼容 API 客户端 — 替代 litellm

所有 OpenAI 兼容格式的 LLM 调用都通过此模块完成。
包括：DeepSeek OpenAI 端点、硅基流动、Ollama、OpenAI 官方等。
"""

import json
from typing import Any, AsyncGenerator

import httpx


# ═══════════════════════════════════════════════════════════
# 数据结构 — 与 litellm ModelResponse 属性对齐
# ═══════════════════════════════════════════════════════════

class OpenAIFunctionDelta:
    """delta.tool_calls[i].function"""
    def __init__(self, data: dict):
        self.name = data.get("name") or None
        self.arguments = data.get("arguments") or None


class OpenAIToolCallDelta:
    """delta.tool_calls[i]"""
    def __init__(self, data: dict):
        self.index = data.get("index", 0)
        self.id = data.get("id") or ""
        self.function = OpenAIFunctionDelta(data.get("function", {}))


class OpenAIDelta:
    """chunk.choices[0].delta"""
    def __init__(self, data: dict):
        self.content = data.get("content") or None
        self.reasoning_content = data.get("reasoning_content") or None  # DeepSeek thinking
        self.tool_calls = None
        raw_tc = data.get("tool_calls")
        if raw_tc:
            self.tool_calls = [OpenAIToolCallDelta(tc) for tc in raw_tc]


class OpenAIChoice:
    """chunk.choices[0]"""
    def __init__(self, data: dict):
        self.delta = OpenAIDelta(data.get("delta", {}))
        self.index = data.get("index", 0)


class OpenAIStreamChunk:
    """SSE 解析后的流式 chunk"""
    def __init__(self, data: dict):
        self.choices = [OpenAIChoice(c) for c in data.get("choices", [])]


class OpenAIFunction:
    """非流式 message.tool_calls[i].function"""
    def __init__(self, data: dict):
        self.name = data.get("name") or ""
        self.arguments = data.get("arguments") or ""


class OpenAIToolCall:
    """非流式 message.tool_calls[i]"""
    def __init__(self, data: dict):
        self.id = data.get("id") or ""
        self.function = OpenAIFunction(data.get("function", {}))


class OpenAIMessage:
    """非流式响应的 message"""
    def __init__(self, data: dict):
        self.content = data.get("content") or ""
        self.tool_calls = None
        raw_tc = data.get("tool_calls")
        if raw_tc:
            self.tool_calls = [OpenAIToolCall(tc) for tc in raw_tc]


# ═══════════════════════════════════════════════════════════
# 公开 API — 签名与 litellm.acompletion 兼容
# ═══════════════════════════════════════════════════════════

async def acompletion(
    model: str,
    messages: list[dict],
    api_key: str = "",
    api_base: str = "https://api.openai.com/v1",
    stream: bool = True,
    tools: list[dict] | None = None,
    max_tokens: int | None = None,
    **kwargs,
) -> AsyncGenerator[OpenAIStreamChunk, None] | OpenAIMessage:
    """替代 litellm.acompletion

    stream=True  → 返回 AsyncGenerator[OpenAIStreamChunk, None]
    stream=False → 返回 OpenAIMessage
    """
    url = f"{api_base.rstrip('/')}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    if tools:
        payload["tools"] = tools
    if max_tokens:
        payload["max_tokens"] = max_tokens
    payload.update(kwargs)  # 透传 temperature 等其他参数

    if stream:
        return _stream_response(url, headers, payload)
    else:
        return await _non_stream_response(url, headers, payload)


# ═══════════════════════════════════════════════════════════
# 内部实现
# ═══════════════════════════════════════════════════════════

async def _stream_response(
    url: str, headers: dict, payload: dict
) -> AsyncGenerator[OpenAIStreamChunk, None]:
    """流式 SSE 读取并解析"""
    timeout = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise httpx.HTTPStatusError(
                    f"API 返回 {resp.status_code}: {body.decode(errors='replace')[:500]}",
                    request=resp.request,
                    response=resp,
                )

            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(data)
                    yield OpenAIStreamChunk(chunk_data)
                except json.JSONDecodeError:
                    continue  # 跳过无法解析的行


async def _non_stream_response(
    url: str, headers: dict, payload: dict
) -> OpenAIMessage:
    """非流式完整响应"""
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return OpenAIMessage(data["choices"][0]["message"])
```

---

## 三、修改 `src/core/llm.py`

### 3.1 导入替换

```python
# 删除
import litellm

# 改为
from src.core.openai_client import acompletion as openai_completion
```

### 3.2 `chat_completion()` — kwargs 构建调整

原代码中 api_key/api_base 可能为空字符串，litellm 会忽略空值，但 openai_completion 需要默认值：

```python
# 原代码
kwargs: dict = {
    "model": model_config["model_id"],
    "messages": messages,
    "stream": stream,
}
if api_key:
    kwargs["api_key"] = api_key
if api_base:
    kwargs["api_base"] = api_base
if tools:
    kwargs["tools"] = tools

# 替换为 — api_base 必须有值，api_key 允许空（本地模型不验证）
kwargs: dict = {
    "model": model_config["model_id"],
    "messages": messages,
    "stream": stream,
    "api_key": api_key,
    "api_base": api_base or "https://api.openai.com/v1",
}
if tools:
    kwargs["tools"] = tools
```

### 3.3 `chat_completion()` 流式分支

```python
# 原代码
response = await litellm.acompletion(**kwargs)

# 替换为
response = await openai_completion(**kwargs)
```

后续的 `async for chunk in response:` 循环**完全不变**，因为 `OpenAIStreamChunk` 的属性结构与 litellm 对齐：
- `chunk.choices[0].delta.content` — 文本增量 ✅
- `chunk.choices[0].delta.tool_calls` — 工具调用增量 ✅
- `tc.index` / `tc.id` / `tc.function.name` / `tc.function.arguments` — 全对齐 ✅

### 3.4 `chat_completion()` 非流式分支

```python
# 原代码
response = await litellm.acompletion(**kwargs)
msg = response.choices[0].message
content = msg.content or ""

# 替换为
response = await openai_completion(**kwargs)
msg = response  # 非流式直接返回 OpenAIMessage
content = msg.content or ""
```

tool_calls 处理也完全对齐：

```python
# 原代码
if msg.tool_calls:
    yield {
        "type": "tool_calls",
        "tool_calls": [
            {
                "id": tc.id or "",
                "function_name": tc.function.name if tc.function else "",
                "function_arguments": tc.function.arguments if tc.function else "",
            }
            for tc in msg.tool_calls
        ],
        "text": content,
    }

# 替换后（结构对齐，tc.function 必然存在）
if msg.tool_calls:
    yield {
        "type": "tool_calls",
        "tool_calls": [
            {
                "id": tc.id or "",
                "function_name": tc.function.name,
                "function_arguments": tc.function.arguments,
            }
            for tc in msg.tool_calls
        ],
        "text": content,
    }
```

### 3.5 `simple_completion()` litellm 分支

```python
# ── 原代码（litellm 路径）──
kwargs: dict = {
    "model": model_id,
    "messages": messages,
    "max_tokens": max_tokens,
}
if api_key:
    kwargs["api_key"] = api_key
if api_base:
    kwargs["api_base"] = api_base

response = await litellm.acompletion(**kwargs)
return response.choices[0].message.content or ""

# ── 替换为 ──
response = await openai_completion(
    model=model_id,
    messages=messages,
    max_tokens=max_tokens,
    api_key=api_key or "",
    api_base=api_base or "https://api.openai.com/v1",
    stream=False,
)
return response.content or ""
```

---

## 四、修改 `src/core/agent_loop.py`

### 4.1 导入替换

```python
# 删除
import litellm

# 改为
from src.core.openai_client import acompletion as openai_completion
```

### 4.2 `_build_llm_kwargs()` 修改

```python
# ── 原代码 ──
async def _build_llm_kwargs(
    messages: list[dict],
    tools: list[dict] | None,
    model_config: dict,
    thinking_enabled: bool = False,
) -> dict:
    """构建 litellm.completion 的 kwargs"""
    kwargs: dict = {
        "model": model_config.get("model_id", ""),
        "messages": messages,
        "stream": True,
    }
    for key in ("api_key", "api_base"):
        val = model_config.get(key, "")
        if val:
            kwargs[key] = val
    if tools:
        kwargs["tools"] = tools
    if thinking_enabled:
        model_id = model_config.get("model_id", "").lower()
        if "claude" in model_id:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 10000}
    return kwargs

# ── 替换为 ──
async def _build_llm_kwargs(
    messages: list[dict],
    tools: list[dict] | None,
    model_config: dict,
    thinking_enabled: bool = False,
) -> dict:
    """构建 openai_completion 的 kwargs"""
    kwargs: dict = {
        "model": model_config.get("model_id", ""),
        "messages": messages,
        "stream": True,
        "api_key": model_config.get("api_key", ""),
        "api_base": model_config.get("api_base", "") or "https://api.openai.com/v1",
    }
    if tools:
        kwargs["tools"] = tools
    # 注意：thinking 参数不是 OpenAI 兼容 API 的标准参数
    # DeepSeek/Claude 走 Anthropic SDK 路径，不会进入此函数
    return kwargs
```

**删除了 Claude thinking 逻辑**，因为走 litellm/openai_completion 路径的不会是 Claude/DeepSeek（它们走 Anthropic SDK）。

### 4.3 `agent_loop()` litellm 分支核心替换

```python
# ── 原代码 ──
kwargs = await _build_llm_kwargs(messages, tools, model_config, thinking_enabled)
response = await litellm.acompletion(**kwargs)

# ── 替换为 ──
kwargs = await _build_llm_kwargs(messages, tools, model_config, thinking_enabled)
response = await openai_completion(**kwargs)
```

### 4.4 `agent_loop()` litellm 分支的 thinking 处理

原代码用 `getattr` 读取 `reasoning_content`：

```python
# ── 原代码 ──
if thinking_enabled:
    reasoning = (
        getattr(delta, 'reasoning_content', None)
        or getattr(delta, 'thinking', None)
    )
    if reasoning:
        ...
```

替换后 `OpenAIDelta` 已直接暴露 `reasoning_content` 属性：

```python
# ── 替换为 ──
if thinking_enabled:
    reasoning = delta.reasoning_content
    if reasoning:
        if thinking_start_time is None:
            thinking_start_time = time.time()
        yield {"type": "thinking", "content": reasoning}
```

### 4.5 litellm 分支后续逻辑 — 完全不变

以下代码**不需要任何修改**：
- `delta.tool_calls` 的增量累积
- `delta.content` 的文本增量 yield
- `tool_call_deltas` 转换为 `tool_calls_list`
- `messages.append(...)` 消息拼接
- 工具执行（quick_source / web_search / MCP）
- `tool_result` 事件 yield

因为 `OpenAIStreamChunk` → `OpenAIChoice` → `OpenAIDelta` → `OpenAIToolCallDelta` 的属性结构与 litellm 完全对齐。

---

## 五、修改 `requirements.txt`

```diff
- litellm>=1.50.0
+ httpx>=0.27.0
  mcp>=1.0.0
  chromadb>=0.5.0
  sentence-transformers>=3.0
```

**注意**：`httpx` 可能已被 `anthropic` SDK 间接安装，但显式声明确保可用。
`sentence-transformers` 暂时保留，等第三步 RAG 双模式改造时再移除。

---

## 六、验证清单

替换完成后，按以下顺序验证：

### 6.1 基础验证
- [ ] `pip uninstall litellm -y`，确认代码中无 `import litellm`
- [ ] 启动 AICraft，选择 DeepSeek 模型（走 Anthropic SDK），发送简单消息 → 能收到流式回复
- [ ] 发送需要 `simple_completion` 的消息（如记忆压缩触发）→ 非流式调用正常

### 6.2 OpenAI 兼容路径
- [ ] 配置一个非 DeepSeek/Claude 的模型（如硅基流动），发送消息 → 走 httpx 路径正常
- [ ] 如果没有其他模型可测，临时把 DeepSeek 模型的 protocol 改为空（不走 Anthropic SDK），测试 httpx 路径

### 6.3 工具调用
- [ ] 开启 MCP 工具，发送需要工具调用的消息 → LLM 返回 tool_call → 工具执行 → 继续回复

### 6.4 Thinking
- [ ] DeepSeek 开启 thinking → 能看到 thinking 增量和 thinking_end（Anthropic SDK 路径，未改动）
- [ ] 关闭 thinking → 无 thinking 输出

### 6.5 搜索与 RAG
- [ ] server-side search → 正常（Anthropic SDK 路径，未改动）
- [ ] RAG 搜索 → 正常（onnx 本地 embedding，未改动）

---

## 七、风险与回退

| 风险 | 影响 | 应对 |
|------|------|------|
| SSE 解析边界情况 | 流式输出异常或卡住 | `json.loads` 加 `try/except` 跳过异常行；httpx read timeout 120s |
| 部分 provider 的 SSE 不是 `data: ` 前缀 | 解析不到 chunk | 主流 provider 都用标准 SSE，暂不需兼容 |
| `reasoning_content` 字段因 provider 不同 | thinking 不显示 | 只影响 OpenAI 兼容路径，Anthropic SDK 路径不受影响 |
| httpx 被 anthropic SDK 间接安装但版本冲突 | 极低风险 | anthropic 用 httpx>=0.23，我们声明>=0.27 无冲突 |

**回退方案**：`requirements.txt` 加回 `litellm>=1.50.0`，代码改回 `import litellm` + `litellm.acompletion`。

---

## 八、关于本地大模型

litellm 替换为 httpx 后，AICraft **天然支持本地大模型**，零额外开发。

所有主流本地大模型方案都暴露 OpenAI 兼容 API：
- **Ollama**：`http://localhost:11434/v1`（api_key 随便填）
- **llama.cpp server**：`http://localhost:8080/v1`
- **LM Studio**：`http://localhost:1234/v1`
- **vLLM**：`http://localhost:8000/v1`

用户只需在模型配置中填写本地 base_url 即可。**本次替换不需要做任何额外工作来"支持"本地模型**。

---

## 九、文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/core/openai_client.py` | **新建** | httpx 实现的 OpenAI 兼容客户端 |
| `src/core/llm.py` | **修改** | `import litellm` → `from src.core.openai_client import acompletion`；所有 `litellm.acompletion` → `openai_completion`；kwargs 中 api_base 确保默认值 |
| `src/core/agent_loop.py` | **修改** | `import litellm` → `from src.core.openai_client import acompletion as openai_completion`；litellm 路径 → openai_completion；_build_llm_kwargs 调整；thinking 读取改为 `delta.reasoning_content` |
| `requirements.txt` | **修改** | `litellm>=1.50.0` → `httpx>=0.27.0` |

**不需要修改的文件**：
- `rag_engine.py` — RAG 仍用 onnx 本地 embedding，不受影响
- `chat_ws.py` — WebSocket 层不受影响
- `embedding.py` — 本次不动，后续 RAG 双模式改造时再处理
- `agent_loop.py` 的 Anthropic SDK 路径 — 完全不变

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
