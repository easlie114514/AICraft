"""配置管理模块 - 读写JSON配置文件

支持两种运行模式：
- 开发模式 (python run.py): 所有数据在项目根目录
- 打包模式 (PyInstaller): 出厂数据只读，用户数据在 %APPDATA%/AICraft/

Author: Easlie_YHQ
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# ── 打包模式检测 ──
_FROZEN = getattr(sys, 'frozen', False)

if _FROZEN:
    # 打包模式：出厂只读数据在 exe 内部，用户数据在 AppData
    APP_DIR = Path(sys._MEIPASS) / "data"
    USER_DIR = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'AICraft'
else:
    # 开发模式：所有数据在项目根目录
    APP_DIR = Path(__file__).parent.parent.parent
    USER_DIR = APP_DIR

# 向后兼容：BASE_DIR 指向 APP_DIR
BASE_DIR = APP_DIR

# ── 只读目录（出厂数据，打包后不可写） ──
SKILLS_DIR = APP_DIR / "skills"
ROLES_DIR = APP_DIR / "roles"
RAG_DIR = APP_DIR / "rag"                     # RAG 文档存放目录
DEFAULTS_DIR = APP_DIR / "config" / "defaults"
FRONTEND_DIST = APP_DIR / "frontend" / "dist"
ONNX_MODEL_DIR = APP_DIR / "models" / "onnx" / "all-MiniLM-L6-v2"

# ── 用户可写数据目录 ──
CONFIG_DIR = USER_DIR / "config"
PROFILES_DIR = CONFIG_DIR / "profiles"
MODELS_DIR = USER_DIR / "models"
MEMORY_DIR = USER_DIR / "memory"
CHROMA_DIR = USER_DIR / "chroma_db"
WORKSPACE_DIR = USER_DIR / "workspace"
RAG_STATE_DIR = USER_DIR / "rag"              # RAG 数据源配置（sources.json）

CONVERSATIONS_DIR = MEMORY_DIR / "conversations"
NOTES_DIR = MEMORY_DIR / "project-notes"

# ── 版本号（用于首次启动/升级检测） ──
VERSION_FILE = USER_DIR / ".version"
CURRENT_VERSION = "1.0.0"


def resolve_path(p: str | Path) -> Path:
    """将路径解析为绝对路径，相对路径以 BASE_DIR 为基准。

    - 绝对路径（如 D:\\data\\docs）保持不变
    - 相对路径（如 rag/使用指导）解析为 BASE_DIR / p
    """
    path = Path(p)
    if path.is_absolute():
        return path
    return (BASE_DIR / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    """读取JSON配置文件"""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    """写入JSON配置文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_rag_config():
    """确保 rag_config.json 存在，不存在则从默认模板复制

    不会覆盖已有配置（用户可能已修改）。
    """
    target = CONFIG_DIR / "rag_config.json"
    if not target.exists():
        import shutil
        template = DEFAULTS_DIR / "default_rag_config.json"
        if template.exists():
            shutil.copy2(template, target)
        else:
            # 硬编码兜底
            save_json(target, {
                "embedding_mode": "auto",
                "embedding_api_key": "",
                "embedding_model": "BAAI/bge-large-zh-v1.5",
                "embedding_api_base": "https://api.siliconflow.cn/v1",
            })


