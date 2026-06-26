"""依赖注入 — 单例核心模块实例，各 router 通过 get_deps() 获取"""

from dataclasses import dataclass

from src.core.mcp_client import MCPManager
from src.core.rag_engine import RAGEngine
from src.core.memory import MemoryManager
from src.core.role_loader import RoleLoader
from src.core.skill_loader import SkillLoader
from src.utils.config import (
    APP_CONTEXT_DEFAULT, APP_CONTEXT_PATH,
    DEFAULTS_DIR, WORKSPACE_DIR,
    get_skills_dir, ensure_rag_config, ensure_user_dirs,
)


@dataclass
class AppDeps:
    mcp_manager: MCPManager
    rag_engine: RAGEngine
    memory_manager: MemoryManager
    role_loader: RoleLoader
    skill_loader: SkillLoader


_deps: AppDeps | None = None


def init_deps() -> AppDeps:
    """初始化所有核心模块单例"""
    global _deps

    # 首次启动：创建用户数据目录结构
    ensure_user_dirs()

    # 首次启动：生成默认 app.md 全局上下文文件（如不存在）
    if not APP_CONTEXT_PATH.exists():
        APP_CONTEXT_PATH.write_text(APP_CONTEXT_DEFAULT, encoding="utf-8")

    mcp = MCPManager()
    mcp.load_connections()

    # 首次启动自动导入出厂 MCP 配置
    if not mcp.connections:
        defaults_file = DEFAULTS_DIR / "default_mcp.json"
        if defaults_file.exists():
            import json as _json
            default_data = _json.loads(defaults_file.read_text(encoding="utf-8"))
            workspace_path = str(WORKSPACE_DIR)
            for item in default_data.get("connections", default_data):
                substituted_args = [
                    arg.replace("{workspace_dir}", workspace_path)
                    for arg in item.get("args", [])
                ]
                mcp.add_connection(
                    name=item["name"],
                    conn_type=item.get("type", "stdio"),
                    host=item.get("host", ""),
                    port=item.get("port", 0),
                    url=item.get("url", ""),
                    command=item.get("command", ""),
                    args=substituted_args,
                    env=item.get("env", {}),
                )
    else:
        # ── 迁移：将旧的 npm server-filesystem 替换为 Python 版 file_manager ──
        _migrate_file_manager(mcp)

    rag = RAGEngine()

    # 确保 rag_config.json 存在（从默认模板复制）
    ensure_rag_config()

    rag.load_sources()

    # 首次启动自动导入出厂 RAG 数据源
    if not rag.sources:
        defaults_file = DEFAULTS_DIR / "default_rag.json"
        if defaults_file.exists():
            import json as _json
            default_data = _json.loads(defaults_file.read_text(encoding="utf-8"))
            for item in default_data.get("sources", default_data):
                rag.add_source(
                    name=item["name"],
                    path=item["path"],  # add_source() 内部会 resolve_path
                    source_type=item.get("type", "local"),
                )

    memory = MemoryManager()
    role = RoleLoader()
    role.scan()
    skill = SkillLoader(skill_dir=get_skills_dir())
    skill.scan()
    _deps = AppDeps(
        mcp_manager=mcp,
        rag_engine=rag,
        memory_manager=memory,
        role_loader=role,
        skill_loader=skill,
    )
    return _deps


def _migrate_file_manager(mcp: MCPManager) -> None:
    """将旧版 npm server-filesystem MCP 连接迁移为 Python 版"""
    import json as _json

    for conn in mcp.connections:
        args = conn.args or []
        args_str = " ".join(args)
        if "@modelcontextprotocol/server-filesystem" in args_str:
            # 替换为 Python 版 file_manager
            conn.command = "python"
            conn.args = ["src/mcp_servers/file_manager.py"]
            # 持久化
            mcp.save_connections()


def get_deps() -> AppDeps:
    """获取核心模块单例"""
    assert _deps is not None, "deps not initialized — call init_deps() at startup"
    return _deps
