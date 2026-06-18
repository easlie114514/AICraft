"""模型管理 API — /api/models/*"""

from fastapi import APIRouter, HTTPException

from backend.deps import get_deps
from src.core.llm import test_connection
from src.utils.config import (
    get_all_model_configs,
    save_model_config,
    delete_model_config,
    set_default_model,
    get_current_model_id,
    set_current_model_id,
)

router = APIRouter(tags=["models"])


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
    from src.utils.config import get_all_model_configs
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
    set_current_model_id(model_id)
    return {"ok": True}


@router.put("/models/{name}/default")
async def set_model_default(name: str):
    """设为默认模型"""
    from src.utils.config import get_all_model_configs
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
