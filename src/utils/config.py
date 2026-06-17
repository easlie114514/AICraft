"""配置管理模块 - 读写JSON配置文件"""

import json
from pathlib import Path
from typing import Any

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
PROFILES_DIR = CONFIG_DIR / "profiles"
MODELS_DIR = BASE_DIR / "models"
ROLES_DIR = BASE_DIR / "roles"
SKILLS_DIR = BASE_DIR / "skills"
RAG_DIR = BASE_DIR / "rag"
MEMORY_DIR = BASE_DIR / "memory"
CONVERSATIONS_DIR = MEMORY_DIR / "conversations"
NOTES_DIR = MEMORY_DIR / "project-notes"
CHROMA_DIR = BASE_DIR / "chroma_db"


def load_json(path: Path) -> dict[str, Any]:
    """读取JSON配置文件"""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    """写入JSON配置文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_current_profile() -> str:
    """获取当前激活的profile名称"""
    app_config = load_json(CONFIG_DIR / "app.json")
    return app_config.get("current_profile", "default")


def get_profile_dir(profile: str | None = None) -> Path:
    """获取profile目录路径"""
    name = profile or get_current_profile()
    return PROFILES_DIR / name


def load_profile_config(key: str, profile: str | None = None) -> dict[str, Any]:
    """读取profile下的某个配置"""
    profile_dir = get_profile_dir(profile)
    return load_json(profile_dir / f"{key}.json")


def save_profile_config(key: str, data: dict[str, Any], profile: str | None = None) -> None:
    """写入profile下的某个配置"""
    profile_dir = get_profile_dir(profile)
    save_json(profile_dir / f"{key}.json", data)


# ============================================================
# 模型配置管理
# ============================================================

def get_all_model_configs() -> list[dict[str, Any]]:
    """获取所有已配置的模型（从 models/ 目录读取JSON文件）"""
    models = []
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for f in sorted(MODELS_DIR.glob("*.json")):
        cfg = load_json(f)
        if cfg.get("model_id"):
            cfg["_filename"] = f.stem
            models.append(cfg)
    return models


def get_model_config(model_id: str) -> dict[str, Any]:
    """按 model_id 获取模型完整配置"""
    for m in get_all_model_configs():
        if m.get("model_id") == model_id:
            return m
    return {}


def save_model_config(data: dict[str, Any]) -> None:
    """保存模型配置到 models/ 目录（以name为文件名）"""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    name = data.get("name", "unknown").strip()
    if not name:
        raise ValueError("模型名称不能为空")
    # 文件名以 safe name 存储
    safe_name = "".join(c for c in name if c.isalnum() or c in "_- ").strip()
    path = MODELS_DIR / f"{safe_name}.json"
    # 如果 model_id 为空，自动生成
    if not data.get("model_id"):
        provider = data.get("provider", "openai").strip()
        data["model_id"] = f"{provider}/{safe_name.lower().replace(' ', '-')}"
    # 如果已有默认标记，先取消其他模型的默认
    if data.get("is_default"):
        _unset_all_defaults()
    save_json(path, data)


def delete_model_config(name: str) -> bool:
    """删除指定模型配置"""
    safe_name = "".join(c for c in name if c.isalnum() or c in "_- ").strip()
    path = MODELS_DIR / f"{safe_name}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def _unset_all_defaults() -> None:
    """取消所有模型的默认标记"""
    for m in get_all_model_configs():
        if m.get("is_default"):
            safe_name = "".join(c for c in m["name"] if c.isalnum() or c in "_- ").strip()
            m["is_default"] = False
            save_json(MODELS_DIR / f"{safe_name}.json", m)


def set_default_model(model_id: str) -> None:
    """设置默认模型"""
    # 取消所有默认
    for m in get_all_model_configs():
        fn = "".join(c for c in m.get("name", "") if c.isalnum() or c in "_- ").strip()
        if m.get("is_default"):
            m["is_default"] = False
            save_json(MODELS_DIR / f"{fn}.json", m)
    # 设置新默认
    for m in get_all_model_configs():
        if m.get("model_id") == model_id:
            fn = "".join(c for c in m.get("name", "") if c.isalnum() or c in "_- ").strip()
            m["is_default"] = True
            save_json(MODELS_DIR / f"{fn}.json", m)
            # 同时更新 profile 的 model.json
            profile_config = load_profile_config("model")
            profile_config["model_id"] = model_id
            save_profile_config("model", profile_config)
            break


def get_current_model_id() -> str:
    """获取当前profile选中的model_id"""
    profile_config = load_profile_config("model")
    return profile_config.get("model_id", "")


def set_current_model_id(model_id: str) -> None:
    """设置当前profile的model_id"""
    profile_config = load_profile_config("model")
    profile_config["model_id"] = model_id
    save_profile_config("model", profile_config)


def get_current_role_name() -> str:
    """获取当前profile选中的角色名称"""
    profile_config = load_profile_config("model")
    return profile_config.get("role", "通用助手")


def set_current_role_name(role_name: str) -> None:
    """设置当前profile的角色名称"""
    profile_config = load_profile_config("model")
    profile_config["role"] = role_name
    save_profile_config("model", profile_config)
