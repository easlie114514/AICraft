---
AIGC:
    Label: "1"
    ContentProducer: 001191110102MACQD9K64018705
    ProduceID: 7625823129042141450-data_volume/files/所有对话/主对话/AICraft_RAG_Patch.md
    ReservedCode1: ""
    ContentPropagator: 001191110102MACQD9K64028705
    PropagateID: 837183881094343#1782193686342
    ReservedCode2: ""
---
# AICraft 本地RAG补丁化 — Claude Code 实现指令

## 任务目标

将本地RAG的onnx embedding拆为可选补丁。未安装补丁时：
- RAG页面正常显示，embedding模式只有 `api` 可选（`local` 和 `auto` 灰掉）
- 其余6个页面零影响
- chromadb 仍是必要依赖（用于向量存储），但不再需要 sentence-transformers 和 onnxruntime

安装补丁后：
- embedding模式多出 `local` 和 `auto` 选项
- 可在无网络时用本地onnx做embedding

---

## 1. 修改 `requirements.txt`

```
# 删掉这一行：
sentence-transformers>=3.0

# chromadb 保留（向量存储必须）
# chromadb 默认会拉 onnxruntime 作为可选依赖，需要在打包时排除
```

---

## 2. 修改 `src/core/embedding.py`

### 2.1 `get_embedding_function` 增加本地补丁可用性检测

```python
def is_local_embedding_available() -> bool:
    """检测本地 onnx embedding 补丁是否已安装"""
    try:
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def get_embedding_function(mode: str = "auto", api_key: str = "") -> EmbeddingFunction | None:
    # 如果 mode 是 local 或 auto（无key），但本地补丁未安装 → 报错
    if mode == "local":
        if not is_local_embedding_available():
            raise ValueError(
                "本地 Embedding 补丁未安装。请运行: pip install onnxruntime sentence-transformers"
            )
        return None  # ChromaDB 使用默认 onnx

    if mode == "api":
        if not api_key:
            raise ValueError("API 模式需要提供硅基流动 API Key")
        return SiliconFlowEmbeddingFunction(api_key=api_key)

    # auto 模式
    if api_key:
        return SiliconFlowEmbeddingFunction(api_key=api_key)
    # 无 key，尝试本地
    if is_local_embedding_available():
        return None
    # 既没 key 也没补丁
    raise ValueError(
        "无可用 Embedding：未配置硅基流动 API Key，且本地 Embedding 补丁未安装。"
        "请在 RAG 设置页配置 API Key，或运行: pip install onnxruntime sentence-transformers"
    )
```

### 2.2 `SiliconFlowEmbeddingFunction` 加关闭方法

```python
class SiliconFlowEmbeddingFunction(EmbeddingFunction):
    # ... 现有代码不变 ...

    def close(self):
        """关闭 httpx 客户端"""
        if hasattr(self, '_client') and self._client:
            self._client.close()

    def __del__(self):
        self.close()
```

---

## 3. 修改 `src/core/rag_engine.py`

### 3.1 `_get_embed_fn` 增加异常保护

```python
def _get_embed_fn(self):
    """根据配置获取 embedding 函数，失败返回 None 并打印警告"""
    try:
        config = self._get_rag_config()
        mode = config.get("embedding_mode", "auto")
        api_key = config.get("embedding_api_key", "")
        return get_embedding_function(mode=mode, api_key=api_key)
    except ValueError as e:
        print(f"[RAG] Embedding 不可用: {e}")
        return None
    except Exception as e:
        print(f"[RAG] Embedding 初始化异常: {type(e).__name__}: {e}")
        return None
```

### 3.2 `warmup` 增加本地补丁可用性检查

