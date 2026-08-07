"""升级模块 — 解压、替换、重启

一键升级的核心机制：
1. 探测可写目录 → 解压新版到暂存区
2. 复制用户数据到暂存区 → rename 交换新旧目录（原子操作）
3. os._exit 暴力退出 → bat 接管目录交换和重启

Author: Easlie_YHQ
"""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

import httpx

from src.utils.config import USER_DIR, CURRENT_VERSION

logger = logging.getLogger("aicraft.upgrader")

_STAGING_NAME = "AICraft_new"
_BAT_NAME = "_aicraft_upgrade.bat"


def get_staging_dir(target_dir: Path | None = None) -> Path:
    """选择一个可写的解压暂存目录。"""
    if target_dir is None:
        target_dir = USER_DIR
    parent = target_dir.parent
    try:
        test_file = parent / ".aicraft_write_test"
        test_file.touch()
        test_file.unlink()
        return parent / _STAGING_NAME
    except (PermissionError, OSError):
        logger.warning("目标目录同级不可写，回退到系统临时目录")
        return Path(tempfile.gettempdir()) / _STAGING_NAME


async def download_update(
    download_url: str,
    progress_cb=None,
    zip_path: Path | None = None,
) -> Path:
    """下载升级包到临时文件。"""
    if zip_path is None:
        zip_path = Path(tempfile.gettempdir()) / "AICraft_update.zip"

    logger.info("开始下载升级包: %s → %s", download_url, zip_path)

    async with httpx.AsyncClient(timeout=600.0, follow_redirects=True) as client:
        async with client.stream("GET", download_url) as response:
            response.raise_for_status()
            total = None
            cl = response.headers.get("content-length")
            if cl and cl.isdigit():
                total = int(cl)
            downloaded = 0
            with open(zip_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)

    file_size_mb = zip_path.stat().st_size / (1024 * 1024)
    logger.info("下载完成: %.1f MB", file_size_mb)
    return zip_path


def extract_update(zip_path: str | Path, target_dir: Path | None = None) -> dict:
    """解压升级包到暂存目录。"""
    if target_dir is None:
        target_dir = USER_DIR

    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise FileNotFoundError(f"升级包不存在: {zip_path}")

    staging = get_staging_dir(target_dir)

    if staging.exists():
        logger.info("清理旧暂存目录: %s", staging)
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)

    logger.info("解压 %s → %s", zip_path, staging)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(staging)

    staging = _flatten_if_needed(staging)

    exe_path = _find_exe(staging)
    if exe_path is None:
        shutil.rmtree(staging)
        raise ValueError("升级包内未找到 AICraft.exe，请确认 zip 内容完整")

    file_count = sum(1 for _ in staging.rglob("*") if _.is_file())
    new_version = _read_version(staging)

    logger.info("解压完成: %d 个文件, 版本 %s", file_count, new_version or "未知")

    return {
        "staging_dir": str(staging),
        "file_count": file_count,
        "new_version": new_version,
        "current_version": CURRENT_VERSION,
    }


def build_upgrade_bat(
    staging_dir: str | Path,
    target_dir: Path | None = None,
    pid: int | None = None,
) -> str:
    """生成升级 bat 脚本。

    策略：rename 交换目录（原子操作，不碰锁定文件）
    1. 等待旧进程退出
    2. 复制用户数据到暂存区
    3. rename 旧目录 → .bak, rename 暂存区 → 目标
    4. 启动新版
    """
    staging = Path(staging_dir).resolve()
    if target_dir is None:
        target_dir = USER_DIR
    target = target_dir.resolve()

    if staging == target:
        raise ValueError(
            f"暂存目录不能与目标目录相同: {staging}"
        )

    exe_name = "AICraft.exe"
    exe_path = _find_exe(staging)
    if exe_path is not None:
        exe_name = exe_path.name

    if pid:
        wait_line = f"echo Old process PID: {pid}, waiting... && timeout /t 10 /nobreak >nul"
    else:
        wait_line = "timeout /t 10 /nobreak >nul"

    # Use for-loop in bat to iterate user data dirs (avoids %d var expansion issues)
    user_dirs_list = " ".join([
        "config", "chroma_db", "memory", "models",
        "workspace", "roles", "skills", "mcp", "rag",
    ])

    bat = f'''@echo off
setlocal enabledelayedexpansion
echo [AICraft] Upgrading...
echo   Source : {staging}
echo   Target : {target}

:: Wait for old process to fully exit
{wait_line}

:: Copy user data from old to new
echo Copying user data...
for %%d in ({user_dirs_list}) do (
    if exist "{target}\\\%%d" xcopy "{target}\\\%%d" "{staging}\\\%%d" /E /I /Y /Q >nul 2>&1
)

:: Copy .version file
if exist "{target}\\.version" copy /Y "{target}\\.version" "{staging}\\.version" >nul 2>&1

:: Swap directories (rename is atomic on same volume)
:: Must cd away first — cmd.exe has old dir as CWD which blocks rename
echo Swapping directories...
cd /d "%TEMP%"
set "bak={target}.bak.%RANDOM%"
move "{target}" "!bak!" >nul 2>&1
if errorlevel 1 (
    echo [AICraft] FAILED - cannot rename old directory ^(files in use?^)
    echo Staging kept at: {staging}
    pause
    exit /b 1
)
move "{staging}" "{target}" >nul 2>&1
if errorlevel 1 (
    echo [AICraft] FAILED - cannot rename staging to target
    echo Trying to restore old directory...
    move "!bak!" "{target}" >nul 2>&1
    echo Staging kept at: {staging}
    pause
    exit /b 1
)

echo [AICraft] Upgrade OK, starting...
start "" "{target}\\{exe_name}"

:: Clean up old version in background
timeout /t 3 /nobreak >nul
rmdir /s /q "%bak%" 2>nul
exit
'''
    return bat


