"""MCP客户端模块 - 连接MCP Server，发现和调用工具"""

import asyncio
from dataclasses import dataclass
from typing import Any

from src.utils.config import load_json, save_json, RAG_DIR


@dataclass
class MCPConnection:
    """MCP连接配置"""
    name: str
    host: str = ""
    port: int = 0
    url: str = ""  # 完整URL（优先级高于 host+port）
    enabled: bool = True
    status: str = "disconnected"  # disconnected / connecting / connected / error
    tools: list[dict] = None
    error_msg: str = ""

    def __post_init__(self):
        if self.tools is None:
            self.tools = []

    @property
    def sse_url(self) -> str:
        """获取SSE连接URL"""
        if self.url:
            return self.url
        return f"http://{self.host}:{self.port}/sse"

    @property
    def display_url(self) -> str:
        """用于UI展示的地址"""
        if self.url:
            return self.url
        return f"{self.host}:{self.port}"


class MCPManager:
    """MCP连接管理器"""

    CONFIG_PATH = RAG_DIR.parent / "config" / "mcp_connections.json"

    def __init__(self):
        self.connections: list[MCPConnection] = []
        self._sessions: dict[str, Any] = {}

    def load_connections(self) -> list[MCPConnection]:
        """从配置文件加载连接列表"""
        # 配置存在profile目录下
        from src.utils.config import load_profile_config
        config = load_profile_config("mcp_connections")
        connections = []

        for item in config.get("connections", []):
            conn = MCPConnection(
                name=item.get("name", ""),
                host=item.get("host", ""),
                port=item.get("port", 0),
                url=item.get("url", ""),
                enabled=item.get("enabled", True),
            )
            connections.append(conn)

        self.connections = connections
        return connections

    def save_connections(self) -> None:
        """保存连接列表到配置文件"""
        from src.utils.config import save_profile_config
        data = {
            "connections": [
                {
                    "name": c.name,
                    "host": c.host,
                    "port": c.port,
                    "url": c.url,
                    "enabled": c.enabled,
                }
                for c in self.connections
            ]
        }
        save_profile_config("mcp_connections", data)

    def add_connection(self, name: str, host: str = "", port: int = 0, url: str = "") -> MCPConnection:
        """添加新的MCP连接，支持 host+port 或完整 URL"""
        conn = MCPConnection(name=name, host=host, port=port, url=url)
        self.connections.append(conn)
        self.save_connections()
        return conn

    def remove_connection(self, name: str) -> None:
        """移除MCP连接"""
        self.connections = [c for c in self.connections if c.name != name]
        self.save_connections()

    def toggle_connection(self, name: str, enabled: bool) -> None:
        """开关MCP连接"""
        for conn in self.connections:
            if conn.name == name:
                conn.enabled = enabled
                if not enabled:
                    conn.status = "disconnected"
                break
        self.save_connections()

    async def connect(self, conn: MCPConnection) -> bool:
        """连接到MCP Server并发现工具"""
        conn.status = "connecting"
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            async with sse_client(conn.sse_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()

                    conn.tools = [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "inputSchema": t.inputSchema or {},
                        }
                        for t in tools_result.tools
                    ]
                    conn.status = "connected"
                    conn.error_msg = ""
                    return True

        except Exception as e:
            conn.status = "error"
            conn.error_msg = str(e)[:200]
            return False

    async def connect_all_enabled(self) -> None:
        """连接所有已启用的MCP Server"""
        tasks = [self.connect(c) for c in self.connections if c.enabled]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def check_status(self, conn: MCPConnection) -> str:
        """检测MCP Server连接状态"""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            async with sse_client(conn.sse_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    conn.status = "connected"
                    return "connected"
        except Exception:
            conn.status = "disconnected"
            return "disconnected"

    def get_enabled_tools(self) -> list[dict]:
        """获取所有已连接MCP的工具列表（OpenAI function calling格式）"""
        tools = []
        for conn in self.connections:
            if conn.enabled and conn.status == "connected":
                for t in conn.tools:
                    tools.append({
                        "type": "function",
                        "function": {
                            "name": t["name"],
                            "description": t["description"],
                            "parameters": t["inputSchema"],
                        }
                    })
        return tools
