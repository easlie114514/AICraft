---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_SiliconFlow_Embedding.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782180519709
    ReservedCode2: ""
---
# AICraft 硅基流动 Embedding 接入 — Claude Code 实现指令

## 任务目标

在 RAG 中新增硅基流动(SiliconFlow)免费 Embedding API 支持，与现有 onnx 本地 embedding 并存，用户可切换。

---

## 1. 新建 `src/core/embedding.py`

```python
"""Embedding 函数 — 支持 SiliconFlow API 和本地 onnx 两种模式"""

import httpx
from chromadb.api.types import EmbeddingFunction


class SiliconFlowEmbeddingFunction(EmbeddingFunction):
    """通过硅基流动 API 生成向量"""

    def __init__(
        self,
        api_key: str,
        model: str = "BAAI/bge-large-zh-v1.5",
        api_base: str = "https://api.siliconflow.cn/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base.rstrip("/")
        self._client = httpx.Client(timeout=60.0)

    def __call__(self, input: list[str]) -> list[list[float]]:
        batch_size = 64
        all_embeddings: list[list[float]] = []
        for i in range(0, len(input), batch_size):
            batch = input[i : i + batch_size]
            try:
                resp = self._client.post(
                    f"{self.api_base}/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "input": batch},
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                data.sort(key=lambda x: x["index"])
                all_embeddings.extend([d["embedding"] for d in data])
            except httpx.HTTPStatusError as e:
                print(f"[Embedding] API 错误: {e.response.status_code} {e.response.text[:200]}")
                raise
            except Exception as e:
                print(f"[Embedding] 请求异常: {type(e).__name__}: {e}")
                raise
        return all_embeddings


def get_embedding_function(mode: str = "auto", api_key: str = "") -> EmbeddingFunction | None:
    """获取 embedding 函数
    
    mode="api" → 强制硅基流动API（需api_key）
    mode="local" → 本地onnx（返回None，ChromaDB用默认）
    mode="auto" → 有key用API，否则本地
    """
    if mode == "api":
        if not api_key:
            raise ValueError("API 模式需要提供硅基流动 API Key")
        return SiliconFlowEmbeddingFunction(api_key=api_key)
    if mode == "local":
        return None
    # auto
    if api_key:
        return SiliconFlowEmbeddingFunction(api_key=api_key)
    return None
```

---

## 2. 新建 `config/rag_config.json`

```json
{
  "embedding_mode": "auto",
  "embedding_api_key": "",
  "embedding_model": "BAAI/bge-large-zh-v1.5",
  "embedding_api_base": "https://api.siliconflow.cn/v1"
}
```

字段说明：
- `embedding_mode`: `auto`（有Key用API否则本地）/ `api`（强制API）/ `local`（强制本地onnx）
- `embedding_api_key`: 硅基流动 API Key，空=未配置
- `embedding_model`: 默认 `BAAI/bge-large-zh-v1.5`（中文，1024维，免费）
- `embedding_api_base`: 默认 `https://api.siliconflow.cn/v1`

---

## 3. 修改 `src/core/rag_engine.py`

### 3.1 顶部新增 import

```python
from src.core.embedding import get_embedding_function
```

### 3.2 RAGEngine 类新增两个方法

```python
def _get_rag_config(self) -> dict:
    """读取 RAG 配置"""
    from src.utils.config import load_json, CONFIG_DIR
    return load_json(CONFIG_DIR / "rag_config.json")

def _get_embed_fn(self) -> EmbeddingFunction | None:
    """根据配置获取 embedding 函数"""
    config = self._get_rag_config()
    mode = config.get("embedding_mode", "auto")
    api_key = config.get("embedding_api_key", "")
    return get_embedding_function(mode=mode, api_key=api_key)
```

### 3.3 修改 6 处 get_or_create_collection / get_collection 调用

**所有 ChromaDB collection 操作都要传 `embedding_function`**，具体位置：

**(1) `_index_local()` 中的 `get_or_create_collection`**

```python
# 原：
collection = client.get_or_create_collection(
    name=f"rag_{_safe_collection_name(source.name)}",
    metadata={"hnsw:space": "cosine"}
)
# 改为：
embed_fn = self._get_embed_fn()
collection = client.get_or_create_collection(
    name=f"rag_{_safe_collection_name(source.name)}",
    metadata={"hnsw:space": "cosine"},
    embedding_function=embed_fn,
)
```

**(2) `search()` 中的 `get_collection`**

```python
# 原：
collection = client.get_collection(f"rag_{_safe_collection_name(source.name)}")
# 改为：
embed_fn = self._get_embed_fn()
collection = client.get_collection(
    f"rag_{_safe_collection_name(source.name)}",
    embedding_function=embed_fn,
)
```

**(3) `warmup()` 整体替换**

```python
# 原 warmup 改为：
async def warmup(self) -> bool:
    try:
        embed_fn = self._get_embed_fn()
        if embed_fn is not None:
            result = embed_fn(["warmup"])
            return len(result) > 0 and len(result[0]) > 0
        else:
            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            collection = client.get_or_create_collection(
                name="_warmup_test",
                metadata={"hnsw:space": "cosine"},
            )
            collection.upsert(documents=["warmup"], ids=["warmup_1"])
            client.delete_collection("_warmup_test")
            return True
    except Exception as e:
        print(f"[RAG] warmup 失败: {type(e).__name__}: {e}")
        return False
```