```python
async def warmup(self) -> bool:
    """预热：验证 embedding 可用"""
    try:
        embed_fn = self._get_embed_fn()
        if embed_fn is not None:
            # API 模式：同步调用，需放线程池
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, embed_fn, ["warmup"])
            return len(result) > 0 and len(result[0]) > 0
        else:
            # 本地 onnx 模式：需要补丁
            from src.core.embedding import is_local_embedding_available
            if not is_local_embedding_available():
                print("[RAG] 本地 Embedding 补丁未安装，RAG 仅支持 API 模式")
                return False
            import chromadb
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            collection = client.get_or_create_collection(
                name="warmup_test",
                metadata={"hnsw:space": "cosine"},
            )
            collection.upsert(documents=["warmup"], ids=["warmup_1"])
            client.delete_collection("warmup_test")
            return True
    except Exception as e:
        print(f"[RAG] warmup 失败: {type(e).__name__}: {e}")
        return False
```

### 3.3 `search` 增加无 embedding 时的降级

在 `search()` 方法开头加检查：

```python
def search(self, query: str, top_k: int = 5) -> list[str]:
    """检索相关文档片段"""
    try:
        embed_fn = self._get_embed_fn()
        if embed_fn is None:
            # 没有可用 embedding 函数 → 检查是否因为补丁未装
            from src.core.embedding import is_local_embedding_available
            config = self._get_rag_config()
            mode = config.get("embedding_mode", "auto")
            if mode == "local" and not is_local_embedding_available():
                print("[RAG] 本地 Embedding 补丁未安装，无法检索")
                return []
            # None 是合法值（ChromaDB 默认 onnx），继续
        # ... 后续代码不变 ...
```

---

## 4. 后端新增补丁状态 API

在 `backend/routers/rag.py` 新增：

```python
@router.get("/rag/patch-status")
async def rag_patch_status():
    """检测本地 Embedding 补丁是否已安装"""
    try:
        from src.core.embedding import is_local_embedding_available
        available = is_local_embedding_available()
    except Exception:
        available = False
    return {"local_embedding_available": available}
```

---

## 5. 前端修改

### 5.1 RAG 页面 embedding 模式选项动态化

`frontend/src/pages/RAGPage.tsx` 修改：

**新增状态和加载逻辑：**

```tsx
const [localPatchAvailable, setLocalPatchAvailable] = useState(false)

// 在 loadRagConfig 里加：
api.get<{ local_embedding_available: boolean }>('/rag/patch-status').then((data) => {
  setLocalPatchAvailable(data.local_embedding_available)
}).catch(() => {})
```

**模式选择下拉框：**

- `api` — 始终可选
- `auto` — 仅 localPatchAvailable 时可选，否则灰掉并显示"需安装本地补丁"
- `local` — 仅 localPatchAvailable 时可选，否则灰掉并显示"需安装本地补丁"

**如果 localPatchAvailable 为 false 且当前模式是 local/auto：**
- 自动切到 `api`
- 显示提示："本地 Embedding 补丁未安装，当前仅支持 API 模式。安装补丁: pip install onnxruntime sentence-transformers"

### 5.2 RAG 页面空状态优化

当没有任何数据源时，显示引导卡片：

```
📚 RAG 知识库

给 AI 喂资料，让它从你的文档中找到答案。

[添加数据源]

💡 支持 txt/md/py/json/csv/html/xml/docx/pdf 格式
💡 推荐先用硅基流动免费 API 做 Embedding（设置页配置）
```

---

## 6. 新建补丁安装脚本 `scripts/install_rag_patch.py`

```python
"""AICraft 本地 RAG Embedding 补丁安装器

安装 onnxruntime + sentence-transformers，启用本地 RAG embedding。
安装后 RAG 页面的 '本地' 和 '自动' 模式可用。
"""

import subprocess
import sys

def main():
    print("AICraft 本地 RAG Embedding 补丁安装器")
    print("=" * 40)
    print()
    print("即将安装以下依赖：")
    print("  - onnxruntime (约 80MB)")
    print("  - sentence-transformers")
    print()

    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "onnxruntime", "sentence-transformers>=3.0"
        ])
        print()
        print("✅ 补丁安装成功！")
        print("请重启 AICraft，RAG 页面将显示 '本地' 和 '自动' 模式选项。")
    except subprocess.CalledProcessError:
        print()
        print("❌ 安装失败，请检查网络连接和 Python 环境。")

if __name__ == "__main__":
    main()
```

