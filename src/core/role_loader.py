"""角色加载器 - 读取角色md文件，管理system prompt"""

from dataclasses import dataclass
from pathlib import Path

from src.utils.config import ROLES_DIR, load_json, save_json


@dataclass
class Role:
    """角色数据类"""
    name: str
    path: Path
    content: str = ""
    enabled: bool = True


class RoleLoader:
    """角色加载器"""

    def __init__(self, role_dir: Path = ROLES_DIR):
        self.role_dir = role_dir
        self.roles: list[Role] = []

    def scan(self) -> list[Role]:
        """扫描角色目录"""
        roles = []

        if not self.role_dir.exists():
            return roles

        for f in sorted(self.role_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            name = f.stem  # 文件名去掉.md
            roles.append(Role(name=name, path=f, content=content))

        self.roles = roles
        return roles

    def get_role(self, name: str) -> Role | None:
        """按名称获取角色"""
        for role in self.roles:
            if role.name == name:
                return role
        return None

    def get_default_role(self) -> Role | None:
        """获取默认角色（第一个）"""
        return self.roles[0] if self.roles else None

    def build_system_prompt(self, role_name: str | None = None) -> str:
        """构建system prompt"""
        if role_name:
            role = self.get_role(role_name)
        else:
            role = self.get_default_role()

        if role and role.content:
            return role.content
        return "你是AI助手，请用中文回答问题。"