def ensure_user_dirs():
    """首次启动：创建用户数据目录结构，从出厂配置复制初始文件

    只补缺失文件，不覆盖已有文件。
    """
    # 确保所有用户目录存在
    for d in [CONFIG_DIR, PROFILES_DIR, MODELS_DIR, MEMORY_DIR,
              CONVERSATIONS_DIR, NOTES_DIR, CHROMA_DIR, WORKSPACE_DIR,
              RAG_STATE_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    # 检查是否需要初始化（.version 文件不存在表示首次启动）
    is_first_run = not VERSION_FILE.exists()

    # MCP / RAG 默认文件不在此复制——由 init_deps() 统一处理首次初始化，
    # 以便正确替换 {workspace_dir} 等占位符后再持久化。

    # model.json 特殊处理：不存在时从模板复制
    profile_model = PROFILES_DIR / "default" / "model.json"
    if not profile_model.exists():
        profile_model.parent.mkdir(parents=True, exist_ok=True)
        save_json(profile_model, {
            "model_id": "",
            "role": "通用助手",
            "web_search": False,
            "rag": False,
            "memory": True,
            "context": {
                "max_history_chars": 50000,
                "memory_compact_enabled": True,
                "memory_compact_trigger": "messages",
                "memory_compact_interval_chars": 8000,
                "memory_compact_interval_msgs": 20,
                "memory_compact_window": 40,
                "memory_compact_max_tokens": 800,
                "memory_merge_threshold": 8,
                "memory_inject_max_chars": 4000,
                "memory_inject_strategy": "latest",
                "cross_session_inject_count": 10,
                "context_budget_enabled": True,
                "context_window_override": 0,
                "output_reserve_ratio": 0.20,
                "budget_alert_threshold": 0.75,
            },
        })

    # 复制 app.json（不存在时）
    app_json = CONFIG_DIR / "app.json"
    if not app_json.exists():
        save_json(app_json, {
            "current_profile": "default",
            "theme": "system",
            "language": "zh-CN",
            "skills_dir": "",
        })

    # 标记版本
    if is_first_run:
        save_json(VERSION_FILE, {"version": CURRENT_VERSION})


def _copy_if_missing(src: Path, dst: Path):
    """如果目标文件不存在，从源复制"""
    import shutil
    if src.exists() and not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


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
    """删除指定模型配置（按 name 字段匹配，支持任意文件名）"""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for f in MODELS_DIR.glob("*.json"):
        cfg = load_json(f)
        if cfg.get("name") == name:
            f.unlink()
            return True
    # 兼容旧行为：按文件名查找
    safe_name = "".join(c for c in name if c.isalnum() or c in "_- ").strip()
    path = MODELS_DIR / f"{safe_name}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def _unset_all_defaults() -> None:
    """取消所有模型的默认标记"""
    for f in MODELS_DIR.glob("*.json"):
        m = load_json(f)
        if m.get("is_default"):
            m["is_default"] = False
            save_json(f, m)


def set_default_model(model_id: str) -> None:
    """设置默认模型"""
    # 取消所有默认
    for f in MODELS_DIR.glob("*.json"):
        m = load_json(f)
        if m.get("is_default"):
            m["is_default"] = False
            save_json(f, m)
    # 设置新默认
    for f in MODELS_DIR.glob("*.json"):
        m = load_json(f)
        if m.get("model_id") == model_id:
            m["is_default"] = True
            save_json(f, m)
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


def get_skills_dir() -> Path:
    """获取配置的SKILLS目录（从app.json读取，未配置则默认 SKILLS_DIR）"""
    app_config = load_json(CONFIG_DIR / "app.json")
    configured = app_config.get("skills_dir", "")
    if configured:
        p = resolve_path(configured)
        if p.exists():
            return p
    return SKILLS_DIR


def set_skills_dir(path: str) -> Path:
    """设置SKILLS目录并持久化到app.json"""
    app_config = load_json(CONFIG_DIR / "app.json")
    app_config["skills_dir"] = path
    save_json(CONFIG_DIR / "app.json", app_config)
    return resolve_path(path)


def get_context_config() -> dict[str, int | bool | str | float]:
    """获取上下文管理配置（记忆压缩间隔、聊天历史长度、预算控制等）

    支持热更新：每次调用都重新读取 profile 配置。
    """
    profile_config = load_profile_config("model")
    ctx = profile_config.get("context", {})
    return {
        # ── 历史裁剪 ──
        "max_history_chars": int(ctx.get("max_history_chars", 50000)),

        # ── 压缩触发 ──
        "memory_compact_enabled": bool(ctx.get("memory_compact_enabled", True)),
        "memory_compact_trigger": str(ctx.get("memory_compact_trigger", "messages")),
        "memory_compact_interval_chars": int(ctx.get("memory_compact_interval_chars", 8000)),
        "memory_compact_interval_msgs": int(ctx.get("memory_compact_interval_msgs", 20)),

        # ── 压缩质量 ──
        "memory_compact_window": int(ctx.get("memory_compact_window", 40)),
        "memory_compact_max_tokens": int(ctx.get("memory_compact_max_tokens", 800)),

        # ── 长期合并 ──
        "memory_merge_threshold": int(ctx.get("memory_merge_threshold", 8)),

        # ── 注入控制 ──
        "memory_inject_max_chars": int(ctx.get("memory_inject_max_chars", 4000)),
        "memory_inject_strategy": str(ctx.get("memory_inject_strategy", "latest")),
        "cross_session_inject_count": int(ctx.get("cross_session_inject_count", 10)),

        # ── 统一预算控制 ──
        "context_budget_enabled": bool(ctx.get("context_budget_enabled", True)),
        "context_window_override": int(ctx.get("context_window_override", 0)),
        "output_reserve_ratio": float(ctx.get("output_reserve_ratio", 0.20)),
        "budget_alert_threshold": float(ctx.get("budget_alert_threshold", 0.75)),
    }
