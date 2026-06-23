---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_Slim_Down.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782138922714
    ReservedCode2: ""
---
# AICraft 瘦身方案 — 600MB → 175MB

> 目标：去掉 litellm 和 onnxruntime 两个大户，保留 RAG 核心亮点，最终打包 175MB 以内

---

## 一、体积来源分析

| 依赖 | 体积 | 原因 |
|------|------|------|
| onnxruntime | ~150MB | chromadb 默认 embedding 模型的推理引擎 |
| litellm | ~80MB | 多 provider 适配层 + 传递依赖 |
| chromadb | ~40MB | RAG 向量存储 |
| numpy | ~30MB | chromadb 底层数学运算依赖 |
| pywebview | ~20MB | 桌面窗口 |
| Python 运行时 | ~30MB | python313.dll + stdlib |
| 其他（fastapi/pydantic/httpx/anthropic/mcp 等） | ~50MB | 核心业务依赖 |
| **总计** | **~400MB+** | — |

**两大瘦身目标**：
1. **litellm（-80MB）**→ 直接用 httpx + anthropic SDK 调 API
2. **onnxruntime（-150MB）**→ embedding 改 API 调用

---

## 二、改动 1：去掉 litellm

### 2.1 现状

litellm 在项目中有 3 处使用：

| 文件 | 用途 | 调用方式 |
|------|------|---------|
| `src/core/llm.py` → `chat_completion()` | 流式聊天 + 工具调用 | `litellm.acompletion()` |
| `src/core/llm.py` → `simple_completion()` | 非流式简单调用 | `litellm.acompletion()`（非 Anthropic 协议时） |
| `src/core/agent_loop.py` → litellm 路径 | 非 DeepSeek/Claude 模型的 agent 循环 | `litellm.acompletion(**kwargs)` |

### 2.2 替换方案

litellm 本质就是 OpenAI 兼容 API 的客户端封装。AICraft 已有两条路径：
- **Anthropic 协议**（DeepSeek/Claude）→ 已用 `anthropic` SDK 直连，**不走 litellm**
- **OpenAI 兼容协议**（其他模型）→ 这是 litellm 唯一还在用的路径

替换为 `httpx` 直接调 OpenAI 兼容 API：

```python
# 新增文件：src/core/openai_client.py
"""OpenAI 兼容 API 客户端 — 替代 litellm，直接用 httpx 调用"""

import json
import httpx


async def stream_completion(
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
) -> ...:
    """流式调用 OpenAI 兼容 API（SSE 解析）"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST", f"{api_base}/chat/completions",
            headers=headers, json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                chunk = json.loads(data)
                yield chunk


async def simple_completion(
    api_base: str,
    api_key: str,
    model: str,
    messages: list[dict],
    max_tokens: int = 500,
) -> str:
    """非流式简单调用"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{api_base}/chat/completions",
            headers=headers, json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"] or ""
```

### 2.3 需要修改的文件

#### `src/core/llm.py`

```python
# 删除
import litellm

# 改为
from src.core.openai_client import stream_completion, simple_completion as openai_simple
```

`chat_completion()` 函数改造（只展示关键变化）：

```python
async def chat_completion(messages, tools=None, model_config=None, stream=True):
    if model_config is None:
        model_config = get_current_model_config()
    
    api_key = model_config.get("api_key", "")
    api_base = model_config.get("api_base", "")
    model_id = model_config.get("model_id", "")
    
    # ── 所有模型都走 httpx 直调 ──
    # Anthropic 协议的模型（DeepSeek/Claude）走 anthropic SDK（已有实现）
    # 其他模型走 OpenAI 兼容 API
    
    protocol = model_config.get("protocol", "").lower()
    
    if protocol == "anthropic":
        # 已有逻辑，保持不变（用 anthropic SDK）
        ...
    else:
        # 替换 litellm → httpx
        async for chunk in stream_completion(
            api_base=api_base,
            api_key=api_key,
            model=model_id,
            messages=messages,
            tools=tools,
        ):
            # 解析 SSE chunk，yield 统一事件格式
            delta = chunk["choices"][0].get("delta", {})
            if delta.get("content"):
                yield {"type": "text", "content": delta["content"]}
            if delta.get("tool_calls"):
                # 累积 tool_call 增量（复用原有逻辑）
                ...
```

`simple_completion()` 函数改造：

```python
async def simple_completion(model_config, messages, max_tokens=500):
    protocol = model_config.get("protocol", "").lower()
    
    if protocol == "anthropic":
        # 已有逻辑不变
        ...
    else:
        # litellm → httpx
        api_base = model_config.get("api_base", "https://api.openai.com/v1")
        api_key = model_config.get("api_key", "")
        model_id = model_config.get("model_id", "")
        return await openai_simple(api_base, api_key, model_id, messages, max_tokens)
```

