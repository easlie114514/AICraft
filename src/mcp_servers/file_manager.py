"""AICraft File Manager MCP Server

通过 stdio 暴露文件管理工具，支持全盘访问（无内置路径限制）。
权限控制由 AICraft 的 PermissionGuard 在客户端层统一管理。

相对路径解析：所有相对路径以 USER_DIR 为基准解析（开发模式=项目根目录，
打包模式=%APPDATA%/AICraft），确保 Skill 写的 "roles/xxx.md" 等相对路径
始终落在正确位置。

工具接口兼容 @modelcontextprotocol/server-filesystem，LLM 无感知切换。
"""

import asyncio
import os
import re
import shutil
import stat
import time
from datetime import datetime
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from src.utils.config import USER_DIR


# ═══════════════════════════════════════════════════════════
# 文件大小限制
# ═══════════════════════════════════════════════════════════

MAX_FILE_SIZE = 10 * 1024 * 1024      # 读取文件上限 10MB
MAX_WRITE_SIZE = 5 * 1024 * 1024      # 写入内容上限 5MB
MAX_SEARCH_RESULTS = 200              # 搜索最多返回 200 条
MAX_LIST_ITEMS = 500                  # 列目录最多 500 项


def _format_size(size: int) -> str:
    """人类可读的文件大小"""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size} {unit}"
        size //= 1024
    return f"{size} TB"


def _format_permissions(mode: int) -> str:
    """将 st_mode 转为类似 rwxr-xr-x 的字符串"""
    result = ""
    for who in (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR,
                stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP,
                stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH):
        result += "r" if mode & who else "-"
        who >>= 1
        result += "w" if mode & who else "-"
        who >>= 1
        result += "x" if mode & who else "-"
    return result


def _iter_files(path: Path, pattern: str | None, max_results: int) -> list[str]:
    """递归搜索文件，支持 glob pattern"""
    results: list[str] = []
    try:
        if pattern:
            # 如果 pattern 不包含路径分隔符，用 rglob；否则用 glob
            if "/" in pattern or "\\" in pattern:
                it = path.glob(pattern)
            else:
                it = path.rglob(pattern)
        else:
            it = path.rglob("*")

        for p in it:
            if len(results) >= max_results:
                break
            if p.is_file():
                results.append(str(p))
    except PermissionError:
        pass
    return results


# ═══════════════════════════════════════════════════════════
# 工具定义
# ═══════════════════════════════════════════════════════════

READ_FILE_TOOL = Tool(
    name="read_file",
    description=(
        "Read the complete contents of a file. "
        "Supports text files and code files. "
        "For binary files, returns a hex dump. "
        "Maximum file size: 10MB."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to read",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-based, optional)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read (optional, default: all)",
            },
        },
        "required": ["path"],
    },
)

WRITE_FILE_TOOL = Tool(
    name="write_file",
    description=(
        "Create a new file or completely overwrite an existing file with new content. "
        "Use with caution — this overwrites the entire file."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["path", "content"],
    },
)

EDIT_FILE_TOOL = Tool(
    name="edit_file",
    description=(
        "Make targeted edits to a file by replacing exact text. "
        "The old_string must match the file content exactly (including whitespace). "
        "Only the first match is replaced unless replace_all is true."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "The exact text to replace",
            },
            "new_string": {
                "type": "string",
                "description": "The text to replace it with",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences (default: false)",
                "default": False,
            },
        },
        "required": ["path", "old_string", "new_string"],
    },
)

DELETE_FILE_TOOL = Tool(
    name="delete_file",
    description=(
        "Delete a file at the specified path. "
        "The operation will fail gracefully if the file doesn't exist."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to delete",
            },
        },
        "required": ["path"],
    },
)

CREATE_DIRECTORY_TOOL = Tool(
    name="create_directory",
    description="Create a new directory or ensure a directory exists. Creates parent directories as needed.",
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the directory to create",
            },
        },
        "required": ["path"],
    },
)

LIST_DIRECTORY_TOOL = Tool(
    name="list_directory",
    description=(
        "Get a detailed listing of all files and directories in a given path. "
        "Results include name, size, type, and modification time."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the directory to list",
            },
        },
        "required": ["path"],
    },
)

