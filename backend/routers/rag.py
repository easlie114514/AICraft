"""RAG 数据源管理 API — /api/rag/*"""

import asyncio
from fastapi import APIRouter, HTTPException
from src.utils.config import load_json, save_json, CONFIG_DIR

from backend.deps import get_deps

router = APIRouter(tags=["rag"])


@router.get("/rag")
async def list_sources():
    """列出所有 RAG 数据源及其状态"""
    deps = get_deps()
    loop = asyncio.get_event_loop()
    sources = deps.rag_engine.load_sources()
    # get_chroma_stats 内部调用 ChromaDB (SQLite)，是同步阻塞操作
    # 必须放入线程池，否则会阻塞事件循环
    stats = await loop.run_in_executor(None, deps.rag_engine.get_chroma_stats)
    return [
        {
            "name": s.name,
            "path": s.path,
            "source_type": s.source_type,
            "enabled": s.enabled,
            "file_count": s.file_count,
            "indexed": s.indexed,
            "chroma_docs": stats.get(s.name, 0),
        }
        for s in sources
    ]


@router.post("/rag")
async def add_source(data: dict):
    """添加 RAG 数据源"""
    deps = get_deps()
    source = deps.rag_engine.add_source(
        name=data.get("name", ""),
        path=data.get("path", ""),
        source_type=data.get("source_type", "local"),
    )
    return {"ok": True, "name": source.name}


@router.delete("/rag/{name}")
async def remove_source(name: str):
    """删除 RAG 数据源"""
    deps = get_deps()
    deps.rag_engine.remove_source(name)
    return {"ok": True}


@router.put("/rag/{name}/toggle")
async def toggle_source(name: str, data: dict):
    """启用/禁用 RAG 数据源"""
    deps = get_deps()
    deps.rag_engine.toggle_source(name, data.get("enabled", True))
    return {"ok": True}


@router.post("/rag/{name}/index")
def index_source(name: str):
    """索引 RAG 数据源中的文档

    注意：必须使用 def (同步函数) 而非 async def。
    RAGEngine._index_local 虽然声明为 async，但内部全是同步阻塞调用
    (ChromaDB SQLite 读写、文件 I/O)。如果 await 它，会阻塞整个 asyncio
    事件循环，导致 WebSocket 聊天、其他 API 请求全部卡死。
    同步 def 端点由 FastAPI 放入线程池执行，不影响事件循环。
    """
    deps = get_deps()
    source = None
    for s in deps.rag_engine.sources:
        if s.name == name:
            source = s
            break
    if not source:
        raise HTTPException(status_code=404, detail="数据源不存在")
    # 在线程内创建独立 event loop 运行异步的 index_source
    count = asyncio.run(deps.rag_engine.index_source(source))
    return {"ok": True, "file_count": count}


# ═══════════════════════════════════════════════════════════
# RAG Embedding 配置 API
# ═══════════════════════════════════════════════════════════

@router.get("/rag/config")
async def get_rag_config():
    """获取 RAG Embedding 配置"""
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


@router.post("/rag/config")
async def update_rag_config(data: dict):
    """更新 RAG Embedding 配置"""
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


@router.get("/rag/patch-status")
async def rag_patch_status():
    """检测本地 Embedding 补丁是否已安装"""
    try:
        from src.core.embedding import is_local_embedding_available
        available = is_local_embedding_available()
    except Exception:
        available = False
    return {"local_embedding_available": available}


@router.post("/rag/test-embedding")
async def test_embedding(data: dict):
    """测试 Embedding API 连通性"""
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