#### `src/core/agent_loop.py`

litellm 路径（非 DeepSeek/Claude 模型的 else 分支）改造：

```python
# 删除
import litellm

# 改为
from src.core.openai_client import stream_completion
```

agent_loop 函数内 litellm 路径的 `await litellm.acompletion(**kwargs)` 替换为：

```python
else:
    # ── OpenAI 兼容路径（替代 litellm）──
    api_base = model_config.get("api_base", "https://api.openai.com/v1")
    api_key = model_config.get("api_key", "")
    model_id = model_config.get("model_id", "")
    
    thinking_start_time = None
    full_text = ""
    tool_call_deltas: dict[int, dict[str, str]] = {}

    async for chunk in stream_completion(
        api_base=api_base,
        api_key=api_key,
        model=model_id,
        messages=messages,
        tools=tools,
    ):
        delta = chunk["choices"][0].get("delta", {})
        
        # Thinking（部分模型支持 reasoning_content）
        if thinking_enabled:
            reasoning = delta.get("reasoning_content") or delta.get("thinking")
            if reasoning:
                if thinking_start_time is None:
                    thinking_start_time = time.time()
                yield {"type": "thinking", "content": reasoning}
        
        # 文本增量
        content = delta.get("content")
        if content:
            if thinking_start_time is not None:
                duration_ms = int((time.time() - thinking_start_time) * 1000)
                yield {"type": "thinking_end", "duration_ms": duration_ms}
                thinking_start_time = None
            full_text += content
            yield {"type": "text", "content": content}
        
        # 工具调用增量
        tc_list = delta.get("tool_calls")
        if tc_list:
            if thinking_start_time is not None:
                duration_ms = int((time.time() - thinking_start_time) * 1000)
                yield {"type": "thinking_end", "duration_ms": duration_ms}
                thinking_start_time = None
            for tc in tc_list:
                idx = tc.get("index", 0)
                if idx not in tool_call_deltas:
                    tool_call_deltas[idx] = {
                        "id": tc.get("id", ""),
                        "function_name": "",
                        "function_arguments": "",
                    }
                fn = tc.get("function", {})
                if fn.get("name"):
                    tool_call_deltas[idx]["function_name"] += fn["name"]
                if fn.get("arguments"):
                    tool_call_deltas[idx]["function_arguments"] += fn["arguments"]

    # ── 后续的 tool_call 处理逻辑完全不变 ──
```

**注意**：agent_loop.py 中 litellm 路径后续的工具执行、消息拼接逻辑**完全不需要改**，因为 `tool_call_deltas` 的数据结构和 yield 事件格式与原来一致。

### 2.4 `requirements.txt` 变更

```diff
- litellm>=1.50.0
+ httpx>=0.27.0
  mcp>=1.0.0
```

---

## 三、改动 2：Embedding 改 API 调用

### 3.1 现状

`rag_engine.py` 中 chromadb 使用默认的本地 onnxruntime embedding：

```python
# 当前代码（_index_local / warmup / search）
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client.get_or_create_collection(...)
# 默认使用 onnxruntime 跑 all-MiniLM-L6-v2 → 150MB
```

### 3.2 替换方案

自定义 `embedding_function`，走 DeepSeek Embedding API：

```python
# 新增：src/core/embedding.py
"""API Embedding 函数 — 替代 onnxruntime 本地推理"""

import httpx
from chromadb.api.types import EmbeddingFunction


class DeepSeekEmbeddingFunction(EmbeddingFunction):
    """通过 DeepSeek Embedding API 生成向量，替代本地 onnxruntime"""

    def __init__(self, api_key: str, api_base: str = "https://api.deepseek.com/v1"):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = "deepseek-embedding"  # DeepSeek embedding 模型名
        self._client = httpx.Client(timeout=60.0)

    def __call__(self, input: list[str]) -> list[list[float]]:
        """ChromaDB 会调用这个方法"""
        return self._embed(input)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        # 分批处理（API 限制单次数量）
        batch_size = 64
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = self._client.post(
                f"{self.api_base}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": batch},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            # 按 index 排序确保顺序一致
            data.sort(key=lambda x: x["index"])
            all_embeddings.extend([d["embedding"] for d in data])
        return all_embeddings
```

### 3.3 rag_engine.py 改动

