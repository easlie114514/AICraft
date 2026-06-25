"""MCP 连接管理 API — /api/mcp/*"""

import json
from fastapi import APIRouter, HTTPException

from backend.deps import get_deps

router = APIRouter(tags=["mcp"])


def _conn_to_dict(conn):
    return {
        "name": conn.name,
        "type": conn.type,
        "host": conn.host,
        "port": conn.port,
        "url": conn.url,
        "command": conn.command,
        "args": conn.args,
        "env": conn.env,
        "enabled": conn.enabled,
        "auto_grant": conn.auto_grant,
        "status": conn.status,
        "tools": conn.tools,
        "error_msg": conn.error_msg,
        "display_url": conn.display_url,
    }


@router.get("/mcp/env-check")
async def check_mcp_env():
    """检测 MCP 运行环境（Node.js/npx 是否可用）"""
    from src.utils.env import check_node_env
    return check_node_env()


@router.get("/mcp")
async def list_connections():
    """列出所有 MCP 连接"""
    deps = get_deps()
    return [_conn_to_dict(c) for c in deps.mcp_manager.connections]


@router.post("/mcp")
async def add_connection(data: dict):
    """添加 MCP 连接"""
    deps = get_deps()
    conn = deps.mcp_manager.add_connection(
        name=data.get("name", ""),
        conn_type=data.get("type", "sse"),
        host=data.get("host", ""),
        port=data.get("port", 0),
        url=data.get("url", ""),
        command=data.get("command", ""),
        args=data.get("args", []),
        env=data.get("env", {}),
    )
    return _conn_to_dict(conn)


@router.delete("/mcp/{name}")
async def delete_connection(name: str):
    """删除 MCP 连接"""
    deps = get_deps()
    deps.mcp_manager.remove_connection(name)
    return {"ok": True}


@router.put("/mcp/{name}/toggle")
async def toggle_connection(name: str, data: dict):
    """启用/禁用 MCP 连接"""
    deps = get_deps()
    enabled = data.get("enabled", True)
    deps.mcp_manager.toggle_connection(name, enabled)

    # 启用时自动触发重连
    if enabled:
        conn = None
        for c in deps.mcp_manager.connections:
            if c.name == name:
                conn = c
                break
        if conn:
            await deps.mcp_manager.connect(conn)

    return {"ok": True}


@router.put("/mcp/{name}/toggle-approval")
async def toggle_approval(name: str, data: dict):
    """开关 MCP 连接的自动授予权限"""
    deps = get_deps()
    deps.mcp_manager.toggle_auto_grant(name, data.get("auto_grant", False))
    return {"ok": True}


@router.post("/mcp/{name}/connect")
async def connect_mcp(name: str):
    """连接 MCP 服务器"""
    deps = get_deps()
    conn = None
    for c in deps.mcp_manager.connections:
        if c.name == name:
            conn = c
            break
    if not conn:
        raise HTTPException(status_code=404, detail="连接不存在")
    try:
        ok = await deps.mcp_manager.connect(conn)
        return {"ok": ok, "status": conn.status, "tools": conn.tools, "error": conn.error_msg}
    except Exception as e:
        return {"ok": False, "status": "error", "tools": [], "error": str(e)}


@router.post("/mcp/{name}/disconnect")
async def disconnect_mcp(name: str):
    """断开 MCP 连接"""
    deps = get_deps()
    try:
        await deps.mcp_manager.disconnect_stdio(name)
    except Exception:
        pass
    return {"ok": True}


# ── 权限配置 API ──

@router.get("/mcp/permissions")
async def get_permissions():
    """获取权限配置（信任/拒绝路径、超时等）"""
    from src.core.permission_guard import load_permission_config
    return load_permission_config()


@router.put("/mcp/permissions")
async def update_permissions(data: dict):
    """更新权限配置"""
    from src.core.permission_guard import load_permission_config, save_permission_config

    cfg = load_permission_config()
    # 只允许更新白名单字段
    allowed_fields = {"trusted_paths", "denied_paths", "prompt_timeout_seconds"}
    for key in allowed_fields:
        if key in data:
            cfg[key] = data[key]

    save_permission_config(cfg)
    return cfg
