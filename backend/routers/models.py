"""模型管理 API — /api/models/*"""

from fastapi import APIRouter, HTTPException

from backend.deps import get_deps
from src.core.llm import test_connection
from src.utils.config import (
    MODELS_DIR,
    get_all_model_configs,
    load_json,
    save_json,
    save_model_config,
    delete_model_config,
    set_default_model,
    get_current_model_id,
    set_current_model_id,
)


def _unset_all_defaults() -> None:
    """取消所有模型的默认标记"""
    for m in get_all_model_configs():
        if m.get("is_default"):
            fn = m.get("_filename", "")
            if fn:
                m["is_default"] = False
                save_json(MODELS_DIR / f"{fn}.json", m)

router = APIRouter(tags=["models"])

# ═══════════════════════════════════════════════════════════
# 通道预设
# ═══════════════════════════════════════════════════════════

CHANNEL_PRESETS = {
    "deepseek": {
        "name": "DeepSeek 定制通道",
        "base_url": "https://api.deepseek.com/anthropic",
        "protocol": "anthropic",
        "models": [
            {
                "filename": "dsv4pro",
                "name": "DeepSeek V4 Pro",
                "model_id": "deepseek-v4-pro",
                "tier": "pro",
                "supports_thinking": True,
                "supports_web_search": True,
                "is_default": True,
            },
            {
                "filename": "dsv4flash",
                "name": "DeepSeek V4 Flash",
                "model_id": "deepseek-v4-flash",
                "tier": "flash",
                "supports_thinking": True,
                "supports_web_search": True,
                "is_default": False,
            },
        ],
    },
    # 后续可扩展 openai / anthropic 等通道预设
}


# ═══════════════════════════════════════════════════════════
# 现有 CRUD
# ═══════════════════════════════════════════════════════════

@router.get("/models")
async def list_models():
    """获取所有模型配置"""
    configs = get_all_model_configs()
    current_id = get_current_model_id()
    for cfg in configs:
        cfg["is_current"] = cfg.get("model_id") == current_id
        # 隐藏敏感字段
        cfg.pop("api_key", None)
    return configs


@router.post("/models")
async def create_model(data: dict):
    """创建模型配置"""
    try:
        save_model_config(data)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/models/{name}")
async def delete_model(name: str):
    """删除模型配置"""
    ok = delete_model_config(name)
    if not ok:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {"ok": True}


@router.post("/models/{name}/test")
async def test_model(name: str):
    """测试模型连接"""
    configs = get_all_model_configs()
    cfg = None
    for m in configs:
        if m.get("name") == name:
            cfg = m
            break
    if not cfg:
        raise HTTPException(status_code=404, detail="模型不存在")
    ok, msg = await test_connection(cfg)
    return {"ok": ok, "message": msg}


@router.get("/models/current")
async def get_current_model():
    """获取当前选中的模型 ID"""
    return {"model_id": get_current_model_id()}


@router.put("/models/current")
async def set_current_model(data: dict):
    """设置当前模型"""
    model_id = data.get("model_id", "")
    # Auto 是运行时路由，不持久化到配置文件
    if model_id != "auto":
        set_current_model_id(model_id)
    return {"ok": True}


@router.put("/models/{name}/default")
async def set_model_default(name: str):
    """设为默认模型"""
    configs = get_all_model_configs()
    cfg = None
    for m in configs:
        if m.get("name") == name:
            cfg = m
            break
    if not cfg:
        raise HTTPException(status_code=404, detail="模型不存在")
    set_default_model(cfg["model_id"])
    return {"ok": True}


# ═══════════════════════════════════════════════════════════
# 通道预设 API
# ═══════════════════════════════════════════════════════════

@router.get("/models/channels")
async def list_channels():
    """列出可用的通道预设"""
    channels = []
    for key, preset in CHANNEL_PRESETS.items():
        channels.append({
            "type": key,
            "name": preset["name"],
            "base_url": preset["base_url"],
            "protocol": preset["protocol"],
            "models": [
                {
                    "name": m["name"],
                    "model_id": m["model_id"],
                    "tier": m["tier"],
                }
                for m in preset["models"]
            ],
        })
    return channels


@router.post("/models/channel")
async def add_channel(data: dict):
    """通过通道预设批量创建模型配置

    Body:
        channel_type: 通道类型（如 "deepseek"）
        api_key: API Key

    自动创建该通道下的所有模型（Pro + Flash 等）。
    """
    channel_type = data.get("channel_type", "").strip()
    api_key = data.get("api_key", "").strip()

    if not channel_type:
        raise HTTPException(status_code=400, detail="请选择通道类型")
    if not api_key:
        raise HTTPException(status_code=400, detail="请输入 API Key")

    preset = CHANNEL_PRESETS.get(channel_type)
    if not preset:
        raise HTTPException(status_code=400, detail=f"未知通道类型: {channel_type}")

    created = []
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for model_def in preset["models"]:
        config = {
            "name": model_def["name"],
            "provider": channel_type,
            "model_id": model_def["model_id"],
            "api_key": api_key,
            "api_base": preset["base_url"],
            "protocol": preset["protocol"],
            "tier": model_def["tier"],
            "supports_thinking": model_def["supports_thinking"],
            "supports_web_search": model_def["supports_web_search"],
            "is_default": model_def["is_default"],
        }
        # 如果标记为默认，先取消其他模型的默认标记
        if config.get("is_default"):
            _unset_all_defaults()
        save_json(MODELS_DIR / f"{model_def['filename']}.json", config)
        created.append(model_def["name"])

    return {"ok": True, "created": created}


# ═══════════════════════════════════════════════════════════
# 模型更新（Key 联动）
# ═══════════════════════════════════════════════════════════

@router.put("/models/{name}")
async def update_model(name: str, data: dict):
    """更新模型配置，同 provider 的 api_key 自动联动

    Body 可以包含任意模型字段（api_key, api_base, model_id 等）。
    如果修改了 api_key，同 provider 的其他模型也会同步更新。
    """
    # 找到当前模型配置
    configs = get_all_model_configs()
    cfg = None
    for m in configs:
        if m.get("name") == name:
            cfg = m
            break
    if not cfg:
        raise HTTPException(status_code=404, detail="模型不存在")

    filename = cfg.get("_filename", name)

    # 更新字段
    for k, v in data.items():
        if k != "name" and k != "_filename":  # 不允许改名
            cfg[k] = v

    save_json(MODELS_DIR / f"{filename}.json", cfg)

    # 如果修改了 api_key，同 provider 的其他模型也同步
    if "api_key" in data:
        new_key = data["api_key"]
        provider = cfg.get("provider", "")
        for other in configs:
            if other.get("provider") == provider and other.get("name") != name:
                other_fn = other.get("_filename", other.get("name", ""))
                if other_fn:
                    other["api_key"] = new_key
                    save_json(MODELS_DIR / f"{other_fn}.json", other)

    return {"ok": True}
