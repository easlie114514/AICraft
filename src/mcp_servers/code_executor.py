"""AICraft Python Code Execution MCP Server

通过 stdio 暴露 execute_python 工具，在子进程中安全执行 Python 代码。
直接使用系统 Python 运行，无需 npm/node 依赖。
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# ── 工具定义 ──

EXECUTE_PYTHON_TOOL = Tool(
    name="execute_python",
    description=(
        "Execute Python code in a subprocess and return stdout/stderr. "
        "The code runs in a temporary file with a 60-second timeout. "
        "Use this to run calculations, data processing, or test code snippets."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 60, max: 120)",
                "default": 60,
            },
        },
        "required": ["code"],
    },
)

EXECUTE_SHELL_TOOL = Tool(
    name="execute_shell",
    description=(
        "Execute a shell command and return stdout/stderr. "
        "Useful for file operations, package installation, or running scripts. "
        "Commands run with a 30-second timeout."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute",
            },
        },
        "required": ["command"],
    },
)


# ── 执行逻辑 ──

def run_python_code(code: str, timeout: int = 60) -> str:
    """在临时文件中执行 Python 代码，返回输出"""
    timeout = min(timeout, 120)  # 硬上限 120s
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        # 打包模式：exe 需要通过 --run-script 标志执行脚本
        if getattr(sys, 'frozen', False):
            cmd = [sys.executable, "--run-script", tmp_path]
        else:
            cmd = [sys.executable, tmp_path]

        if os.name == "nt":
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
            )

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return f"[超时] 代码执行超过 {timeout} 秒，已终止"

        output_parts = []
        if stdout.strip():
            output_parts.append(stdout.strip())
        if stderr.strip():
            output_parts.append(f"[stderr]\n{stderr.strip()}")

        return "\n".join(output_parts) if output_parts else "[无输出]"

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def run_shell_command(command: str) -> str:
    """执行 shell 命令，返回输出"""
    try:
        if os.name == "nt":
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                cwd=os.path.expanduser("~"),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                cwd=os.path.expanduser("~"),
            )

        try:
            stdout, stderr = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return "[超时] 命令执行超过 30 秒，已终止"

        output_parts = []
        if stdout.strip():
            output_parts.append(stdout.strip())
        if stderr.strip():
            output_parts.append(f"[stderr]\n{stderr.strip()}")

        return "\n".join(output_parts) if output_parts else f"[退出码: {proc.returncode}]"

    except Exception as e:
        return f"执行失败: {e}"


# ── MCP Server ──

app = Server("aicraft-code-executor")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [EXECUTE_PYTHON_TOOL, EXECUTE_SHELL_TOOL]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "execute_python":
        code = arguments.get("code", "")
        if not code:
            return [TextContent(type="text", text="错误: code 参数不能为空")]
        timeout = arguments.get("timeout", 60)
        # 用 run_in_executor 避免 to_thread 的 context 问题
        loop = asyncio.get_running_loop()
        output = await loop.run_in_executor(None, run_python_code, code, timeout)
        return [TextContent(type="text", text=output)]

    if name == "execute_shell":
        command = arguments.get("command", "")
        if not command:
            return [TextContent(type="text", text="错误: command 参数不能为空")]
        loop = asyncio.get_running_loop()
        output = await loop.run_in_executor(None, run_shell_command, command)
        return [TextContent(type="text", text=output)]

    return [TextContent(type="text", text=f"未知工具: {name}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