def execute_upgrade(
    staging_dir: str | Path,
    target_dir: Path | None = None,
    pid: int | None = None,
) -> None:
    """执行升级：写入 bat 脚本 → 分离启动。"""
    staging = Path(staging_dir).resolve()

    if not staging.exists():
        raise FileNotFoundError(f"暂存目录不存在: {staging}")

    bat_path = staging.parent / _BAT_NAME
    bat_content = build_upgrade_bat(staging_dir, target_dir, pid=pid)
    bat_path.write_text(bat_content, encoding="utf-8")

    logger.info("启动升级脚本: %s", bat_path)

    subprocess.Popen(
        ["cmd", "/c", str(bat_path)],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
    )

    logger.info("升级脚本已启动")


# ── 下载任务管理器 ──


class DownloadTaskManager:
    """后台下载+解压任务管理（内存态，前端轮询进度）。"""

    def __init__(self, ttl: float = 300.0):
        self._tasks: dict[str, dict] = {}
        self._ttl = ttl

    def start(self, download_url: str, target_dir: Path | None = None) -> str:
        task_id = uuid.uuid4().hex[:12]
        self._tasks[task_id] = {
            "task_id": task_id,
            "status": "downloading",
            "progress": 0.0,
            "downloaded_bytes": 0,
            "total_bytes": None,
            "message": "开始下载...",
            "error": None,
            "result": None,
            "created_at": time.time(),
        }
        asyncio.create_task(self._run(task_id, download_url, target_dir))
        return task_id

    def get(self, task_id: str) -> dict | None:
        return self._tasks.get(task_id)

    async def _run(self, task_id: str, download_url: str, target_dir: Path | None) -> None:
        state = self._tasks[task_id]
        zip_path = Path(tempfile.gettempdir()) / f"AICraft_update_{task_id}.zip"
        last_update = 0.0

        def on_progress(downloaded: int, total: int | None) -> None:
            nonlocal last_update
            now = time.monotonic()
            if now - last_update < 0.1:
                return
            last_update = now
            state["downloaded_bytes"] = downloaded
            state["total_bytes"] = total
            state["progress"] = (downloaded / total) if total else 0.0
            state["message"] = (
                f"正在下载 {downloaded / 1e6:.1f} MB"
                + (f" / {total / 1e6:.1f} MB" if total else "")
            )

        try:
            await download_update(download_url, progress_cb=on_progress, zip_path=zip_path)

            state["status"] = "extracting"
            state["progress"] = None
            state["message"] = "正在解压新版本..."

            result = await asyncio.to_thread(extract_update, zip_path, target_dir)

            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass

            state["status"] = "done"
            state["progress"] = 1.0
            state["result"] = result
            state["message"] = "下载完成，准备重启"
        except Exception as e:
            logger.exception("下载/解压任务失败: %s", task_id)
            state["status"] = "error"
            state["error"] = str(e)
            state["message"] = f"下载失败: {e}"
            try:
                zip_path.unlink(missing_ok=True)
            except Exception:
                pass
        finally:
            asyncio.create_task(self._schedule_cleanup(task_id))

    async def _schedule_cleanup(self, task_id: str) -> None:
        await asyncio.sleep(self._ttl)
        self._tasks.pop(task_id, None)


download_manager = DownloadTaskManager()


# ── 内部辅助函数 ──


def _flatten_if_needed(staging: Path) -> Path:
    items = list(staging.iterdir())
    if len(items) == 1 and items[0].is_dir():
        subdir = items[0]
        if _find_exe(subdir) or (subdir / "_internal").exists():
            logger.info("检测到包装目录 %s，展平", subdir.name)
            for child in list(subdir.iterdir()):
                shutil.move(str(child), str(staging / child.name))
            subdir.rmdir()
    return staging


def _find_exe(root: Path) -> Path | None:
    exact = root / "AICraft.exe"
    if exact.exists():
        return exact
    for exe in root.glob("*.exe"):
        if "uninstall" not in exe.name.lower():
            return exe
    return None


def _read_version(root: Path) -> str | None:
    version_file = root / ".version"
    if version_file.exists():
        try:
            import json
            data = json.loads(version_file.read_text(encoding="utf-8"))
            return data.get("version")
        except Exception:
            pass
    return None
