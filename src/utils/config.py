"""配置管理模块 - 读写JSON配置文件

支持两种运行模式：
- 开发模式 (python run.py): 所有数据在项目根目录
- 打包模式 (PyInstaller onedir): 出厂数据只读（data/ 子目录），用户数据在 exe 同级目录

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
    # 打包模式：出厂只读数据在 data/ 子目录，用户数据在 exe 同级目录
    APP_DIR = Path(sys._MEIPASS) / "data"
    # 便携式设计：数据跟随程序，不散落到 APPDATA
    _exe_dir = Path(sys.executable).parent
    # onedir 模式：_MEIPASS = exe_dir/_internal（如 D:\AICraft\dist\AICraft\_internal）
    # onefile 模式：_MEIPASS 在系统临时目录，与 exe 位置无关
    if _exe_dir != Path(sys._MEIPASS).parent:
        # 非 onedir 模式（如 onefile）：回退到 APPDATA，并打印警告
        import warnings
        warnings.warn(
            f"检测到非 onedir 打包（_MEIPASS={sys._MEIPASS}，exe={sys.executable}），"
            f"用户数据将回退到 APPDATA。建议使用 onedir 打包以确保便携性。"
        )
        USER_DIR = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'AICraft'
    else:
        USER_DIR = _exe_dir
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
USER_ROLES_DIR = USER_DIR / "roles"           # 用户自建角色（打包模式下与出厂角色分离）
USER_SKILLS_DIR = USER_DIR / "skills"         # 用户自建/修改 Skill（打包模式下与出厂 Skill 分离）

CONVERSATIONS_DIR = MEMORY_DIR / "conversations"
NOTES_DIR = MEMORY_DIR / "project-notes"

# ── 版本号（用于首次启动/升级检测） ──
VERSION_FILE = USER_DIR / ".version"
CURRENT_VERSION = "1.0.5"


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


def migrate_from_appdata() -> None:
    """将旧版 APPDATA 用户数据迁移到 exe 同级目录（便携化迁移）

    仅在 frozen 模式下执行。迁移条件：
    - 旧目录 %APPDATA%/AICraft/ 存在
    - 新目录（exe 同级）尚未初始化（无 .version 文件）

    迁移策略：逐项移动，目标已存在则跳过（不覆盖），旧数据保留不删除。
    迁移完成后在旧目录写入 MIGRATED_TO_EXE.txt 说明。
    """
    if not _FROZEN:
        return

    old_dir = Path(os.environ.get('APPDATA', '')) / 'AICraft'
    if not old_dir.exists():
        return

    new_version_file = USER_DIR / ".version"
    if new_version_file.exists():
        # 新目录已初始化，不重复迁移
        return

    # 新目录可能还没创建，先建好
    USER_DIR.mkdir(parents=True, exist_ok=True)

    import shutil
    migrated_items: list[str] = []
    skipped_items: list[str] = []

    for item in old_dir.iterdir():
        target = USER_DIR / item.name
        if target.exists():
            skipped_items.append(item.name)
            continue
        try:
            shutil.move(str(item), str(target))
            migrated_items.append(item.name)
        except OSError as e:
            skipped_items.append(f"{item.name} ({e})")

    # 写迁移记录到旧目录
    record_lines = [
        "AICraft 数据已迁移\n",
        "=" * 40 + "\n",
        f"旧位置：{old_dir}\n",
        f"新位置：{USER_DIR}\n",
        "\n已迁移：\n",
    ]
    for name in migrated_items:
        record_lines.append(f"  - {name}\n")
    if skipped_items:
        record_lines.append("\n跳过（目标已存在或移动失败）：\n")
        for name in skipped_items:
            record_lines.append(f"  - {name}\n")
    record_lines.append(
        "\n如需清理此旧目录，确认新位置数据完好后手动删除即可。\n"
    )

    record_path = old_dir / "MIGRATED_TO_EXE.txt"
    record_path.write_text("".join(record_lines), encoding="utf-8")


def _check_version_upgrade() -> None:
    """检测版本升级，执行必要的迁移逻辑

    比较 .version 文件中存储的版本与 CURRENT_VERSION，
    如果不同则执行升级钩子并更新存储的版本号。
    """
    stored = load_json(VERSION_FILE).get("version", "0.0.0")
    if stored == CURRENT_VERSION:
        return

    # ── 版本升级钩子 ──
    # 在此处按需添加各版本升级逻辑，例如：
    # if stored < "1.2.0":
    #     _migrate_to_1_2_0()

    # 更新存储的版本号
    save_json(VERSION_FILE, {"version": CURRENT_VERSION})


def ensure_user_dirs():
    """首次启动：创建用户数据目录结构，从出厂配置复制初始文件

    只补缺失文件，不覆盖已有文件。
    """
    # 确保所有用户目录存在
    for d in [CONFIG_DIR, PROFILES_DIR, MODELS_DIR, MEMORY_DIR,
              CONVERSATIONS_DIR, NOTES_DIR, CHROMA_DIR, WORKSPACE_DIR,
              RAG_STATE_DIR, USER_ROLES_DIR, USER_SKILLS_DIR]:
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

    # 首次启动：从出厂目录复制 Skill 到用户目录（如用户目录为空）
    if not any(USER_SKILLS_DIR.iterdir()) if USER_SKILLS_DIR.exists() else True:
        _copy_factory_skills()

    # 标记版本 / 版本升级检测
    if is_first_run:
        save_json(VERSION_FILE, {"version": CURRENT_VERSION})
    else:
        _check_version_upgrade()


def _copy_factory_skills() -> None:
    """将出厂 Skill 复制到用户 Skill 目录（首次初始化用）

    只在用户目录为空时执行，不覆盖已有文件。
    开发模式下 SKILLS_DIR == USER_SKILLS_DIR，跳过。
    """
    if not SKILLS_DIR.exists():
        return
    if SKILLS_DIR.resolve() == USER_SKILLS_DIR.resolve():
        return  # 开发模式，无需复制

    import shutil
    USER_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    for src in SKILLS_DIR.iterdir():
        if not src.is_dir() or src.name.startswith("."):
            continue
        dst = USER_SKILLS_DIR / src.name
        if dst.exists():
            continue
        shutil.copytree(str(src), str(dst))


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
    """获取用户 Skill 目录（从app.json读取，未配置则默认 USER_SKILLS_DIR）"""
    app_config = load_json(CONFIG_DIR / "app.json")
    configured = app_config.get("skills_dir", "")
    if configured:
        p = resolve_path(configured)
        if p.exists():
            return p
    return USER_SKILLS_DIR


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

        # ── Agent 循环 ──
        "max_tool_rounds": int(ctx.get("max_tool_rounds", 25)),
    }


# ═══════════════════════════════════════════════════════════
# 全局应用上下文（app.md）
# ═══════════════════════════════════════════════════════════

APP_CONTEXT_PATH = USER_DIR / "app.md"

APP_CONTEXT_DEFAULT = """\
# 应用上下文

