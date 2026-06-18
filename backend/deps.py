"""依赖注入 — 单例核心模块实例，各 router 通过 get_deps() 获取"""

from dataclasses import dataclass

from src.core.mcp_client import MCPManager
from src.core.rag_engine import RAGEngine
from src.core.memory import MemoryManager
from src.core.role_loader import RoleLoader
from src.core.skill_loader import SkillLoader


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
    mcp = MCPManager()
    mcp.load_connections()
    rag = RAGEngine()
    rag.load_sources()
    memory = MemoryManager()
    role = RoleLoader()
    role.scan()
    skill = SkillLoader()
    skill.scan()
    _deps = AppDeps(
        mcp_manager=mcp,
        rag_engine=rag,
        memory_manager=memory,
        role_loader=role,
        skill_loader=skill,
    )
    return _deps


def get_deps() -> AppDeps:
    """获取核心模块单例"""
    assert _deps is not None, "deps not initialized — call init_deps() at startup"
    return _deps
