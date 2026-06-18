"""记忆管理 API — /api/memory/*"""

import asyncio
from fastapi import APIRouter, HTTPException

from backend.deps import get_deps
from src.core.chat_history import (
    list_conversations,
    load_conversation,
    delete_conversation,
)

router = APIRouter(tags=["memory"])


@router.get("/memory/conversations")
async def get_conversations():
    """列出所有对话"""
    convs = list_conversations()
    return [
        {
            "id": c.get("id"),
            "created": c.get("created", ""),
            "model": c.get("model", ""),
            "role": c.get("role", ""),
            "message_count": c.get("message_count", 0),
        }
        for c in convs
    ]


@router.get("/memory/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """获取某个对话的详细内容"""
    conv = load_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv


@router.delete("/memory/conversations/{conv_id}")
async def remove_conversation(conv_id: str):
    """删除对话"""
    ok = delete_conversation(conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="对话不存在")
    return {"ok": True}


@router.get("/memory/notes")
async def list_notes():
    """列出项目笔记"""
    deps = get_deps()
    notes = deps.memory_manager.list_notes()
    return notes


@router.post("/memory/search")
async def search_memory(data: dict):
    """搜索记忆（使用 RAG 引擎）"""
    query = data.get("query", "")
    top_k = data.get("top_k", 5)
    if not query:
        return {"results": []}
    deps = get_deps()
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, deps.memory_manager.search_memory, query, top_k)
    return {"results": results}
