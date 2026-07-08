"""多项目管理 API — 创建/编辑/删除/激活项目上下文"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from src.utils.config import PROJECTS_CONFIG_PATH

router = APIRouter(tags=["projects"])


class ProjectSave(BaseModel):
    id: str | None = None  # None = 新建
    name: str
    content: str


def _read_projects() -> dict:
    """读取 projects.json"""
    if PROJECTS_CONFIG_PATH.exists():
        try:
            return json.loads(PROJECTS_CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            pass
    return {"active_id": None, "projects": []}


def _write_projects(data: dict):
    """写入 projects.json"""
    PROJECTS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_CONFIG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("/projects")
async def list_projects():
    """列出所有项目"""
    data = _read_projects()
    return {
        "active_id": data.get("active_id"),
        "projects": data.get("projects", []),
    }


@router.post("/projects")
async def save_project(body: ProjectSave):
    """创建或更新项目"""
    data = _read_projects()
    projects: list = data.get("projects", [])
    now = datetime.now().isoformat()

    if body.id:
        # 更新已有项目
        for p in projects:
            if p.get("id") == body.id:
                p["name"] = body.name
                p["content"] = body.content
                p["updated_at"] = now
                _write_projects(data)
                return {"ok": True, "id": body.id}
        # id 没找到，视为新建
        return {"ok": False, "error": "项目不存在"}
    else:
        # 新建
        new_id = f"proj_{uuid.uuid4().hex[:8]}"
        projects.append({
            "id": new_id,
            "name": body.name,
            "content": body.content,
            "created_at": now,
            "updated_at": now,
        })
        _write_projects(data)
        return {"ok": True, "id": new_id}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    """删除项目"""
    data = _read_projects()
    projects: list = data.get("projects", [])
    before = len(projects)
    data["projects"] = [p for p in projects if p.get("id") != project_id]
    if data.get("active_id") == project_id:
        data["active_id"] = None
    if len(data["projects"]) == before:
        return {"ok": False, "error": "项目不存在"}
    _write_projects(data)
    return {"ok": True}


@router.put("/projects/{project_id}/activate")
async def activate_project(project_id: str):
    """激活一个项目作为当前上下文"""
    data = _read_projects()
    projects: list = data.get("projects", [])
    if not any(p.get("id") == project_id for p in projects):
        return {"ok": False, "error": "项目不存在"}
    data["active_id"] = project_id
    _write_projects(data)
    return {"ok": True}


@router.put("/projects/deactivate")
async def deactivate_project():
    """取消激活当前项目"""
    data = _read_projects()
    data["active_id"] = None
    _write_projects(data)
    return {"ok": True}