```python
# 新增 import
from src.core.embedding import DeepSeekEmbeddingFunction
from src.utils.config import get_current_model_config


# 新增辅助方法
def _get_embedding_function(self) -> DeepSeekEmbeddingFunction | None:
    """获取当前模型的 embedding 函数"""
    model_config = get_current_model_config()
    api_key = model_config.get("api_key", "")
    api_base = model_config.get("api_base", "")
    
    if not api_key:
        return None
    
    # embedding 用的 API base（默认和聊天模型相同）
    embed_base = api_base or "https://api.deepseek.com/v1"
    
    return DeepSeekEmbeddingFunction(api_key=api_key, api_base=embed_base)
```

所有 `chromadb.PersistentClient()` + `get_or_create_collection` 的地方改为：

```python
# 之前
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = client.get_or_create_collection(name=..., metadata={"hnsw:space": "cosine"})

# 之后
client = chromadb.PersistentClient(path=str(CHROMA_DIR))
embed_fn = self._get_embedding_function()
collection = client.get_or_create_collection(
    name=...,
    metadata={"hnsw:space": "cosine"},
    embedding_function=embed_fn,  # 新增
)
```

涉及 3 处：
1. `_index_local()` — 索引时需要 embedding
2. `warmup()` — 预热测试
3. `search()` — 检索时需要把 query 转向量

**warmup 改造**：去掉 onnxruntime 模型预热逻辑，改为验证 API 可达：

```python
async def warmup(self) -> bool:
    """预热：验证 embedding API 可用"""
    try:
        embed_fn = self._get_embedding_function()
        if embed_fn is None:
            return False
        # 调一次 embedding 验证 API 连通
        result = embed_fn(["warmup"])
        return len(result) > 0
    except Exception:
        return False
```

### 3.4 Embedding 提供者配置

在 models 配置中新增 `embedding_provider` 字段，支持不同 embedding 来源：

```json
// models/dpv4p.json
{
  "model_id": "deepseek/deepseek-chat",
  "provider": "deepseek",
  "api_key": "sk-xxx",
  "api_base": "https://api.deepseek.com",
  "protocol": "anthropic",
  "embedding_provider": "deepseek"  // 新增，默认和 provider 相同
}
```

`_get_embedding_function()` 支持多来源：

```python
def _get_embedding_function(self):
    model_config = get_current_model_config()
    api_key = model_config.get("api_key", "")
    embedding_provider = model_config.get("embedding_provider", "").lower()
    
    if not api_key:
        return None
    
    if embedding_provider == "openai":
        return DeepSeekEmbeddingFunction(
            api_key=api_key,
            api_base="https://api.openai.com/v1",
            model="text-embedding-3-small",
        )
    else:
        # 默认 DeepSeek
        return DeepSeekEmbeddingFunction(
            api_key=api_key,
            api_base="https://api.deepseek.com/v1",
            model="deepseek-embedding",
        )
```

### 3.5 requirements.txt 变更

```diff
  chromadb>=0.5.0
- # onnxruntime 不再需要，chromadb 不会自动拉入
```

**关键**：chromadb 默认会尝试 import onnxruntime，但如果我们提供了自定义 `embedding_function`，它就不会触发本地 embedding 模型加载。需确认 chromadb 在有自定义 embedding function 时不拉入 onnxruntime 依赖。如果 chromadb 的 setup.py 强制依赖 onnxruntime，需要：

```bash
pip install chromadb --no-deps
pip install pydantic pulsar-client tenacity typing-extensions  # 只装 chromadb 真正需要的运行时依赖
```

或者更简单的方案——在 `requirements.txt` 中保留 `chromadb>=0.5.0`，但在 build_clean.bat 的 venv 中先装，然后手动删掉 onnxruntime：

```bat
pip uninstall onnxruntime -y
```

---

## 四、改动 3：PyInstaller spec 更新

### 4.1 aicraft.spec 变更

```python
# excludes 列表更新
excludes = [
    # ── 去掉 litellm ──
    'litellm',
    # ── 去掉本地 embedding ──
    'onnxruntime', 'onnx',
    'sentence_transformers', 'transformers',
    # ── 去掉 torch 及其生态 ──
    'torch', 'torchvision', 'torchaudio',
    # ── 去掉 sklearn/scipy ──
    'sklearn', 'scipy',
    # ── 其他不需要的 ──
    'tkinter', 'test', 'unittest',
    'setuptools', 'pip', 'wheel',
]

# hiddenimports 更新（去掉 litellm，确保 httpx 在）
hiddenimports = [
    'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on',
    'chromadb', 'chromadb.config',
    'httpx',  # 新增（替代 litellm）
    'anthropic',
    'mcp', 'mcp.client', 'mcp.client.stdio',
    'pywebview',
    'fastapi', 'pydantic',
    'websockets',
    'langchain_text_splitters',
]
```

