---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_RAG_Debug.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782141783482
    ReservedCode2: ""
---
# AICraft RAG 瘦身改造 — 当前状态与问题排查

## 一、改造目标

去掉 litellm（-80MB）和 onnxruntime（-150MB），RAG embedding 从本地模型改为 API 调用，目标打包体积 ~175MB。

## 二、已完成的改动

### 2.1 新建文件

| 文件 | 说明 |
|------|------|
| `src/core/embedding.py` | API Embedding 函数（DeepSeekEmbeddingFunction + OpenAIEmbeddingFunction），替代 onnxruntime 本地推理 |

### 2.2 修改文件

| 文件 | 改动内容 |
|------|---------|
| `requirements.txt` | litellm → httpx，去掉了 sentence-transformers |
| `src/core/rag_engine.py` | ① `_get_embedding_function()` 新增方法，从 `src.core.embedding` 导入 API embedding 类 ② `_index_local()` 的 `get_or_create_collection` 加了 `embedding_function=embed_fn` ③ `warmup()` 改为调 API 验证连通 ④ `search()` 的 `get_collection` 加了 `embedding_function=embed_fn` |

### 2.3 需要确认的文件（可能改了也可能没改）

| 文件 | 需要确认的改动 |
|------|--------------|
| `src/core/llm.py` | 应该已去掉 litellm，改用 httpx 或 openai_client。**需要确认 `chat_completion()` 和 `simple_completion()` 是否已正确替换** |
| `src/core/agent_loop.py` | litellm 路径是否已替换为 httpx/openai_client。**需要确认 `import litellm` 是否已删除，litellm.acompletion 是否已替换** |
| `src/core/openai_client.py` | 瘦身方案要求新建此文件（httpx 实现的 OpenAI 兼容流式客户端）。**需要确认是否存在** |
| `aicraft.spec` | excludes 是否已更新（加 litellm/onnxruntime/onnx） |
| `build_clean.bat` | 依赖列表是否已更新 |

## 三、当前问题

### 问题描述
RAG 检索开关开启后，LLM 回答"没有内置 AICraft 使用指导"，完全没用到 RAG 数据。

### 排查方向

#### 方向 1：DeepSeek Embedding API 不可用

`src/core/embedding.py` 调用的是 `https://api.deepseek.com/v1/embeddings`，模型 `deepseek-embedding`。

**需要验证**：
```python
import httpx
client = httpx.Client(timeout=30.0)
resp = client.post(
    "https://api.deepseek.com/v1/embeddings",
    headers={"Authorization": "Bearer <你的API_KEY>"},
    json={"model": "deepseek-embedding", "input": ["测试文本"]},
)
print(resp.status_code, resp.text[:300])
```

如果返回 404 或其他错误，说明 DeepSeek embedding API 的端点或模型名不对，需要修正 `embedding.py` 中的 `api_base` 或 `model`。

**备选方案**：如果 DeepSeek 确实没有 embedding API（部分资料显示可能有），改用 OpenAI 的 `text-embedding-3-small`（端点 `https://api.openai.com/v1/embeddings`）。AICraft 用户已经有 API Key，在 model_config 中加一个 `embedding_provider: openai` 字段即可切换。

#### 方向 2：索引静默失败

`_index_local()` 内部调用 `self._get_embedding_function()`，如果此方法抛异常（比如 import 失败、API Key 为空、API 不可达），`asyncio.run()` 会吞掉错误。索引按钮点了没反应但没报错。

**需要验证**：
1. 在 `_index_local()` 的 `embed_fn = self._get_embedding_function()` 后加日志，确认 embed_fn 不为 None
2. 如果 embed_fn 为 None（API Key 为空），索引会 fallback 到 chromadb 默认 onnxruntime，然后触发 79MB 模型下载
3. 在 `backend/routers/rag.py` 的 `index_source` 端点加 try/except 打印异常

#### 方向 3：旧索引数据与新 embedding 维度不匹配

`E:\AICraft\chroma_db\chroma.sqlite3` 存在，这是用旧 onnxruntime embedding（all-MiniLM-L6-v2，384维）索引的数据。如果新 API embedding 的向量维度不同（DeepSeek embedding 是 1024 维或 4096 维），`collection.query()` 会返回空结果。

**必须**：删除 `E:\AICraft\chroma_db\` 目录后重新索引。但之前删除后重新索引似乎也没生效，说明索引过程本身就有问题。

#### 方向 4：`_get_embedding_function()` 内部异常

这个方法从 `src.core.llm` 导入 `get_current_model_config()`，如果此时模型配置尚未加载（比如应用启动阶段），会返回空 dict，导致 api_key 为空，返回 None。

## 四、排查建议

1. **先验证 DeepSeek Embedding API 是否可用**（方向1的测试代码）
2. **在 `_index_local()` 加异常日志**，不要让错误被吞掉：
   ```python
   embed_fn = self._get_embedding_function()
   if embed_fn is None:
       print("[RAG] ERROR: _get_embedding_function() 返回 None，无法索引")
       return 0
   ```
3. **在 `backend/routers/rag.py` 的 `index_source` 端点加异常捕获**：
   ```python
   try:
       count = asyncio.run(deps.rag_engine.index_source(source))
   except Exception as e:
       print(f"[RAG] 索引失败: {e}")
       traceback.print_exc()
       raise HTTPException(status_code=500, detail=str(e))
   ```
4. **删除旧 chroma_db 目录后重启，点索引按钮，观察终端输出**

## 五、关键代码路径

```
用户点"索引"按钮
  → POST /api/rag/{name}/index (backend/routers/rag.py)
    → asyncio.run(deps.rag_engine.index_source(source))
      → _index_local()
        → _get_embedding_function()  ← 可能返回 None 或抛异常
          → from src.core.embedding import DeepSeekEmbeddingFunction
          → from src.core.llm import get_current_model_config
        → chromadb.PersistentClient().get_or_create_collection(embedding_function=embed_fn)
        → collection.upsert(documents=chunks, ...)  ← 如果 embed_fn 异常，这里会 fallback 到默认 onnx

用户发消息（RAG 开启）
  → chat_ws.py → deps.rag_engine.search(user_text, 5)
    → _get_embedding_function()  ← 同上
    → client.get_collection(name, embedding_function=embed_fn)
    → collection.query(query_texts=[query])  ← 维度不匹配或 embed_fn 异常则返回空
```

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
