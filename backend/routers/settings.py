"""应用设置 API — 持久化主题等偏好到 config/app.json"""

import json
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from src.utils.config import APP_CONTEXT_PATH, load_app_context

router = APIRouter(tags=["settings"])

APP_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "app.json"

# 前端主题名称白名单
VALID_THEMES = {"blue", "green", "purple", "orange", "rose", "teal", "amber", "pink", "slate"}


class SettingsUpdate(BaseModel):
    theme: str | None = None
    show_emotion_portrait: bool | None = None
    max_tool_rounds: int | None = None


class AppContextUpdate(BaseModel):
    content: str


def _read_config() -> dict:
    """读取 app.json 配置"""
    if APP_CONFIG_PATH.exists():
        try:
            return json.loads(APP_CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            pass
    return {}


def _write_config(config: dict):
    """写入 app.json 配置"""
    APP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("/settings")
async def get_settings():
    """获取应用设置"""
    config = _read_config()
    return {
        "theme": config.get("theme", "blue"),
        "language": config.get("language", "zh-CN"),
        "show_emotion_portrait": config.get("show_emotion_portrait", True),
        "max_tool_rounds": config.get("max_tool_rounds", 25),
    }


@router.put("/settings")
async def update_settings(body: SettingsUpdate):
    """更新应用设置（目前支持 theme）"""
    config = _read_config()
    if body.theme is not None:
        theme = body.theme.strip()
        if theme not in VALID_THEMES:
            return {"ok": False, "error": f"无效主题: {theme}"}
        config["theme"] = theme
    if body.show_emotion_portrait is not None:
        config["show_emotion_portrait"] = body.show_emotion_portrait
    if body.max_tool_rounds is not None:
        if body.max_tool_rounds < 1 or body.max_tool_rounds > 100:
            return {"ok": False, "error": "最大工具轮次需在 1-100 之间"}
        config["max_tool_rounds"] = body.max_tool_rounds
    _write_config(config)
    return {"ok": True, "theme": config.get("theme", "blue")}


# ── 项目上下文 (app.md) 读写 ──

@router.get("/settings/app-context")
async def get_app_context():
    """读取 app.md 项目上下文原始内容（不含占位符展开）"""
    if APP_CONTEXT_PATH.exists():
        return {"content": APP_CONTEXT_PATH.read_text(encoding="utf-8")}
    return {"content": ""}


@router.put("/settings/app-context")
async def update_app_context(body: AppContextUpdate):
    """写入 app.md 项目上下文"""
    APP_CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_CONTEXT_PATH.write_text(body.content, encoding="utf-8")
    return {"ok": True}
