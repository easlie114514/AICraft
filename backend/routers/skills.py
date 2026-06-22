"""技能管理 API — /api/skills/*"""

import asyncio
from pathlib import Path
from fastapi import APIRouter

from backend.deps import get_deps
from src.utils.config import get_skills_dir, set_skills_dir

router = APIRouter(tags=["skills"])


def _open_folder_dialog(initial_dir: str) -> str | None:
    """使用 tkinter 打开原生文件夹选择对话框（在 thread pool 中调用）"""
    try:
        from tkinter import Tk, filedialog
        root = Tk()
        root.withdraw()  # 隐藏主窗口
        root.attributes("-topmost", True)  # 置顶
        result = filedialog.askdirectory(
            initialdir=initial_dir,
            title="选择 Skills 根目录"
        )
        root.destroy()
        return str(Path(result).resolve()) if result else None
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
