"""Skill加载器 - 扫描Skill目录，读取SKILL.md

支持双目录模式：
- 出厂 Skill（APP_DIR/skills）：打包后只读，随版本发布
- 用户 Skill（USER_DIR/skills）：用户自建/修改，优先级高于同名出厂 Skill
"""

from dataclasses import dataclass, field
from pathlib import Path

from src.utils.config import SKILLS_DIR, USER_SKILLS_DIR, load_json, save_json


@dataclass
class Skill:
    """技能数据类"""
    name: str
    path: Path
    description: str = ""
    enabled: bool = True
    is_user: bool = False   # 是否为用户自建 Skill

    @property
    def skill_md(self) -> Path:
        return self.path / "SKILL.md"

    @property
    def exists(self) -> bool:
        return self.skill_md.exists()


class SkillLoader:
    """技能加载器 — 合并扫描出厂 + 用户 Skill 目录"""

    def __init__(self, skill_dir: Path = SKILLS_DIR, user_dir: Path = USER_SKILLS_DIR):
        self.bundled_dir = skill_dir        # 出厂 Skill（打包后只读）
        self.user_dir = user_dir             # 用户自建 Skill（始终可写）
        self.skills: list[Skill] = []
        self._toggles_path = self.user_dir / "toggles.json"

    def scan(self) -> list[Skill]:
        """扫描出厂 + 用户 Skill 目录，合并返回

        同名 Skill 以用户版本为准（允许覆盖出厂 Skill）。
        开发模式下两目录合一，所有 Skill 均视为用户 Skill。
        """
        skill_map: dict[str, Skill] = {}
        same_dir = (self.user_dir.resolve() == self.bundled_dir.resolve())

        # 1) 先加载出厂 Skill
        if self.bundled_dir.exists():
            for folder in sorted(self.bundled_dir.iterdir()):
                if not folder.is_dir() or folder.name.startswith("."):
                    continue
                skill_md = folder / "SKILL.md"
                if not skill_md.exists():
                    continue
                description = self._extract_description(skill_md)
                skill_map[folder.name] = Skill(
                    name=folder.name,
                    path=folder,
                    description=description,
                    is_user=same_dir,
                )

        # 2) 再加载用户 Skill（覆盖同名出厂 Skill）
        if self.user_dir.exists() and not same_dir:
            for folder in sorted(self.user_dir.iterdir()):
                if not folder.is_dir() or folder.name.startswith("."):
                    continue
                skill_md = folder / "SKILL.md"
                if not skill_md.exists():
                    continue
                description = self._extract_description(skill_md)
                skill_map[folder.name] = Skill(
                    name=folder.name,
                    path=folder,
                    description=description,
                    is_user=True,
                )

        # 3) 应用开关状态（优先从用户目录读取）
        toggles = self._load_toggles()
        for skill in skill_map.values():
            skill.enabled = toggles.get(skill.name, True)

        self.skills = list(skill_map.values())
        return self.skills

    def toggle(self, skill_name: str, enabled: bool) -> None:
        """开关某个Skill"""
        for skill in self.skills:
            if skill.name == skill_name:
                skill.enabled = enabled
                break
        self._save_toggles()

    def get_enabled_skills(self) -> list[Skill]:
        """获取所有已启用的Skill"""
        return [s for s in self.skills if s.enabled]

    def build_skill_prompt(self) -> str:
        """构建注入到system prompt的Skill描述
        只注入名称和简短描述，不注入完整SKILL.md内容，
        防止模型在回复中念出技能描述。
        """
        enabled = self.get_enabled_skills()
        if not enabled:
            return ""

        parts = ["\n\n# 可用技能\n你具备以下技能，当用户问题匹配时可以调用对应工具：\n"]
        for skill in enabled:
            parts.append(f"- {skill.name}：{skill.description}")
        return "\n".join(parts)

    def _extract_description(self, path: Path) -> str:
        """从SKILL.md提取简要描述"""
        try:
            text = path.read_text(encoding="utf-8")
            # 取第一个非空非标题行作为描述
            for line in text.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    return line[:100]
        except Exception:
            pass
        return "无描述"

    def _load_toggles(self) -> dict[str, bool]:
        """加载开关状态"""
        return load_json(self._toggles_path)

    def _save_toggles(self) -> None:
        """保存开关状态（始终写入用户目录）"""
        toggles = {s.name: s.enabled for s in self.skills}
        save_json(self._toggles_path, toggles)
