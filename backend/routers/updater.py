"""更新检查与升级 API — 从 GitHub Raw 获取 latest.json，支持一键升级"""

import logging
import os
import sys
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.utils.config import CURRENT_VERSION
from src.utils.upgrader import download_manager, extract_update, execute_upgrade

logger = logging.getLogger("aicraft.updater")
router = APIRouter(tags=["update"])


class ExtractRequest(BaseModel):
    zip_path: str = ""       # 本地 zip 路径
    download_url: str = ""   # 远程下载地址（从 latest.json 获取）
    target_dir: str = ""     # 升级目标目录（默认 USER_DIR，测试时可指定）


class UpgradeRequest(BaseModel):
    staging_dir: str
    target_dir: str = ""     # 升级目标目录（默认 USER_DIR）


class DownloadStartRequest(BaseModel):
    download_url: str
    target_dir: str = ""     # 升级目标目录（默认 USER_DIR，测试时可指定）


# GitHub Raw 版本文件地址
LATEST_JSON_URL = "https://raw.githubusercontent.com/easlie114514/AICraft/main/latest.json"

# 缓存：避免短时间内多次请求
_cache: dict = {
    "data": None,
    "ts": 0,
}
_CACHE_TTL = 300  # 5 分钟


async def _fetch_latest() -> dict | None:
    """从 GitHub Raw 获取 latest.json，网络不可达时返回 None

    打包模式下优先读取 exe 同级目录的 latest.json（便于离线/测试）。
    """
    import json as _json
    from pathlib import Path as _Path

    # 本地文件优先
    if getattr(sys, 'frozen', False):
        local = _Path(sys.executable).parent / "latest.json"
    else:
        local = _Path(__file__).resolve().parent.parent.parent / "latest.json"
    if local.exists():
        try:
            with open(local, "r", encoding="utf-8") as f:
                logger.info("读取本地 latest.json: %s", local)
                return _json.load(f)
        except Exception:
            pass

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


@router.post("/update/extract")
async def extract_update_package(req: ExtractRequest):
    """下载并解压升级包到暂存目录

    POST /api/update/extract
    Body: {"download_url": "https://github.com/.../AICraft_v1.1.4.zip"}

    如果提供了 download_url 则先下载再解压；
    如果只提供了 zip_path 则直接解压本地文件。

    返回暂存目录路径、文件数、新版版本号，供后续 upgrade 步骤使用。
    """
    try:
        from src.utils.upgrader import download_update

        zip_path = req.zip_path
        target_dir = Path(req.target_dir) if req.target_dir else None

        # 优先从 download_url 下载
        if req.download_url:
            zip_path = str(await download_update(req.download_url))

        if not zip_path:
            raise HTTPException(status_code=400, detail="请提供 download_url 或 zip_path")

        result = extract_update(zip_path, target_dir)

        # 下载的临时 zip 可以在解压后清理
        if req.download_url:
            try:
                Path(zip_path).unlink(missing_ok=True)
            except Exception:
                pass

        return result
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="升级包文件不存在")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        logger.exception("下载升级包失败")
        raise HTTPException(status_code=502, detail=f"下载失败: {e}")
    except Exception as e:
        logger.exception("解压升级包失败")
        raise HTTPException(status_code=500, detail=f"解压失败: {e}")


@router.post("/update/download", status_code=202)
async def start_download(req: DownloadStartRequest):
    """启动后台下载+解压任务，返回 task_id（前端轮询进度）

    POST /api/update/download
    Body: {"download_url": "https://github.com/.../AICraft.zip"}

    返回 {"task_id": "abc123"}，前端轮询 GET /update/download/{task_id}
    """
    if not req.download_url:
        raise HTTPException(status_code=400, detail="download_url 不能为空")
    target_dir = Path(req.target_dir) if req.target_dir else None
    task_id = download_manager.start(req.download_url, target_dir)
    return {"task_id": task_id}


@router.get("/update/download/{task_id}")
async def get_download_progress(task_id: str):
    """查询下载任务进度

    GET /api/update/download/{task_id}

    返回:
    {
      "task_id": "abc",
      "status": "downloading" | "extracting" | "done" | "error",
      "progress": 0.42,
      "downloaded_bytes": 1234,
      "total_bytes": 5678,
      "message": "正在下载 1.2 MB / 5.6 MB",
      "error": null,
      "result": {...}
    }
    """
    state = download_manager.get(task_id)
    if state is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return state


@router.post("/update/upgrade")
async def trigger_upgrade(req: UpgradeRequest):
    """触发升级：写入 bat 脚本并分离启动

    POST /api/update/upgrade
    Body: {"staging_dir": "D:/AICraft_new"}

    调用后 bat 脚本在后台等待旧进程退出，然后 robocopy 覆盖文件并重启。
    前端收到响应后应调用 window.pywebview.api.close() 关闭窗口。
    """
    try:
        target_dir = Path(req.target_dir) if req.target_dir else None
        execute_upgrade(req.staging_dir, target_dir, pid=os.getpid())
        return {"status": "ok", "message": "升级脚本已启动，请关闭窗口"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="暂存目录不存在")
    except Exception as e:
        logger.exception("触发升级失败")
        raise HTTPException(status_code=500, detail=f"升级失败: {e}")