---

## 7. 新建补丁卸载脚本 `scripts/uninstall_rag_patch.py`

```python
"""AICraft 本地 RAG Embedding 补丁卸载器"""

import subprocess
import sys

def main():
    print("AICraft 本地 RAG Embedding 补丁卸载器")
    print("=" * 40)
    print()
    print("即将卸载以下依赖：")
    print("  - onnxruntime")
    print("  - sentence-transformers")
    print()
    print("⚠️ 卸载后 RAG 仅支持 API 模式（需联网 + 硅基流动 Key）")
    print()

    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "uninstall", "-y",
            "onnxruntime", "sentence-transformers"
        ])
        print()
        print("✅ 补丁已卸载。请重启 AICraft。")
    except subprocess.CalledProcessError:
        print()
        print("❌ 卸载失败。")

if __name__ == "__main__":
    main()
```

---

## 8. `.gitignore` 新增

```
config/rag_config.json
```

**同时处理已提交的敏感文件：**

```bash
# 从 git 追踪中移除（不删本地文件）
git rm --cached config/rag_config.json
git commit -m "chore: 从版本控制中移除 rag_config.json（含API Key）"
```

然后在 `config/defaults/` 下新建 `default_rag_config.json`（不含 Key）：

```json
{
  "embedding_mode": "auto",
  "embedding_api_key": "",
  "embedding_model": "BAAI/bge-large-zh-v1.5",
  "embedding_api_base": "https://api.siliconflow.cn/v1"
}
```

修改 `src/utils/config.py`：`rag_config.json` 不存在时，从 `config/defaults/default_rag_config.json` 复制一份。

```python
# 在 RAGEngine._get_rag_config 或 config.py 中
def ensure_rag_config():
    """确保 rag_config.json 存在，不存在则从默认模板复制"""
    target = CONFIG_DIR / "rag_config.json"
    if not target.exists():
        import shutil
        template = DEFAULTS_DIR / "default_rag_config.json"
        if template.exists():
            shutil.copy2(template, target)
        else:
            # 硬编码兜底
            save_json(target, {
                "embedding_mode": "auto",
                "embedding_api_key": "",
                "embedding_model": "BAAI/bge-large-zh-v1.5",
                "embedding_api_base": "https://api.siliconflow.cn/v1",
            })
```

在 `deps.py` 的 `init_deps()` 中，`rag.load_sources()` 之前调用 `ensure_rag_config()`。

---

## 9. 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `requirements.txt` | 修改 | 删除 sentence-transformers |
| `src/core/embedding.py` | 修改 | 新增 is_local_embedding_available()、get_embedding_function 增加 ValueError、SiliconFlowEmbeddingFunction 加 close/__del__ |
| `src/core/rag_engine.py` | 修改 | _get_embed_fn 加异常保护、warmup 加补丁检测+线程池、search 加降级 |
| `backend/routers/rag.py` | 修改 | 新增 GET /rag/patch-status |
| `frontend/src/pages/RAGPage.tsx` | 修改 | 模式选项动态化、补丁未装时灰掉 local/auto、空状态引导 |
| `scripts/install_rag_patch.py` | 新建 | 补丁安装脚本 |
| `scripts/uninstall_rag_patch.py` | 新建 | 补丁卸载脚本 |
| `config/defaults/default_rag_config.json` | 新建 | 不含 Key 的默认配置模板 |
| `src/utils/config.py` | 修改 | 新增 ensure_rag_config() |
| `backend/deps.py` | 修改 | init_deps() 中调用 ensure_rag_config() |
| `.gitignore` | 修改 | 新增 config/rag_config.json |

---

> 本内容由 Coze AI 生成，请遵循相关法律法规及《人工智能生成合成内容标识办法》使用与传播。