### 4.2 build_clean.bat 更新

```bat
@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================================
echo   AICraft 瘦身版构建 (目标 ~175MB)
echo ============================================================

set "PROJECT=E:\AICraft"
set "VENV=%PROJECT%\.build-venv"
set "DIST=%PROJECT%\dist"

:: 1. 创建干净虚拟环境
if exist "%VENV%" rmdir /s /q "%VENV%"
python -m venv "%VENV%"
call "%VENV%\Scripts\activate.bat"

:: 2. 升级 pip
pip install --upgrade pip

:: 3. 只装核心依赖（不含 litellm/torch/onnxruntime）
pip install ^
    httpx>=0.27.0 ^
    mcp>=1.0.0 ^
    chromadb>=0.5.0 ^
    langchain-text-splitters ^
    PyPDF2 ^
    python-docx ^
    anthropic>=0.100.0 ^
    watchdog ^
    pyperclip ^
    fastapi>=0.115.0 ^
    uvicorn>=0.30.0 ^
    websockets>=13.0 ^
    pywebview>=5.0 ^
    pyinstaller

:: 4. 删掉可能被传递依赖拉入的 onnxruntime
pip uninstall onnxruntime onnx -y 2>nul

:: 5. 编译前端
cd /d "%PROJECT%\frontend"
if not exist dist (
    call npm run build
)

:: 6. PyInstaller 打包
cd /d "%PROJECT%"
pyinstaller aicraft.spec --clean --noconfirm ^
    --distpath "%DIST%" ^
    --workpath "%PROJECT%\build"

echo.
echo ============================================================
echo   完成！产物在 %DIST%\AICraft\
echo ============================================================
```

### 4.3 requirements.txt 最终版

```
httpx>=0.27.0
mcp>=1.0.0
chromadb>=0.5.0
langchain-text-splitters
PyPDF2
python-docx
anthropic>=0.100.0
watchdog
pyperclip
fastapi>=0.115.0
uvicorn>=0.30.0
websockets>=13.0
pywebview>=5.0
```

---

## 五、预期体积

| 组件 | 体积 |
|------|------|
| Python 运行时 | ~30MB |
| chromadb（不含 onnxruntime） | ~15MB |
| numpy | ~30MB |
| anthropic SDK | ~5MB |
| httpx + pydantic | ~10MB |
| FastAPI + uvicorn + websockets | ~10MB |
| pywebview | ~20MB |
| mcp SDK | ~5MB |
| 其他小依赖（watchdog/pyperclip/PyPDF2/python-docx/langchain-text-splitters） | ~20MB |
| 前端 dist/ | ~5MB |
| PyInstaller bootloader + DLL | ~10MB |
| **总计** | **~160MB** |

比 175MB 目标还少，留有余量。

---

## 六、实现顺序

1. **新建 `src/core/openai_client.py`** — httpx 实现的 OpenAI 兼容流式/非流式客户端
2. **新建 `src/core/embedding.py`** — API embedding 函数
3. **修改 `src/core/llm.py`** — 替换 litellm → openai_client
4. **修改 `src/core/agent_loop.py`** — 替换 litellm 路径 → openai_client
5. **修改 `src/core/rag_engine.py`** — embedding_function 改为 API
6. **修改 `requirements.txt`** — litellm → httpx
7. **修改 `aicraft.spec`** — 更新 excludes/hiddenimports
8. **修改 `build_clean.bat`** — 更新依赖列表
9. **venv 打包测试** — 运行 build_clean.bat，验证 exe 可启动

---

## 七、风险与回退

| 风险 | 影响 | 应对 |
|------|------|------|
| chromadb 强制依赖 onnxruntime | 打包时仍被拉入 | build_clean.bat 中 `pip uninstall onnxruntime -y` |
| DeepSeek embedding API 不稳定 | RAG 功能不可用 | 降级为关键词搜索（chromadb 支持 where 过滤），或加 OpenAI embedding 备选 |
| httpx SSE 解析边界情况 | 流式输出异常 | 参考 litellm 的 SSE 解析逻辑补齐边界处理 |
| 部分 OpenAI 兼容模型（非 DeepSeek）API 格式差异 | 非 DeepSeek 模型调不通 | 保留 model_config 中的 api_base/api_key 灵活配置 |

**回退方案**：如果 httpx 方案出问题，只需在 requirements.txt 加回 `litellm>=1.50.0`，代码改回 `litellm.acompletion` 即可恢复。

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