**(4) `load_sources()` 中检查 ChromaDB 集合是否为空**

```python
# 原：
col = client.get_collection(
    f"rag_{_safe_collection_name(item.get('name', ''))}"
)
# 改为：
embed_fn = self._get_embed_fn()
get_kwargs = {}
if embed_fn is not None:
    get_kwargs["embedding_function"] = embed_fn
col = client.get_collection(
    f"rag_{_safe_collection_name(item.get('name', ''))}",
    **get_kwargs,
)
```

**(5) `get_chroma_stats()` 中的 `get_collection`**

```python
# 原：
collection = client.get_collection(f"rag_{_safe_collection_name(source.name)}")
# 改为：
embed_fn = self._get_embed_fn()
get_kwargs = {}
if embed_fn is not None:
    get_kwargs["embedding_function"] = embed_fn
collection = client.get_collection(
    f"rag_{_safe_collection_name(source.name)}",
    **get_kwargs,
)
```

**(6) 检查是否有其他 `get_collection` / `get_or_create_collection` 调用遗漏，补齐 embedding_function 参数**

---

## 4. 后端新增 3 个 API 端点

在 `backend/main.py`（或对应的 API 路由文件）中新增：

### GET `/api/rag/config` — 获取 RAG 配置

```python
@app.get("/api/rag/config")
async def get_rag_config():
    from src.utils.config import load_json, CONFIG_DIR
    config = load_json(CONFIG_DIR / "rag_config.json")
    masked_key = ""
    if config.get("embedding_api_key"):
        key = config["embedding_api_key"]
        masked_key = key[:6] + "***" + key[-4:] if len(key) > 10 else "***"
    return {
        "embedding_mode": config.get("embedding_mode", "auto"),
        "embedding_api_key_masked": masked_key,
        "has_api_key": bool(config.get("embedding_api_key")),
        "embedding_model": config.get("embedding_model", "BAAI/bge-large-zh-v1.5"),
        "embedding_api_base": config.get("embedding_api_base", "https://api.siliconflow.cn/v1"),
    }
```

### POST `/api/rag/config` — 更新 RAG 配置

```python
@app.post("/api/rag/config")
async def update_rag_config(data: dict):
    from src.utils.config import load_json, save_json, CONFIG_DIR
    config = load_json(CONFIG_DIR / "rag_config.json")
    if "embedding_mode" in data:
        if data["embedding_mode"] not in ("auto", "api", "local"):
            return {"success": False, "error": "无效的 embedding_mode"}
        config["embedding_mode"] = data["embedding_mode"]
    if "embedding_api_key" in data and data["embedding_api_key"]:
        config["embedding_api_key"] = data["embedding_api_key"]
    if "embedding_model" in data:
        config["embedding_model"] = data["embedding_model"]
    if "embedding_api_base" in data:
        config["embedding_api_base"] = data["embedding_api_base"]
    save_json(CONFIG_DIR / "rag_config.json", config)
    return {"success": True}
```

### POST `/api/rag/test-embedding` — 测试 Embedding 连通性

```python
@app.post("/api/rag/test-embedding")
async def test_embedding(data: dict):
    try:
        from src.core.embedding import SiliconFlowEmbeddingFunction
        api_key = data.get("api_key", "")
        model = data.get("model", "BAAI/bge-large-zh-v1.5")
        api_base = data.get("api_base", "https://api.siliconflow.cn/v1")
        if not api_key:
            return {"success": False, "error": "未提供 API Key"}
        embed_fn = SiliconFlowEmbeddingFunction(api_key=api_key, model=model, api_base=api_base)
        result = embed_fn(["AICraft Embedding 连通性测试"])
        dim = len(result[0]) if result else 0
        return {"success": True, "dimension": dim}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
```

---

## 5. 前端设置页新增 RAG 配置区域

在设置页新增「RAG 配置」区域，包含：

| 字段 | 控件 | 说明 |
|------|------|------|
| Embedding 模式 | 下拉选择 auto/api/local | auto=有Key用API否则本地 |
| 硅基流动 API Key | 密码输入框 + 测试连接按钮 | 免费注册: cloud.siliconflow.cn |
| Embedding 模型 | 下拉选择 | BAAI/bge-large-zh-v1.5（默认）/ BAAI/bge-large-en-v1.5 / BAAI/bge-m3 |
| API 地址 | 文本输入框 | 默认 https://api.siliconflow.cn/v1 |

交互逻辑：
- 选 `local` 时隐藏 API Key 输入框
- 「测试连接」调 POST `/api/rag/test-embedding`，成功显示"✅ 连接成功，维度: 1024"，失败显示错误
- API Key 获取时返回 masked（前6后4），保存时不传 key 字段则保留原值
- 模式切换后提示"需重新索引"，提供「重新索引全部」按钮

---

## 6. 注意事项

- **索引和检索必须用同一个 embedding 函数**：API(1024维) 和本地onnx(384维) 向量不兼容，切换模式后必须重新索引
- **异常不崩溃**：search() 中网络错误/API错误 try/except 返回空列表，日志报错
- **不删除 onnxruntime**：本步只是新增 API 模式，onnx 保留作为回退，第三步才做补丁化
- `requirements.txt` 不需要改（httpx 已有，onnxruntime 保留）

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
