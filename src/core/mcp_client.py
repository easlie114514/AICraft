"""MCP客户端模块 - 连接MCP Server，发现和调用工具

支持两种连接模式：
  - SSE: HTTP 连接远程 MCP Server（短连接，每次调用重新建立）
  - Stdio: subprocess + 管道连接本地脚本（长连接，保持子进程存活）
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from src.utils.config import load_json, save_json, RAG_DIR


@dataclass
class MCPConnection:
    """MCP连接配置"""
    name: str
    type: str = "sse"              # 连接类型: "sse" | "stdio"
    # SSE 模式参数
    host: str = ""
    port: int = 0
    url: str = ""                  # 完整URL（优先级高于 host+port）
    # Stdio 模式参数
    command: str = ""              # 启动命令，如 "py" 或 "python"
    args: list[str] = field(default_factory=list)   # 命令参数
    env: dict[str, str] = field(default_factory=dict)  # 环境变量（可选）
    # 通用
    enabled: bool = True
    status: str = "disconnected"   # disconnected / connecting / connected / error
    tools: list[dict] = field(default_factory=list)
    error_msg: str = ""

    @property
    def sse_url(self) -> str:
        """获取SSE连接URL"""
        if self.url:
            return self.url
        return f"http://{self.host}:{self.port}/sse"

    @property
    def display_url(self) -> str:
        """用于UI展示的连接信息"""
        if self.type == "stdio":
            args_str = " ".join(self.args) if self.args else ""
            if args_str:
                return f"{self.command} {args_str}"
            return self.command
        if self.url:
            return self.url
        return f"{self.host}:{self.port}"


class MCPManager:
    """MCP连接管理器 — 支持 SSE 和 Stdio 两种模式"""

    CONFIG_PATH = RAG_DIR.parent / "config" / "mcp_connections.json"

    def __init__(self):
        self.connections: list[MCPConnection] = []
        # SSE 会话（预留，当前仍用短连接）
        self._sessions: dict[str, Any] = {}
        # Stdio 长连接上下文: {conn_name: {transport_ctx, session_ctx, session}}
        self._stdio_procs: dict[str, Any] = {}

    # ── 配置持久化 ──

    def load_connections(self) -> list[MCPConnection]:
        """从配置文件加载连接列表（兼容旧配置，无 type 字段默认 sse）"""
        from src.utils.config import load_profile_config
        config = load_profile_config("mcp_connections")
        connections = []

        for item in config.get("connections", []):
            conn = MCPConnection(
                name=item.get("name", ""),
                type=item.get("type", "sse"),        # 旧配置没有 type → 默认 sse
                host=item.get("host", ""),
                port=item.get("port", 0),
                url=item.get("url", ""),
                command=item.get("command", ""),
                args=item.get("args", []),
                env=item.get("env", {}),
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
                    "type": c.type,
                    "host": c.host,
                    "port": c.port,
                    "url": c.url,
                    "command": c.command,
                    "args": c.args,
                    "env": c.env,
                    "enabled": c.enabled,
                }
                for c in self.connections
            ]
        }
        save_profile_config("mcp_connections", data)

    def add_connection(
        self,
        name: str,
        conn_type: str = "sse",
        host: str = "",
        port: int = 0,
        url: str = "",
        command: str = "",
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> MCPConnection:
        """添加新的MCP连接"""
        conn = MCPConnection(
            name=name,
            type=conn_type,
            host=host,
            port=port,
            url=url,
            command=command,
            args=args or [],
            env=env or {},
        )
        self.connections.append(conn)
        self.save_connections()
        return conn

    def remove_connection(self, name: str) -> None:
        """移除MCP连接（先断开 stdio 连接再删除）"""
        # 如果是 stdio，先清理子进程
        if name in self._stdio_procs:
            from asyncio import ensure_future
            ensure_future(self.disconnect_stdio(name))
        self.connections = [c for c in self.connections if c.name != name]
        self.save_connections()

    def toggle_connection(self, name: str, enabled: bool) -> None:
        """开关MCP连接"""
        for conn in self.connections:
            if conn.name == name:
                conn.enabled = enabled
                if not enabled:
                    conn.status = "disconnected"
                    # 禁用时清理 stdio 子进程
                    if name in self._stdio_procs:
                        from asyncio import ensure_future
                        ensure_future(self.disconnect_stdio(name))
                break
        self.save_connections()

    # ── 统一连接入口 ──

    async def connect(self, conn: MCPConnection) -> bool:
        """连接 MCP Server（自动判断模式）"""
        if conn.type == "stdio":
            return await self.connect_stdio(conn)
        else:
            return await self.connect_sse(conn)

    # ── SSE 连接 ──

    async def connect_sse(self, conn: MCPConnection) -> bool:
        """通过 SSE 连接远程 MCP Server（短连接，仅发现工具）"""
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

    # ── Stdio 连接（长连接，保持子进程存活）──

    async def connect_stdio(self, conn: MCPConnection) -> bool:
        """通过 stdio 连接本地 MCP 脚本并保持长连接"""
        conn.status = "connecting"

        # 先清理旧连接
        if conn.name in self._stdio_procs:
            await self.disconnect_stdio(conn.name)

        try:
            from mcp import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client

            server_params = StdioServerParameters(
                command=conn.command,
                args=conn.args,
                env=conn.env if conn.env else None,
            )

            # 手动进入上下文——不退出，保持子进程存活
            transport_ctx = stdio_client(server_params)
            read, write = await transport_ctx.__aenter__()

            session_ctx = ClientSession(read, write)
            session = await session_ctx.__aenter__()
            await session.initialize()

            tools_result = await session.list_tools()

            # 存储上下文，供后续 call_tool 复用
            self._stdio_procs[conn.name] = {
                "transport_ctx": transport_ctx,
                "session_ctx": session_ctx,
                "session": session,
            }

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

    # ── 工具调用（复用长连接）──

    async def call_tool(
        self, conn_name: str, tool_name: str, arguments: dict
    ) -> str:
        """调用 MCP 工具（自动判断模式，返回文本结果）

        - stdio: 复用长连接 session
        - sse:  新建短连接
        """
        conn = next((c for c in self.connections if c.name == conn_name), None)
        if not conn:
            return f"连接 {conn_name} 不存在"

        if conn.type == "stdio":
            proc = self._stdio_procs.get(conn_name)
            if not proc:
                return f"stdio 连接 {conn_name} 无活跃会话，请先连接"
            try:
                result = await proc["session"].call_tool(tool_name, arguments)
            except Exception as e:
                return f"工具执行失败: {str(e)}"
        else:
            # SSE: 每次新建短连接
            try:
                from mcp import ClientSession
                from mcp.client.sse import sse_client

                async with sse_client(conn.sse_url) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)
            except Exception as e:
                return f"工具执行失败: {str(e)}"

        # 提取文本结果
        if result.content:
            return "\n".join(
                c.text for c in result.content if hasattr(c, "text")
            )
        return str(result)

    # ── 连接管理 ──

    async def connect_all_enabled(self) -> None:
        """连接所有已启用的MCP Server"""
        tasks = [self.connect(c) for c in self.connections if c.enabled]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def check_status(self, conn: MCPConnection) -> str:
        """检测MCP Server连接状态"""
        if conn.type == "stdio":
            # Stdio: 检查是否有活跃 session
            if conn.name in self._stdio_procs:
                conn.status = "connected"
                return "connected"
            conn.status = "disconnected"
            return "disconnected"

        # SSE: 尝试 HTTP 连接
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

    async def disconnect_stdio(self, conn_name: str) -> None:
        """关闭 stdio 连接，清理子进程"""
        proc = self._stdio_procs.pop(conn_name, None)
        if not proc:
            return
        # 先退出 session，再退出 transport
        try:
            await proc["session_ctx"].__aexit__(None, None, None)
        except Exception:
            pass
        try:
            await proc["transport_ctx"].__aexit__(None, None, None)
        except Exception:
            pass

    async def disconnect_all(self) -> None:
        """断开所有连接（关闭应用时调用，清理 stdio 子进程）"""
        for name in list(self._stdio_procs.keys()):
            await self.disconnect_stdio(name)

    def disconnect_all_sync(self) -> None:
        """同步版 disconnect_all，供 atexit 等不能运行 async 的场景使用"""
        import asyncio
        try:
            asyncio.run(self.disconnect_all())
        except Exception:
            pass

    # ── 工具列表 ──

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