SEARCH_FILES_TOOL = Tool(
    name="search_files",
    description=(
        "Recursively search for files and directories matching a pattern. "
        "The pattern can be a simple filename (e.g. '*.py') or a glob path pattern. "
        "Returns up to 200 results."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the directory to search in",
            },
            "pattern": {
                "type": "string",
                "description": "Filename pattern (e.g. '*.py', 'test_*.ts', '**/*.json')",
            },
        },
        "required": ["path", "pattern"],
    },
)

MOVE_FILE_TOOL = Tool(
    name="move_file",
    description=(
        "Move or rename a file or directory. "
        "Can move files between different directories."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Absolute path to the source file/directory",
            },
            "destination": {
                "type": "string",
                "description": "Absolute path to the destination",
            },
        },
        "required": ["source", "destination"],
    },
)

GET_FILE_INFO_TOOL = Tool(
    name="get_file_info",
    description=(
        "Retrieve detailed metadata about a file or directory. "
        "Returns size, permissions, modification time, owner, and type."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file or directory",
            },
        },
        "required": ["path"],
    },
)


# ═══════════════════════════════════════════════════════════
# 路径解析
# ═══════════════════════════════════════════════════════════

def _resolve_path(raw_path: str) -> Path:
    """将路径解析为绝对路径。相对路径以 USER_DIR 为基准。

    这样 Skill 写的 "roles/xxx.md" 在开发模式解析到项目根目录，
    在打包模式解析到 %APPDATA%/AICraft/，不受 CWD 影响。
    """
    p = Path(raw_path)
    if p.is_absolute():
        return p
    return (USER_DIR / p).resolve()


# ═══════════════════════════════════════════════════════════
# 工具实现
# ═══════════════════════════════════════════════════════════

def _read_file(path: Path, offset: int = 0, limit: int = 0) -> str:
    """同步读取文件，返回文本内容"""
    if not path.exists():
        return f"错误: 文件不存在: {path}"
    if not path.is_file():
        return f"错误: 路径不是文件: {path}"
    if path.stat().st_size > MAX_FILE_SIZE:
        return f"错误: 文件过大 ({_format_size(path.stat().st_size)} > {_format_size(MAX_FILE_SIZE)})"

    # 检测是否为二进制文件
    try:
        with open(path, "r", encoding="utf-8") as f:
            sample = f.read(512)
        is_binary = "\x00" in sample
    except (UnicodeDecodeError, OSError):
        is_binary = True

    if is_binary:
        # 返回十六进制 dump（前 1024 字节）
        with open(path, "rb") as f:
            data = f.read(1024)
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = " ".join(f"{b:02x}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{i:08x}  {hex_part:<48}  {ascii_part}")
        header = f"[二进制文件] 大小: {_format_size(path.stat().st_size)}\n\n"
        return header + "\n".join(lines)

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    total = len(lines)
    if offset > 0:
        lines = lines[offset - 1:]  # offset is 1-based
    if limit > 0:
        lines = lines[:limit]

    result = "".join(lines)
    if offset > 0 or limit > 0:
        header = f"[文件: {path}] [行 {max(offset, 1)}-{max(offset, 1) + len(lines) - 1} / 共 {total} 行]\n"
    else:
        header = f"[文件: {path}] [共 {total} 行]\n"
    return header + result


def _write_file(path: Path, content: str) -> str:
    """同步写入文件"""
    if len(content.encode("utf-8")) > MAX_WRITE_SIZE:
        return f"错误: 内容过大 ({_format_size(len(content.encode('utf-8')))} > {_format_size(MAX_WRITE_SIZE)})"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        size = path.stat().st_size
        return f"成功写入: {path} ({_format_size(size)})"
    except Exception as e:
        return f"写入失败: {e}"


def _edit_file(path: Path, old_string: str, new_string: str, replace_all: bool = False) -> str:
    """同步编辑文件（精确字符串替换）"""
    if not path.exists():
        return f"错误: 文件不存在: {path}"
    if not path.is_file():
        return f"错误: 路径不是文件: {path}"

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"读取文件失败: {e}"

    if old_string not in content:
        return (
            f"错误: 未找到要替换的文本。old_string 必须与文件内容完全匹配。\n"
            f"提示: 检查空格、换行和缩进。"
        )

    count = content.count(old_string) if replace_all else 1
    new_content = content.replace(old_string, new_string) if replace_all else content.replace(old_string, new_string, 1)

    try:
        path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return f"写入文件失败: {e}"

    return f"成功编辑: {path}（替换了 {count} 处）"


