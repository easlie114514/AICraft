"""角色管理 API — /api/roles/*"""

from fastapi import APIRouter, HTTPException

from backend.deps import get_deps
from src.utils.config import get_current_role_name, set_current_role_name, ROLES_DIR

router = APIRouter(tags=["roles"])


@router.get("/roles")
async def list_roles():
    """获取所有角色"""
    deps = get_deps()
    roles = deps.role_loader.scan()
    current = get_current_role_name()
    return [
        {"name": r.name, "content": r.content, "is_current": r.name == current}
        for r in roles
    ]


@router.get("/roles/current")
async def get_current_role():
    """获取当前选中的角色"""
    return {"name": get_current_role_name()}


@router.put("/roles/current")
async def set_current_role(data: dict):
    """设置当前角色"""
    name = data.get("name", "")
    set_current_role_name(name)
    return {"ok": True}


@router.post("/roles")
async def create_role(data: dict):
    """创建角色（写入 .md 文件）"""
    name = data.get("name", "").strip()
    content = data.get("content", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="角色名称不能为空")
    path = ROLES_DIR / f"{name}.md"
    if path.exists():
        raise HTTPException(status_code=400, detail="角色已存在")
    path.write_text(content, encoding="utf-8")
    deps = get_deps()
    deps.role_loader.scan()
    return {"ok": True}


@router.get("/roles/{name}")
async def get_role(name: str):
    """获取角色内容"""
    deps = get_deps()
    role = deps.role_loader.get_role(name)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    return {"name": role.name, "content": role.content}


@router.put("/roles/{name}")
async def update_role(name: str, data: dict):
    """更新角色内容"""
    path = ROLES_DIR / f"{name}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="角色不存在")
    content = data.get("content", "")
    path.write_text(content, encoding="utf-8")
    deps = get_deps()
    deps.role_loader.scan()
    return {"ok": True}


@router.delete("/roles/{name}")
async def delete_role(name: str):
    """删除角色"""
    path = ROLES_DIR / f"{name}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail="角色不存在")
    path.unlink()
    deps = get_deps()
    deps.role_loader.scan()
    return {"ok": True}