## 关于 AICraft

你是 AICraft 内置的 AI 助手。AICraft 是一个桌面 Agent 启动器——像游戏启动器管理 mod 一样管理 AI 的能力模块。它让用户用可视化界面组装 Skill、MCP 工具、本地 RAG 知识库和角色记忆，而不是手写配置或敲 CLI。

核心能力：
- Skill 管理：热插拔式加载 Skill 模块，一键切换
- MCP 工具：文件管理 + 代码执行，Agent 能真正动手
- 本地 RAG：基于 ChromaDB 的私有知识库，数据不出本机
- 角色系统：预设人格模板，保留记忆同时无痕快切
- DeepSeek 一键接入：填入 Key 自动配置，支持深度思考 + 自动路由
- 联网搜索：按权威源分类检索，结果注入上下文
- 上下文预算：6 级优先级裁剪，尽可能帮用户节省 tokens

AICraft 适合不习惯 CLI、更喜欢桌面应用的用户，作为日常和工作中随时可用的 AI 伙伴。

## 项目结构

以下是关键目录及用途，方便你定位文件：

- `roles/`           角色 md 文件（出厂 + 用户自建）
- `skills/`          Skill 模块
- `config/`          应用 & 权限 JSON 配置
- `models/`          模型配置 JSON
- `memory/`          记忆数据 & 对话历史
- `rag/`             RAG 知识库源文档
- `src/core/`        Python 核心逻辑（llm、mcp、rag、memory、agent_loop）
- `src/mcp_servers/` MCP 工具实现（file_manager、code_executor）
- `frontend/`        React 前端
- `workspace/`       工作区（用户文件默认存放处）
- `chroma_db/`       向量数据库文件

## 技术环境

- 操作系统：Windows
- Python 版本：3.11+
- 关键依赖：FastAPI、ChromaDB、litellm、sentence-transformers
- 打包方式：PyInstaller onedir（exe 内无独立 Python，不可 pip install）
- 前端：React 19 + Vite 8 + TailwindCSS 4

## 工作区

- 项目根目录：{PROJECT_ROOT}
- 用户数据目录：{USER_DATA}
- 工作区：{WORKSPACE_DIR}

## 文件权限

以下目录你被授权直接读写（无需用户逐次确认）：

{TRUSTED_PATHS}

以下目录被安全策略禁止访问，绝对不可操作：

{DENIED_PATHS}

## 规则

- 所有相对路径以项目根目录为基准解析
- 读写文件前确认目标路径在信任范围内
- 用户要求操作禁止路径时，明确告知该路径被安全策略限制
- 不知道文件在哪时，先对照上方项目结构定位，不要从根目录盲目扫描
"""


def expand_placeholders(text: str) -> str:
    """展开文本中的占位符为实际路径"""
    from src.core.permission_guard import load_permission_config as _load_perm

    # 先展开路径类占位符，后续填入的权限路径也会被正确展开
    def _expand_path(s: str) -> str:
        return s.replace("{PROJECT_ROOT}", str(USER_DIR)) \
                .replace("{USER_DATA}", str(USER_DIR)) \
                .replace("{WORKSPACE_DIR}", str(WORKSPACE_DIR))

    result = _expand_path(text)

    # 动态占位符：每次实时读取权限配置，并对每条路径展开占位符
    perm = _load_perm()
    trusted = [_expand_path(p) for p in perm.get("trusted_paths", [])]
    denied = [_expand_path(p) for p in perm.get("denied_paths", [])]

    if trusted:
        result = result.replace(
            "{TRUSTED_PATHS}",
            "\n".join(f"- {p}" for p in trusted),
        )
    else:
        result = result.replace("{TRUSTED_PATHS}", "（未配置信任路径）")

    if denied:
        result = result.replace(
            "{DENIED_PATHS}",
            "\n".join(f"- {p}" for p in denied),
        )
    else:
        result = result.replace("{DENIED_PATHS}", "（未配置禁止路径）")

    return result


def load_app_context() -> str:
    """加载 app.md 全局上下文，展开占位符后返回

    文件不存在时返回空字符串。每次调用都重新读取，支持热更新。
    """
    if not APP_CONTEXT_PATH.exists():
        return ""
    text = APP_CONTEXT_PATH.read_text(encoding="utf-8")
    return expand_placeholders(text)