def _delete_file(path: Path) -> str:
    """同步删除文件"""
    if not path.exists():
        return f"错误: 文件不存在: {path}"
    if not path.is_file():
        return f"错误: 路径不是文件: {path}（使用其他工具删除目录）"

    try:
        path.unlink()
        return f"成功删除: {path}"
    except Exception as e:
        return f"删除失败: {e}"


def _create_directory(path: Path) -> str:
    """同步创建目录"""
    if path.exists():
        if path.is_dir():
            return f"目录已存在: {path}"
        return f"错误: 已存在同名文件: {path}"

    try:
        path.mkdir(parents=True, exist_ok=True)
        return f"成功创建目录: {path}"
    except Exception as e:
        return f"创建目录失败: {e}"


def _list_directory(path: Path) -> str:
    """同步列出目录"""
    if not path.exists():
        return f"错误: 目录不存在: {path}"
    if not path.is_dir():
        return f"错误: 路径不是目录: {path}"

    try:
        items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return f"错误: 没有权限访问: {path}"

    if not items:
        return f"[空目录] {path}"

    lines = [f"[目录列表] {path}\n"]
    lines.append(f"{'类型':<6} {'大小':<10} {'修改时间':<20} {'权限':<11} {'名称'}")
    lines.append("-" * 80)

    count = 0
    for item in items:
        if count >= MAX_LIST_ITEMS:
            lines.append(f"\n... 还有 {len(items) - MAX_LIST_ITEMS} 项未显示")
            break
        try:
            st = item.stat()
            ftype = "DIR" if item.is_dir() else "FILE"
            fsize = _format_size(st.st_size) if item.is_file() else "-"
            mtime = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            perm = _format_permissions(st.st_mode)
            name = item.name + ("/" if item.is_dir() else "")
            lines.append(f"{ftype:<6} {fsize:<10} {mtime:<20} {perm:<11} {name}")
            count += 1
        except (PermissionError, OSError):
            lines.append(f"{'??':<6} {'??':<10} {'??':<20} {'??':<11} {item.name}")
            count += 1

    return "\n".join(lines)


def _search_files(path: Path, pattern: str) -> str:
    """同步搜索文件"""
    if not path.exists():
        return f"错误: 目录不存在: {path}"
    if not path.is_dir():
        return f"错误: 路径不是目录: {path}"

    try:
        results = _iter_files(path, pattern, MAX_SEARCH_RESULTS)
    except Exception as e:
        return f"搜索失败: {e}"

    if not results:
        return f"未找到匹配 '{pattern}' 的文件（在 {path} 中）"

    lines = [f"[搜索: {pattern}] 在 {path} 中找到 {len(results)} 个文件\n"]
    for r in results:
        try:
            size = _format_size(Path(r).stat().st_size)
            lines.append(f"  {size:<10} {r}")
        except OSError:
            lines.append(f"  {'??':<10} {r}")

    return "\n".join(lines)


def _move_file(source: Path, destination: Path) -> str:
    """同步移动/重命名文件"""
    if not source.exists():
        return f"错误: 源文件不存在: {source}"

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return f"成功移动: {source} → {destination}"
    except Exception as e:
        return f"移动失败: {e}"


