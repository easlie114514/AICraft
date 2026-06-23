"""记忆管理 API — /api/memory/*"""

import asyncio
from fastapi import APIRouter, HTTPException

from backend.deps import get_deps
from src.core.chat_history import (
    list_conversations,
    load_conversation,
    delete_conversation,
)
from src.utils.config import get_context_config, save_profile_config, load_profile_config

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
    """列出记忆片段（compact + 长期记忆）"""
    deps = get_deps()
    notes = deps.memory_manager.list_notes()
    return notes


@router.delete("/memory/notes/{filename}")
async def delete_note(filename: str):
    """删除指定记忆片段"""
    deps = get_deps()
    ok = deps.memory_manager.delete_note(filename)
    if not ok:
        raise HTTPException(status_code=404, detail="文件不存在或不允许删除")
    return {"ok": True}


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


# ── 新增：记忆统计 ──

@router.get("/memory/stats")
async def get_memory_stats():
    """获取记忆系统统计（compact数/长期记忆大小/总字符数）"""
    deps = get_deps()
    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, deps.memory_manager.get_memory_stats)
    return stats


# ── 新增：手动触发合并 ──

@router.post("/memory/merge")
async def trigger_memory_merge():
    """手动触发记忆合并（compact → long_term_memory）"""
    deps = get_deps()
    from src.core.model_selector import select_model_for_task
    from src.core.llm import get_current_model_config

    model_config = get_current_model_config()
    if not model_config or not model_config.get("model_id"):
        raise HTTPException(status_code=400, detail="未配置模型，请先在模型页添加API配置")

    compact_model = select_model_for_task("memory_compact", model_config)
    path = await deps.memory_manager.merge_compacts(compact_model)
    if path:
        return {"ok": True, "path": path, "message": f"已将片段合并为长期记忆"}
    else:
        return {"ok": False, "message": "没有可合并的片段或合并失败"}


# ── 新增：记忆配置读写 ──

@router.get("/memory/config")
async def get_memory_config():
    """获取当前记忆配置"""
    return get_context_config()


@router.put("/memory/config")
async def update_memory_config(data: dict):
    """更新记忆配置（写入 profile model.json context 字段）"""
    profile_config = load_profile_config("model")
    ctx = profile_config.get("context", {})

    # 只更新合法的记忆配置字段
    allowed_keys = {
        "max_history_chars", "memory_compact_enabled", "memory_compact_trigger",
        "memory_compact_interval_chars", "memory_compact_interval_msgs",
        "memory_compact_window", "memory_compact_max_tokens",
        "memory_merge_threshold", "memory_inject_max_chars",
        "memory_inject_strategy", "cross_session_inject_count",
        "context_budget_enabled", "context_window_override",
        "output_reserve_ratio", "budget_alert_threshold",
    }
    for k, v in data.items():
        if k in allowed_keys:
            ctx[k] = v

    profile_config["context"] = ctx
    save_profile_config("model", profile_config)
    return {"ok": True, "config": get_context_config()}
