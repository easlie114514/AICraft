"""网络搜索 API — /api/search"""

import asyncio
from fastapi import APIRouter

from src.core.web_search import web_search, format_search_results

router = APIRouter(tags=["search"])


@router.post("/search")
async def web_search_api(data: dict):
    """执行网络搜索"""
    query = data.get("query", "")
    max_results = data.get("max_results", 5)
    if not query:
        return {"results": [], "formatted": ""}
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, web_search, query, max_results)
    formatted = format_search_results(results)
    return {"results": results, "formatted": formatted}
