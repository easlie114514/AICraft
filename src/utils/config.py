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
