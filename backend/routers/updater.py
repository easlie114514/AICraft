"""更新检查 API — 从 GitHub Raw 获取 latest.json 比较版本"""

import time

import httpx
from fastapi import APIRouter

from src.utils.config import CURRENT_VERSION

router = APIRouter(tags=["update"])

# GitHub Raw 版本文件地址
LATEST_JSON_URL = "https://raw.githubusercontent.com/easlie114514/AICraft/main/latest.json"

# 缓存：避免短时间内多次请求
_cache: dict = {
    "data": None,
    "ts": 0,
}
_CACHE_TTL = 300  # 5 分钟


async def _fetch_latest() -> dict | None:
    """从 GitHub Raw 获取 latest.json，网络不可达时返回 None"""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(LATEST_JSON_URL)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


@router.get("/update/check")
async def check_update(force: bool = False):
    """检查是否有新版本

    - force=False（默认）：缓存 5 分钟
    - force=True：绕过缓存，立即请求远端

    返回格式：
    {
      "has_update": bool,
      "current_version": str,
      "latest_version": str | None,
      "page_url": str | None,
      "download_url": str | None,
      "notes": str | None,
      "error": str | None   // "network" 表示网络不可达
    }
    """
    now = time.time()

    # 缓存命中（非强制模式）
    if not force and _cache["data"] is not None and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]

    latest = await _fetch_latest()

    if latest is None:
        result = {
            "has_update": False,
            "current_version": CURRENT_VERSION,
            "latest_version": None,
            "page_url": None,
            "download_url": None,
            "notes": None,
            "error": "network",
        }
    else:
        remote_version = latest.get("version", "0.0.0")
        has_update = _version_is_newer(remote_version, CURRENT_VERSION)
        result = {
            "has_update": has_update,
            "current_version": CURRENT_VERSION,
            "latest_version": remote_version,
            "page_url": latest.get("page_url", ""),
            "download_url": latest.get("download_url", ""),
            "notes": latest.get("notes", ""),
            "error": None,
        }

    _cache["data"] = result
    _cache["ts"] = now
    return result


def _version_is_newer(remote: str, local: str) -> bool:
    """比较语义化版本号，remote > local 返回 True"""
    try:
        remote_parts = [int(x) for x in remote.split(".")]
        local_parts = [int(x) for x in local.split(".")]
    except (ValueError, AttributeError):
        return False

    # 补齐长度
    while len(remote_parts) < 3:
        remote_parts.append(0)
    while len(local_parts) < 3:
        local_parts.append(0)

    return remote_parts > local_parts
