"""技能管理 API — /api/skills/*"""

import os
import subprocess
import sys
from fastapi import APIRouter

from backend.deps import get_deps

router = APIRouter(tags=["skills"])


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


@router.put("/skills/{name}/toggle")
async def toggle_skill(name: str, data: dict):
    """启用/禁用技能"""
    enabled = data.get("enabled", True)
    deps = get_deps()
    deps.skill_loader.toggle(name, enabled)
    return {"ok": True}


@router.post("/skills/{name}/open")
async def open_skill_dir(name: str):
    """在文件管理器中打开技能目录"""
    deps = get_deps()
    for s in deps.skill_loader.skills:
        if s.name == name:
            path = str(s.path)
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
            return {"ok": True}
    return {"ok": False, "detail": "技能不存在"}
