"""角色加载器 - 读取角色md文件，管理system prompt

支持双目录模式：
- 出厂角色（APP_DIR/roles）：打包后只读，随版本发布
- 用户角色（USER_DIR/roles）：用户自建，优先级高于同名出厂角色
"""

from dataclasses import dataclass
from pathlib import Path

from src.utils.config import ROLES_DIR, USER_ROLES_DIR


@dataclass
class Role:
    """角色数据类"""
    name: str
    path: Path
    content: str = ""
    enabled: bool = True
    is_user: bool = False   # 是否为用户自建角色


class RoleLoader:
    """角色加载器 — 合并扫描出厂 + 用户角色目录"""

    def __init__(self, bundled_dir: Path = ROLES_DIR, user_dir: Path = USER_ROLES_DIR):
        self.bundled_dir = bundled_dir     # 出厂角色（打包后只读）
        self.user_dir = user_dir           # 用户自建角色（始终可写）
        self.roles: list[Role] = []

    def scan(self) -> list[Role]:
        """扫描出厂 + 用户角色目录，合并返回

        同名角色以用户版本为准（允许覆盖出厂角色）。
        开发模式下两目录合一，所有角色均视为用户角色（可删除）。
        """
        role_map: dict[str, Role] = {}
        same_dir = (self.user_dir == self.bundled_dir)

        # 1) 先加载出厂角色
        if self.bundled_dir.exists():
            for f in sorted(self.bundled_dir.glob("*.md")):
                content = f.read_text(encoding="utf-8")
                name = f.stem
                # 开发模式（同目录）：统一视为用户角色，允许删除
                role_map[name] = Role(name=name, path=f, content=content, is_user=same_dir)

        # 2) 再加载用户角色（覆盖同名出厂角色）
        if self.user_dir.exists() and not same_dir:
            for f in sorted(self.user_dir.glob("*.md")):
                content = f.read_text(encoding="utf-8")
                name = f.stem
                role_map[name] = Role(name=name, path=f, content=content, is_user=True)

        self.roles = list(role_map.values())
        return self.roles

    @property
    def writable_dir(self) -> Path:
        """返回可写入的角色目录（新建/修改角色用）"""
        return self.user_dir

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
