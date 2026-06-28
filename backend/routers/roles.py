"""角色管理 API — /api/roles/*

创建/修改/删除操作均写入用户角色目录（USER_ROLES_DIR），
出厂角色目录（ROLES_DIR）在打包模式下只读，不可直接修改。

角色存储格式：roles/<name>/role.md（文件夹结构）
情绪画像：roles/<name>/emotion_<key>.png + emotion.json
"""

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.deps import get_deps
from src.utils.config import get_current_role_name, set_current_role_name, ROLES_DIR, USER_ROLES_DIR

router = APIRouter(tags=["roles"])

# 6 种标准情绪
EMOTION_KEYS = {"neutral", "happy", "thinking", "confused", "working", "concerned"}
EMOTION_ORDER = ["neutral", "happy", "thinking", "confused", "working", "concerned"]


def _get_role_folder(name: str) -> Path | None:
    """查找角色文件夹（用户目录优先，出厂目录兜底）"""
    for parent in [USER_ROLES_DIR, ROLES_DIR]:
        folder = parent / name
        if folder.is_dir() and (folder / "role.md").exists():
            return folder
    return None


def _get_emotion_writable(name: str) -> Path:
    """获取情绪画像可写目录（始终在用户目录）"""
    folder = USER_ROLES_DIR / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _get_available_emotions(folder: Path) -> list[str]:
    """扫描 emotion_*.png 获取已配置的情绪列表，按标准顺序返回"""
    available: set[str] = set()
    for f in folder.glob("emotion_*.png"):
        key = f.stem[len("emotion_"):]
        if key in EMOTION_KEYS:
            available.add(key)
    return [k for k in EMOTION_ORDER if k in available]


def _read_emotion_config(folder: Path) -> dict:
    """读取 emotion.json，不存在时返回默认值"""
    path = folder / "emotion.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"enabled": False}


def _write_emotion_config(folder: Path, config: dict) -> None:
    """写入 emotion.json"""
    path = folder / "emotion.json"
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _check_duplicate(name: str, loader) -> None:
    """检查角色名是否已存在（扫描最新状态后判断）"""
    loader.scan()
    if loader.get_role(name):
        raise HTTPException(status_code=400, detail=f"角色「{name}」已存在")


def _write_role_content(name: str, content: str, parent_dir: Path) -> Path:
    """在 parent_dir 下创建/覆盖角色文件夹并写入 role.md"""
    folder = parent_dir / name
    folder.mkdir(parents=True, exist_ok=True)
    prompt = folder / "role.md"
    prompt.write_text(content, encoding="utf-8")
    return folder


def _delete_role_folder(folder: Path) -> None:
    """安全删除角色文件夹（含所有内容）"""
    if folder.is_dir():
        shutil.rmtree(folder)


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
    """创建角色 — 写入用户角色目录（文件夹结构）"""
    name = data.get("name", "").strip()
    content = data.get("content", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="角色名称不能为空")

    deps = get_deps()
    _check_duplicate(name, deps.role_loader)

    writable = deps.role_loader.writable_dir
    writable.mkdir(parents=True, exist_ok=True)
    _write_role_content(name, content, writable)
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

    # 出厂角色不可直接修改，在用户目录下创建同名文件夹覆盖
    if not role.is_user:
        writable = deps.role_loader.writable_dir
        writable.mkdir(parents=True, exist_ok=True)
        _write_role_content(name, content, writable)
    else:
        role.prompt_file.write_text(content, encoding="utf-8")

    deps.role_loader.scan()
    return {"ok": True}


@router.delete("/roles/{name}")
async def delete_role(name: str):
    """删除角色 — 用户角色物理删除，出厂角色软删除（写入 .trash 标记隐藏）"""
    deps = get_deps()
    deps.role_loader.scan()
    role = deps.role_loader.get_role(name)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    if role.is_user:
        # 用户角色：删除整个文件夹
        _delete_role_folder(role.path)
    else:
        # 出厂角色无法物理删除，用软删除标记隐藏
        deps.role_loader.hide_role(name)

    deps.role_loader.scan()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# 情绪画像管理 API
# ═══════════════════════════════════════════════════════════

@router.get("/roles/{name}/emotion")
async def get_emotion_config(name: str):
    """获取角色情绪画像配置 — 合并用户目录和出厂目录"""
    folder = _get_role_folder(name)
    if not folder:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 合并用户目录和出厂目录的数据（用户目录优先）
    enabled = False
    available_set: set[str] = set()
    for parent in [USER_ROLES_DIR, ROLES_DIR]:
        candidate = parent / name
        if candidate.is_dir():
            cfg = _read_emotion_config(candidate)
            if cfg.get("enabled", False):
                enabled = True
            for k in _get_available_emotions(candidate):
                available_set.add(k)

    available = [k for k in EMOTION_ORDER if k in available_set]
    return {"enabled": enabled, "available": available}


@router.put("/roles/{name}/emotion")
async def update_emotion_config(name: str, data: dict):
    """更新角色情绪画像开关"""
    folder = _get_role_folder(name)
    if not folder:
        raise HTTPException(status_code=404, detail="角色不存在")
    enabled = bool(data.get("enabled", False))
    writable = _get_emotion_writable(name)
    config = _read_emotion_config(writable)
    config["enabled"] = enabled
    _write_emotion_config(writable, config)
    return {"ok": True}


@router.get("/roles/{name}/emotion/{key}")
async def get_emotion_image(name: str, key: str):
    """获取角色某情绪的画像图片"""
    if key not in EMOTION_KEYS:
        raise HTTPException(status_code=400, detail=f"无效的情绪 key: {key}")
    # 查找角色文件夹（用户目录优先，出厂目录兜底）
    for parent in [USER_ROLES_DIR, ROLES_DIR]:
        path = parent / name / f"emotion_{key}.png"
        if path.exists():
            return FileResponse(path, media_type="image/png")
    raise HTTPException(status_code=404, detail="画像不存在")


@router.put("/roles/{name}/emotion/{key}")
async def upload_emotion_image(name: str, key: str, file: UploadFile = File(...)):
    """上传角色某情绪的画像（PNG）"""
    if key not in EMOTION_KEYS:
        raise HTTPException(status_code=400, detail=f"无效的情绪 key: {key}")
    # 确保角色存在
    deps = get_deps()
    role = deps.role_loader.get_role(name)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    content = await file.read()
    # 基本校验：PNG 文件头
    if len(content) < 8 or content[:8] != b'\x89PNG\r\n\x1a\n':
        raise HTTPException(status_code=400, detail="仅支持 PNG 格式")

    writable = _get_emotion_writable(name)
    path = writable / f"emotion_{key}.png"
    path.write_bytes(content)
    return {"ok": True}


@router.delete("/roles/{name}/emotion/{key}")
async def delete_emotion_image(name: str, key: str):
    """删除角色某情绪的画像"""
    if key not in EMOTION_KEYS:
        raise HTTPException(status_code=400, detail=f"无效的情绪 key: {key}")
    writable = _get_emotion_writable(name)
    path = writable / f"emotion_{key}.png"
    if path.exists():
        path.unlink()
    # 如果所有帧都被删除，关闭开关
    available = _get_available_emotions(writable)
    if not available:
        config = _read_emotion_config(writable)
        config["enabled"] = False
        _write_emotion_config(writable, config)
    return {"ok": True}
