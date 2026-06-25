"""角色管理 API — /api/roles/*

创建/修改/删除操作均写入用户角色目录（USER_ROLES_DIR），
出厂角色目录（ROLES_DIR）在打包模式下只读，不可直接修改。
"""

from fastapi import APIRouter, HTTPException

from backend.deps import get_deps
from src.utils.config import get_current_role_name, set_current_role_name, USER_ROLES_DIR

router = APIRouter(tags=["roles"])


def _check_duplicate(name: str, loader) -> None:
    """检查角色名是否已存在（扫描最新状态后判断）"""
    loader.scan()
    if loader.get_role(name):
        raise HTTPException(status_code=400, detail=f"角色「{name}」已存在")


@router.get("/roles")
async def list_roles():
    """获取所有角色（含出厂 + 用户自建，同名以用户版为准）"""
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
    """创建角色 — 写入用户角色目录"""
    name = data.get("name", "").strip()
    content = data.get("content", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="角色名称不能为空")

    deps = get_deps()
    _check_duplicate(name, deps.role_loader)

    writable = deps.role_loader.writable_dir
    writable.mkdir(parents=True, exist_ok=True)
    path = writable / f"{name}.md"
    path.write_text(content, encoding="utf-8")
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
    """更新角色内容 — 若为出厂角色则在用户目录创建覆盖副本"""
    deps = get_deps()
    deps.role_loader.scan()
    role = deps.role_loader.get_role(name)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    content = data.get("content", "")

    # 出厂角色不可直接修改，在用户目录下创建同名文件覆盖
    if not role.is_user:
        writable = deps.role_loader.writable_dir
        writable.mkdir(parents=True, exist_ok=True)
        path = writable / f"{name}.md"
        path.write_text(content, encoding="utf-8")
    else:
        role.path.write_text(content, encoding="utf-8")

    deps.role_loader.scan()
    return {"ok": True}


@router.delete("/roles/{name}")
async def delete_role(name: str):
    """删除角色 — 只能删除用户自建角色"""
    deps = get_deps()
    deps.role_loader.scan()
    role = deps.role_loader.get_role(name)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if not role.is_user:
        raise HTTPException(status_code=400, detail="出厂角色不可删除，你可以在用户目录创建同名角色覆盖它")

    role.path.unlink(missing_ok=True)
    deps.role_loader.scan()
    return {"ok": True}
