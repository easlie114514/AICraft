"""MCP客户端模块 - 连接MCP Server，发现和调用工具

支持两种连接模式：
  - SSE: HTTP 连接远程 MCP Server（短连接，每次调用重新建立）
  - Stdio: subprocess + 管道连接本地脚本（长连接，保持子进程存活）

打包模式 (PyInstaller)：
  - Stdio 连接的 command 自动从 "python" 切换为 sys.executable (exe 自身)
  - MCP Server 通过 --mcp-server <name> 标志在子进程中启动
"""

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.utils.config import load_json, save_json, RAG_DIR, resolve_path


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


def _extract_error(exc: Exception) -> str:
    """从 ExceptionGroup 中提取实际错误信息"""
    msg = str(exc)
    # Python 3.11+ ExceptionGroup: 展开子异常获取真实错误
    if hasattr(exc, "exceptions"):
        sub_msgs = []
        for sub in exc.exceptions:  # type: ignore[attr-defined]
            sub_msgs.append(_extract_error(sub))
        if sub_msgs:
            msg = "; ".join(sub_msgs)
    return msg


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

        for item in config.get("connections", config if isinstance(config, list) else []):
            conn = MCPConnection(
                name=item.get("name", ""),
                type=item.get("type", "sse"),        # 旧配置没有 type → 默认 sse
                host=item.get("host", ""),
                port=item.get("port", 0),
                url=item.get("url", ""),
                command=item.get("command", ""),
                args=self._resolve_mcp_args(item.get("args", [])),
                env=item.get("env", {}),
                enabled=item.get("enabled", True),
            )
            connections.append(conn)

        self.connections = connections
        return connections

    def save_connections(self) -> None:
        """保存连接列表到配置文件（args 中的项目路径自动转回相对路径）"""
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
                    "args": MCPManager._relativize_mcp_args(c.args),
                    "env": c.env,
                    "enabled": c.enabled,
                }
                for c in self.connections
            ]
        }
        save_profile_config("mcp_connections", data)

    @staticmethod
    def _resolve_mcp_args(args: list[str]) -> list[str]:
        """加载时：将 args 中的相对路径解析为绝对路径（以 BASE_DIR 为基准）。

        跳过 flags（-开头）、npm 包名（@开头或无作用域包名）、
        占位符（{开头）、URL（http开头）、纯数字（端口/超时值）。
        其余参数若在 BASE_DIR 下存在、或以 . / \\ 开头，视为相对路径并解析。

        自愈机制：已经过时的绝对路径（如 E:\\AICraft\\workspace 在 D: 盘机器上不存在）
        会尝试在当前 BASE_DIR 下查找同名路径。
        """
        from pathlib import Path
        from src.utils.config import BASE_DIR
        result = []
        for arg in args:
            if not isinstance(arg, str):
                result.append(arg)
                continue
            # 跳过明确的非路径模式
            if arg.startswith(("-", "@", "{", "http")) or arg.isdigit():
                result.append(arg)
                continue
            p = Path(arg)
            if p.is_absolute():
                # 自愈：绝对路径不存在时，尝试在当前 BASE_DIR 下查找同名相对路径
                if not p.exists():
                    healed = MCPManager._heal_path(arg, BASE_DIR)
                    if healed is not None:
                        result.append(healed)
                        continue
                result.append(arg)
                continue
            # 相对路径：以 BASE_DIR 为基准解析
            # 条件：包含路径分隔符 / \、以 . 开头、或在 BASE_DIR 下存在
            looks_like_path = (
                "/" in arg or "\\" in arg
                or arg.startswith(".")
                or (BASE_DIR / arg).exists()
            )
            if looks_like_path:
                resolved = resolve_path(arg)
                result.append(str(resolved))
            else:
                result.append(arg)
        return result

    @staticmethod
    def _heal_path(abs_path: str, base_dir) -> str | None:
        """自愈过时的绝对路径：尝试在 base_dir 下查找同名文件/目录。

        例如 E:\\AICraft\\workspace 在 D: 盘机器上不存在，
        但 D:\\AICraft\\workspace 存在 → 返回后者。

        从路径最右端逐层向左尝试，匹配第一个在 base_dir 下存在的路径。
        """
        from pathlib import Path
        p = Path(abs_path)
        parts = p.parts  # ('E:\\', 'AICraft', 'workspace')
        # 从倒数第1层到第2层（跳过盘符），尝试在 base_dir 下拼接
        for i in range(1, len(parts)):
            candidate = Path(base_dir, *parts[i:])
            if candidate.exists():
                return str(candidate)
        return None

    @staticmethod
    def _relativize_mcp_args(args: list[str]) -> list[str]:
        """保存时：将 args 中位于项目目录下的绝对路径转回相对路径。

        这样配置文件在不同机器/盘符间可移植，不会写入 E:\\AICraft 等绝对路径。
        不在项目目录下的外部路径保持绝对路径不变。
        """
        from pathlib import Path
        from src.utils.config import BASE_DIR
        result = []
        for arg in args:
            if not isinstance(arg, str):
                result.append(arg)
                continue
            try:
                p = Path(arg)
                if p.is_absolute():
                    # 尝试转为相对于 BASE_DIR 的路径
                    try:
                        rel = p.relative_to(BASE_DIR)
                        # 使用 POSIX 风格正斜杠，跨平台兼容
                        result.append(rel.as_posix())
                    except ValueError:
                        # 不在项目目录下，保持绝对路径
                        result.append(arg)
                else:
                    result.append(arg)
            except Exception:
                result.append(arg)
        return result

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
            args=self._resolve_mcp_args(args or []),
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
            conn.error_msg = _extract_error(e)[:200]
            return False

    # ── Stdio 连接（长连接：后台 Task + 消息队列）──
    #
    #  所有 anyio/MCP session 操作必须在同一个 asyncio task 中执行，
    #  否则 anyio 会抛出 "cancel scope in a different task" 错误。
    #  因此采用「后台 Task 持有连接 + 消息队列派发调用」的架构：
    #
    #    connect_stdio()  ──启动──▶  _run_session() (后台 task)
    #                                   │
    #    call_tool()  ──request──▶   msg_queue  ──▶  session.call_tool()
    #                   ◀──response───  resp_queue  ◀──
    #

    @staticmethod
    def _normalize_stdio_params(
        command: str, args: list[str]
    ) -> tuple[str, list[str]]:
        """适配打包环境：将 "python script.py" 转换为 "exe --mcp-server name"

        在 PyInstaller 打包后，系统没有独立的 python 解释器。
        需要让 exe 通过 --mcp-server <name> 标志自举启动 MCP 服务器。

        映射规则（从 args 提取服务器名称）：
          src/mcp_servers/code_executor.py  →  code_executor
          src/mcp_servers/file_manager.py   →  file_manager
        """
        if not getattr(sys, 'frozen', False):
            return command, args

        # 只转换 python/py 命令（保留 node/npx 等其他命令不变）
        if command not in ("python", "py", "python3"):
            return command, args

        # 从 args 中提取 MCP 服务器名称
        server_name = ""
        for arg in args:
            if not isinstance(arg, str):
                continue
            # 匹配 "xxx/code_executor.py" 或 "xxx\\code_executor.py"
            p = Path(arg)
            if p.suffix == ".py":
                server_name = p.stem
                break

        if not server_name:
            return command, args

        return sys.executable, ["--mcp-server", server_name]

    async def connect_stdio(self, conn: MCPConnection) -> bool:
        """启动后台 task 持有 stdio 长连接"""
        conn.status = "connecting"

        # 先清理旧连接
        if conn.name in self._stdio_procs:
            await self.disconnect_stdio(conn.name)

        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        # 打包模式下自动切换 command：python → sys.executable
        command, args = self._normalize_stdio_params(conn.command, conn.args)

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=conn.env if conn.env else None,
        )

        result_queue: asyncio.Queue = asyncio.Queue(maxsize=1)

        async def _run_session():
            """在单一 task 中持有连接、处理所有 call_tool 请求"""
            msg_queue: asyncio.Queue = asyncio.Queue()
            try:
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_result = await session.list_tools()

                        # 存储消息队列供 call_tool 使用
                        self._stdio_procs[conn.name] = {
                            "msg_queue": msg_queue,
                            "task": asyncio.current_task(),
                        }

                        # 通知调用方连接成功
                        result_queue.put_nowait({
                            "ok": True,
                            "tools": [
                                {
                                    "name": t.name,
                                    "description": t.description or "",
                                    "inputSchema": t.inputSchema or {},
                                }
                                for t in tools_result.tools
                            ]
                        })

                        # 循环处理 call_tool 请求
                        while True:
                            req = await msg_queue.get()
                            if req["type"] == "shutdown":
                                break
                            # call_tool 请求
                            resp_q = req["resp_q"]
                            try:
                                result = await session.call_tool(
                                    req["tool_name"], req["arguments"]
                                )
                                resp_q.put_nowait({"ok": True, "result": result})
                            except Exception as e:
                                resp_q.put_nowait({"ok": False, "error": _extract_error(e)})

            except asyncio.CancelledError:
                pass  # 正常取消，async with 的 __aexit__ 在同一 task 中执行
            except Exception as e:
                try:
                    result_queue.put_nowait({"ok": False, "error": _extract_error(e)[:200]})
                except asyncio.QueueFull:
                    pass
            finally:
                self._stdio_procs.pop(conn.name, None)

        # 启动后台 task
        task = asyncio.create_task(_run_session())
        self._stdio_procs[conn.name] = {"task": task}

        # 等待连接结果（超时 30 秒）
        try:
            result = await asyncio.wait_for(result_queue.get(), timeout=30.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except Exception:
                pass
            conn.status = "error"
            conn.error_msg = "连接超时"
            return False

        if result["ok"]:
            conn.tools = result["tools"]
            conn.status = "connected"
            conn.error_msg = ""
            return True
        else:
            conn.status = "error"
            conn.error_msg = result["error"]
            return False

    # ── 工具调用 ──

    async def call_tool(
        self, conn_name: str, tool_name: str, arguments: dict
    ) -> str:
        """调用 MCP 工具（自动判断模式，返回文本结果）

        - stdio: 通过消息队列派发给后台 task 执行，确保 anyio 不报错
        - sse:  新建短连接
        """
        conn = next((c for c in self.connections if c.name == conn_name), None)
        if not conn:
            return f"连接 {conn_name} 不存在"

        if conn.type == "stdio":
            proc = self._stdio_procs.get(conn_name)
            if not proc:
                return f"stdio 连接 {conn_name} 无活跃会话，请先连接"
            msg_queue = proc.get("msg_queue")
            if not msg_queue:
                return f"stdio 连接 {conn_name} 尚未就绪"
            resp_q: asyncio.Queue = asyncio.Queue(maxsize=1)
            msg_queue.put_nowait({
                "type": "call",
                "tool_name": tool_name,
                "arguments": arguments,
                "resp_q": resp_q,
            })
            resp = await resp_q.get()
            if resp["ok"]:
                result = resp["result"]
                if result.content:
                    return "\n".join(
                        c.text for c in result.content if hasattr(c, "text")
                    )
                return str(result)
            else:
                return f"工具执行失败: {resp['error']}"
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
        """关闭 stdio 连接：发 shutdown 消息给后台 task，触发 async with __aexit__"""
        proc = self._stdio_procs.pop(conn_name, None)
        if not proc:
            return
        task = proc.get("task")
        if not task or task.done():
            return
        # 先尝试通过消息队列优雅关闭（如果 msg_queue 已就绪）
        msg_queue = proc.get("msg_queue")
        if msg_queue:
            try:
                msg_queue.put_nowait({"type": "shutdown"})
                await asyncio.wait_for(task, timeout=5.0)
                return
            except (asyncio.TimeoutError, asyncio.QueueFull):
                pass
        # 回退：cancel task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
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
