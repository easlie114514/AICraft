"""技能管理 API — /api/skills/*"""

import asyncio
import os
from pathlib import Path
from fastapi import APIRouter

from backend.deps import get_deps
from src.utils.config import get_skills_dir, set_skills_dir

router = APIRouter(tags=["skills"])


def _open_folder_dialog(initial_dir: str) -> str | None:
    """使用 Windows Shell API 打开原生文件夹选择对话框（无需 tkinter，打包后可用）

    在 thread pool 中调用，阻塞等待用户选择。
    """
    if os.name != "nt":
        return None

    try:
        import ctypes
        from ctypes import wintypes

        shell32 = ctypes.windll.shell32
        user32  = ctypes.windll.user32
        ole32   = ctypes.windll.ole32

        # COM 初始化（STA 模式，SHBrowseForFolder 需要）
        hr = ole32.CoInitialize(None)
        if hr < 0:
            return None

        try:
            # ── 回调：初始化时将对话框定位到 initial_dir ──
            BrowseCallbackProc = ctypes.WINFUNCTYPE(
                ctypes.c_int, wintypes.HWND, wintypes.UINT,
                wintypes.LPARAM, wintypes.LPARAM,
            )

            @BrowseCallbackProc
            def _browse_callback(hwnd, msg, _lp, _data):
                # BFFM_INITIALIZED = 1
                if msg == 1 and initial_dir:
                    # BFFM_SETSELECTIONW = 0x00000467
                    user32.SendMessageW(
                        hwnd, 0x00000467,
                        1,  # TRUE: enable + set
                        ctypes.c_wchar_p(initial_dir),
                    )
                return 0

            class BROWSEINFOW(ctypes.Structure):
                _fields_ = [
                    ("hwndOwner",      wintypes.HWND),
                    ("pidlRoot",       ctypes.c_void_p),
                    ("pszDisplayName", ctypes.c_wchar_p),
                    ("lpszTitle",      ctypes.c_wchar_p),
                    ("ulFlags",        wintypes.UINT),
                    ("lpfn",           BrowseCallbackProc),
                    ("lParam",         wintypes.LPARAM),
                    ("iImage",         ctypes.c_int),
                ]

            BIF_RETURNONLYFSDIRS = 0x00000001
            BIF_NEWDIALOGSTYLE  = 0x00000040  # 新版样式（带"新建文件夹"按钮和地址栏）
            BIF_EDITBOX         = 0x00000010  # 显示地址编辑框

            display_buf = ctypes.create_unicode_buffer(260)
            bi = BROWSEINFOW()
            bi.hwndOwner = 0
            bi.pidlRoot = 0
            bi.pszDisplayName = ctypes.cast(display_buf, ctypes.c_wchar_p)
            bi.lpszTitle = "选择 Skills 根目录"
            bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE | BIF_EDITBOX
            bi.lpfn = _browse_callback
            bi.lParam = 0
            bi.iImage = 0

            pidl = shell32.SHBrowseForFolderW(ctypes.byref(bi))

            if pidl:
                result_buf = ctypes.create_unicode_buffer(260)
                shell32.SHGetPathFromIDListW(pidl, result_buf)
                ole32.CoTaskMemFree(pidl)
                path_str = result_buf.value
                if path_str:
                    return str(Path(path_str).resolve())
            return None
        finally:
            ole32.CoUninitialize()
    except Exception:
        return None


@router.get("/skills/browse-dir")
async def browse_skills_dir():
    """打开原生文件夹选择对话框，返回所选路径"""
    initial_dir = str(get_skills_dir())
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _open_folder_dialog, initial_dir)
    if result:
        return {"ok": True, "path": result}
    return {"ok": False, "detail": "未选择目录"}


@router.get("/skills")
async def list_skills():
    """列出所有技能"""
    deps = get_deps()
    skills = deps.skill_loader.scan()
    return [
        {
            "name": s.name,
            "description": s.description,
            "enabled": s.enabled,
            "path": str(s.path),
        }
        for s in skills
    ]


@router.get("/skills/dir")
async def get_dir():
    """获取当前技能根目录"""
    return {"path": str(get_skills_dir())}


@router.put("/skills/dir")
async def set_dir(data: dict):
    """设置技能根目录并重新扫描"""
    path = data.get("path", "").strip()
    if not path:
        return {"ok": False, "detail": "路径不能为空"}
    p = set_skills_dir(path)
    if not p.exists():
        return {"ok": False, "detail": "路径不存在"}
    # 重建 skill_loader 并重新扫描
    deps = get_deps()
    from src.core.skill_loader import SkillLoader
    deps.skill_loader = SkillLoader(skill_dir=p)
    deps.skill_loader.scan()
    return {"ok": True, "path": str(p)}


@router.put("/skills/{name}/toggle")
async def toggle_skill(name: str, data: dict):
    """启用/禁用技能"""
    enabled = data.get("enabled", True)
    deps = get_deps()
    deps.skill_loader.toggle(name, enabled)
    return {"ok": True}
