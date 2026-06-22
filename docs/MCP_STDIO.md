# AICraft MCP Stdio 模式设计文档

> 本文档定义 MCP 客户端新增 stdio 模式的实现规范，使 AICraft 能直接启动本地 MCP 脚本通过管道通信，无需额外 HTTP 服务。

## 一、背景

当前 `mcp_client.py` 仅支持 SSE 模式（HTTP 连接远程 MCP Server）。
但很多 MCP 服务是本地脚本（如 sipp_workshop_mcp.py），通过 stdin/stdout 通信，不走网络。
Claude Code 用 `claude mcp add xxx -- python xxx.py` 就是 stdio 模式。
AICraft 也应该支持。

## 二、连接类型定义

### 2.1 两种模式

| 模式 | 连接方式 | 适用场景 | MCP SDK 客户端 |
|------|---------|---------|--------------|
| `sse` | HTTP 连接远程服务 | 远程/局域网 MCP Server | `mcp.client.sse.sse_client` |
| `stdio` | subprocess + 管道 | 本地 Python 脚本 | `mcp.client.stdio.stdio_client` |

### 2.2 MCPConnection 扩展

```python
@dataclass
class MCPConnection:
    name: str
    type: str = "sse"           # 新增：连接类型 "sse" | "stdio"
    # SSE 模式参数
    host: str = ""
    port: int = 0
    url: str = ""
    # Stdio 模式参数
    command: str = ""           # 启动命令，如 "python" 或 "py"
    args: list[str] = None      # 命令参数，如 ["scripts/workshop_mcp.py"]（相对项目根）
    env: dict[str, str] = None  # 环境变量（可选）
    # 通用
    enabled: bool = True
    status: str = "disconnected"
    tools: list[dict] = None
    error_msg: str = ""
```

### 2.3 配置文件格式

`mcp_connections.json` 示例：

```json
{
  "connections": [
    {
      "name": "积木工坊",
      "type": "sse",
      "host": "",
      "port": 0,
      "url": "http://172.28.33.101/api",
      "enabled": true
    },
    {
      "name": "SIPP积木工坊",
      "type": "stdio",
      "command": "py",
      "args": ["-3.13", "scripts/workshop_mcp.py"],
      "env": {},
      "enabled": true
    }
  ]
}
```

## 三、Stdio 连接实现

### 3.1 核心代码

MCP Python SDK 已内置 stdio 客户端，直接用：

```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

async def connect_stdio(self, conn: MCPConnection) -> bool:
    """通过 stdio 连接本地 MCP 脚本"""
    conn.status = "connecting"
    try:
        server_params = StdioServerParameters(
            command=conn.command,       # "py" 或 "python"
            args=conn.args,             # ["-3.13", "scripts/workshop_mcp.py"]
            env=conn.env or None,       # 额外环境变量
        )

        async with stdio_client(server_params) as (read, write):
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
```

### 3.2 统一 connect 入口

```python
async def connect(self, conn: MCPConnection) -> bool:
    """连接 MCP Server（自动判断模式）"""
    if conn.type == "stdio":
        return await self.connect_stdio(conn)
    else:
        return await self.connect_sse(conn)
```

把原 `connect` 方法重命名为 `connect_sse`，新增 `connect_stdio`，统一入口自动路由。

### 3.3 工具调用

工具调用逻辑和 SSE 完全一致，都是 `session.call_tool(name, arguments)`。
区别是 stdio 模式需要保持子进程活跃，不能每次调用都重新启动。

**方案：长连接会话管理**

```python
class MCPManager:
    def __init__(self):
        self.connections: list[MCPConnection] = []
        self._sessions: dict[str, Any] = {}        # SSE 会话
        self._stdio_procs: dict[str, Any] = {}      # stdio 子进程上下文

    async def connect_stdio(self, conn: MCPConnection) -> bool:
        """连接 stdio MCP 并保持会话"""
        conn.status = "connecting"
        try:
            server_params = StdioServerParameters(
                command=conn.command,
                args=conn.args,
                env=conn.env or None,
            )
            # 进入上下文但不退出，保持子进程存活
            ctx = stdio_client(server_params)
            read, write = await ctx.__aenter__()
            
            session_ctx = ClientSession(read, write)
            session = await session_ctx.__aenter__()
            await session.initialize()
            
            # 存储上下文，后续调用用同一个 session
            self._stdio_procs[conn.name] = {
                "transport_ctx": ctx,
                "session_ctx": session_ctx,
                "session": session,
            }

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

    async def call_tool(self, conn_name: str, tool_name: str, arguments: dict) -> Any:
        """调用 MCP 工具（自动判断模式）"""
        conn = next((c for c in self.connections if c.name == conn_name), None)
        if not conn:
            raise ValueError(f"连接 {conn_name} 不存在")

        if conn.type == "stdio":
            proc = self._stdio_procs.get(conn_name)
            if not proc:
                raise RuntimeError(f"stdio 连接 {conn_name} 无活跃会话")
            result = await proc["session"].call_tool(tool_name, arguments)
            return result
        else:
            # SSE 模式：每次新建短连接
            async with sse_client(conn.sse_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    return result

    async def disconnect_stdio(self, conn_name: str) -> None:
        """关闭 stdio 连接，清理子进程"""
        proc = self._stdio_procs.pop(conn_name, None)
        if proc:
            try:
                await proc["session_ctx"].__aexit__(None, None, None)
            except Exception:
                pass
            try:
                await proc["transport_ctx"].__aexit__(None, None, None)
            except Exception:
                pass
```

### 3.4 清理

应用关闭时必须清理所有 stdio 子进程：

```python
async def disconnect_all(self) -> None:
    """断开所有连接"""
    for name in list(self._stdio_procs.keys()):
        await self.disconnect_stdio(name)
```

## 四、UI 变更

### 4.1 MCP 连接页新增

添加连接时，根据选择的类型显示不同表单：

- **SSE 模式**：输入 host / port / url（现有逻辑不变）
- **Stdio 模式**：输入 command（如 `py`）、args（如 `-3.13 scripts/workshop_mcp.py`，空格分隔，路径相对于项目根）

### 4.2 连接卡片展示

- SSE：显示 `host:port` 或 url
- Stdio：显示 `command args[0] args[1]...`

### 4.3 连接状态检测

- SSE：尝试 HTTP 连接
- Stdio：检查子进程是否存活（session 是否可用）

## 五、配置迁移

旧配置文件没有 `type` 字段，加载时默认为 `sse`：

```python
conn = MCPConnection(
    name=item.get("name", ""),
    type=item.get("type", "sse"),   # 兼容旧配置
    # ...
)
```

## 六、改动清单

| 文件 | 改动 |
|------|------|
| `src/core/mcp_client.py` | MCPConnection 新增 type/command/args/env 字段；connect 拆分为 connect_sse/connect_stdio；新增 call_tool/disconnect_stdio/disconnect_all；长连接会话管理 |
| `aicraft.py` | MCP 页面 UI 新增连接类型选择和 stdio 表单；关闭应用时调用 disconnect_all |
| `config/profiles/default/mcp_connections.json` | 新增 type 字段，兼容旧配置 |

## 七、注意事项

1. **子进程生命周期**：stdio 模式的子进程随 AICraft 启动而启动，随关闭而关闭。如果脚本崩溃，需要重新连接。
2. **Python 版本**：Windows 多版本共存时，command 用 `py`，args 加 `-3.13` 指定版本。
3. **工作目录**：stdio 子进程的工作目录默认是 AICraft 启动目录，如需指定在 env 中设置。
4. **依赖**：`mcp` 包已包含 `mcp.client.stdio`，无需额外安装。
