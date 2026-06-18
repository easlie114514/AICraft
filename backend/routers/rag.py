"""RAG 数据源管理 API — /api/rag/*"""

import asyncio
from fastapi import APIRouter, HTTPException

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
