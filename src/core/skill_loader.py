"""Skill加载器 - 扫描Skill目录，读取SKILL.md"""

from dataclasses import dataclass, field
from pathlib import Path

from src.utils.config import SKILLS_DIR, load_json, save_json


@dataclass
class Skill:
    """技能数据类"""
    name: str
    path: Path
    description: str = ""
    enabled: bool = True

    @property
    def skill_md(self) -> Path:
        return self.path / "SKILL.md"

    @property
    def exists(self) -> bool:
        return self.skill_md.exists()


class SkillLoader:
    """技能加载器"""

    def __init__(self, skill_dir: Path = SKILLS_DIR):
        self.skill_dir = skill_dir
        self.skills: list[Skill] = []
        self._toggles_path = self.skill_dir / "toggles.json"

    def scan(self) -> list[Skill]:
        """扫描Skill目录，识别所有Skill"""
        toggles = self._load_toggles()
        skills = []

        if not self.skill_dir.exists():
            return skills

        for folder in sorted(self.skill_dir.iterdir()):
            if not folder.is_dir():
                continue
            if folder.name.startswith("."):
                continue
            skill_md = folder / "SKILL.md"
            if not skill_md.exists():
                continue

            # 读取SKILL.md的前几行作为描述
            description = self._extract_description(skill_md)
            enabled = toggles.get(folder.name, True)

            skill = Skill(
                name=folder.name,
                path=folder,
                description=description,
                enabled=enabled,
            )
            skills.append(skill)

        self.skills = skills
        return skills

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
        """保存开关状态"""
        toggles = {s.name: s.enabled for s in self.skills}
        from src.utils.config import save_json
        save_json(self._toggles_path, toggles)
