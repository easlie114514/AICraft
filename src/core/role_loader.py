"""角色加载器 - 读取角色md文件，管理system prompt

支持双目录模式：
- 出厂角色（APP_DIR/roles）：打包后只读，随版本发布
- 用户角色（USER_DIR/roles）：用户自建，优先级高于同名出厂角色

角色存储格式：
- 新格式（文件夹）：roles/<name>/role.md + emotion.png + emotion.json
- 旧格式（单文件）：roles/<name>.md → scan() 时自动迁移为新格式
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from src.utils.config import ROLES_DIR, USER_ROLES_DIR


@dataclass
class Role:
    """角色数据类"""
    name: str
    path: Path           # 角色文件夹路径（新格式），迁移前短暂为 .md 文件
    content: str = ""
    enabled: bool = True
    is_user: bool = False   # 是否为用户自建角色

    @property
    def prompt_file(self) -> Path:
        """role.md 文件路径"""
        return self.path / "role.md" if self.path.is_dir() else self.path


class RoleLoader:
    """角色加载器 — 合并扫描出厂 + 用户角色目录"""

    def __init__(self, bundled_dir: Path = ROLES_DIR, user_dir: Path = USER_ROLES_DIR):
        self.bundled_dir = bundled_dir     # 出厂角色（打包后只读）
        self.user_dir = user_dir           # 用户自建角色（始终可写）
        self.roles: list[Role] = []

    @property
    def _trash_dir(self) -> Path:
        """软删除标记目录"""
        return self.user_dir / ".trash"

    def _load_role_from_folder(self, folder: Path, is_user: bool) -> Role | None:
        """从文件夹加载新格式角色"""
        md = folder / "role.md"
        if not md.exists():
            return None
        name = folder.name
        content = md.read_text(encoding="utf-8")
        return Role(name=name, path=folder, content=content, is_user=is_user)

    def _migrate_old_format(self, md_file: Path) -> Role | None:
        """将旧格式 .md 文件迁移为新格式文件夹，返回迁移后的 Role

        操作：创建同名文件夹 → 移入 role.md → 删除旧 .md 文件
        失败时返回 None（旧文件保留不丢）
        """
        name = md_file.stem
        folder = md_file.parent / name
        target = folder / "role.md"

        # 如果目标文件夹已存在 role.md，说明已有新格式，删除旧文件即可
        if target.exists():
            try:
                md_file.unlink()
            except OSError:
                pass
            return None  # 由新格式扫描处理

        try:
            folder.mkdir(parents=True, exist_ok=True)
            # 读取内容 → 写入新位置
            content = md_file.read_text(encoding="utf-8")
            target.write_text(content, encoding="utf-8")
            # 删除旧文件
            md_file.unlink()
            return Role(name=name, path=folder, content=content, is_user=True)
        except OSError:
            # 迁移失败，仍按旧格式返回（保证功能不中断）
            content = md_file.read_text(encoding="utf-8")
            return Role(name=name, path=md_file, content=content, is_user=True)

    def scan(self) -> list[Role]:
        """扫描出厂 + 用户角色目录，合并返回

        扫描顺序：
        1. 先扫新格式（roles/*/role.md）
        2. 再扫旧格式（roles/*.md），自动迁移为新格式
        同名角色以用户版本为准（允许覆盖出厂角色）。
        开发模式下两目录合一，所有角色均视为用户角色。
        被软删除的角色（.trash 中有同名标记文件）会被过滤掉。
        """
        role_map: dict[str, Role] = {}
        same_dir = (self.user_dir == self.bundled_dir)

        # 读取软删除标记
        hidden: set[str] = set()
        trash = self._trash_dir
        if trash.exists():
            for f in trash.glob("*.md"):
                hidden.add(f.stem)

        def _scan_dir(directory: Path, is_user: bool) -> None:
            """扫描一个目录下的角色（新格式 + 旧格式自动迁移）"""
            if not directory.exists():
                return

            # 第一步：扫描新格式 roles/*/role.md
            for md in sorted(directory.glob("*/role.md")):
                name = md.parent.name
                if name in hidden:
                    continue
                content = md.read_text(encoding="utf-8")
                role_map[name] = Role(
                    name=name, path=md.parent, content=content,
                    is_user=(same_dir or is_user),
                )

            # 第二步：扫描旧格式 roles/*.md，自动迁移
            for f in sorted(directory.glob("*.md")):
                name = f.stem
                if name in hidden:
                    continue
                # 如果同名新格式已存在，删除残留旧文件后跳过
                if name in role_map:
                    try:
                        f.unlink()
                    except OSError:
                        pass
                    continue
                # 自动迁移
                migrated = self._migrate_old_format(f)
                if migrated:
                    migrated.is_user = (same_dir or is_user)
                    role_map[name] = migrated

        # 1) 先加载出厂角色
        _scan_dir(self.bundled_dir, is_user=False)

        # 2) 再加载用户角色（覆盖同名出厂角色）
        if not same_dir:
            _scan_dir(self.user_dir, is_user=True)

        self.roles = list(role_map.values())
        return self.roles

    @property
    def writable_dir(self) -> Path:
        """返回可写入的角色目录（新建/修改角色用）"""
        return self.user_dir

    def hide_role(self, name: str) -> None:
        """软删除出厂角色——在 .trash 目录下创建同名标记文件"""
        self._trash_dir.mkdir(parents=True, exist_ok=True)
        (self._trash_dir / f"{name}.md").touch()

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