def _get_file_info(path: Path) -> str:
    """同步获取文件信息"""
    if not path.exists():
        return f"错误: 路径不存在: {path}"

    try:
        st = path.stat()
    except PermissionError:
        return f"错误: 没有权限访问: {path}"

    lines = [f"[文件信息] {path}\n"]
    lines.append(f"  类型:       {'目录' if path.is_dir() else '文件' if path.is_file() else '其他'}")
    if path.is_symlink():
        lines.append(f"  符号链接:   → {path.readlink()}")
    lines.append(f"  大小:       {_format_size(st.st_size) if path.is_file() else '-'}")
    lines.append(f"  权限:       {_format_permissions(st.st_mode)} ({oct(st.st_mode)[-3:]})")
    lines.append(f"  修改时间:   {datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  访问时间:   {datetime.fromtimestamp(st.st_atime).strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  创建时间:   {datetime.fromtimestamp(st.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}")
    if hasattr(st, 'st_uid'):
        lines.append(f"  所有者UID:  {st.st_uid}")
    lines.append(f"  inode:      {st.st_ino}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# MCP Server
# ═══════════════════════════════════════════════════════════

app = Server("aicraft-file-manager")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        READ_FILE_TOOL,
        WRITE_FILE_TOOL,
        EDIT_FILE_TOOL,
        DELETE_FILE_TOOL,
        CREATE_DIRECTORY_TOOL,
        LIST_DIRECTORY_TOOL,
        SEARCH_FILES_TOOL,
        MOVE_FILE_TOOL,
        GET_FILE_INFO_TOOL,
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    loop = asyncio.get_running_loop()

    try:
        if name == "read_file":
            path = _resolve_path(arguments.get("path", ""))
            if not str(path).strip():
                return [TextContent(type="text", text="错误: path 参数不能为空")]
            offset = arguments.get("offset", 0) or 0
            limit = arguments.get("limit", 0) or 0
            output = await loop.run_in_executor(None, _read_file, path, offset, limit)
            return [TextContent(type="text", text=output)]

        elif name == "write_file":
            path = _resolve_path(arguments.get("path", ""))
            content = arguments.get("content", "")
            if not str(path).strip():
                return [TextContent(type="text", text="错误: path 参数不能为空")]
            output = await loop.run_in_executor(None, _write_file, path, content)
            return [TextContent(type="text", text=output)]

        elif name == "edit_file":
            path = _resolve_path(arguments.get("path", ""))
            old_string = arguments.get("old_string", "")
            new_string = arguments.get("new_string", "")
            replace_all = arguments.get("replace_all", False)
            if not str(path).strip():
                return [TextContent(type="text", text="错误: path 参数不能为空")]
            output = await loop.run_in_executor(
                None, _edit_file, path, old_string, new_string, replace_all
            )
            return [TextContent(type="text", text=output)]

        elif name == "delete_file":
            path = _resolve_path(arguments.get("path", ""))
            if not str(path).strip():
                return [TextContent(type="text", text="错误: path 参数不能为空")]
            output = await loop.run_in_executor(None, _delete_file, path)
            return [TextContent(type="text", text=output)]

        elif name == "create_directory":
            path = _resolve_path(arguments.get("path", ""))
            if not str(path).strip():
                return [TextContent(type="text", text="错误: path 参数不能为空")]
            output = await loop.run_in_executor(None, _create_directory, path)
            return [TextContent(type="text", text=output)]

        elif name == "list_directory":
            path = _resolve_path(arguments.get("path", ""))
            if not str(path).strip():
                return [TextContent(type="text", text="错误: path 参数不能为空")]
            output = await loop.run_in_executor(None, _list_directory, path)
            return [TextContent(type="text", text=output)]

        elif name == "search_files":
            path = _resolve_path(arguments.get("path", ""))
            pattern = arguments.get("pattern", "*")
            if not str(path).strip():
                return [TextContent(type="text", text="错误: path 参数不能为空")]
            output = await loop.run_in_executor(None, _search_files, path, pattern)
            return [TextContent(type="text", text=output)]

        elif name == "move_file":
            source = _resolve_path(arguments.get("source", ""))
            destination = _resolve_path(arguments.get("destination", ""))
            if not str(source).strip() or not str(destination).strip():
                return [TextContent(type="text", text="错误: source 和 destination 参数不能为空")]
            output = await loop.run_in_executor(None, _move_file, source, destination)
            return [TextContent(type="text", text=output)]

        elif name == "get_file_info":
            path = _resolve_path(arguments.get("path", ""))
            if not str(path).strip():
                return [TextContent(type="text", text="错误: path 参数不能为空")]
            output = await loop.run_in_executor(None, _get_file_info, path)
            return [TextContent(type="text", text=output)]

        else:
            return [TextContent(type="text", text=f"未知工具: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"工具执行异常: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
