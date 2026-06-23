"""记忆管理模块 - 对话历史、项目笔记、智能检索、记忆压缩与合并"""

import json
from datetime import datetime
from pathlib import Path

from src.utils.config import (
    CONVERSATIONS_DIR, NOTES_DIR, MEMORY_DIR,
    load_json, save_json
)
from src.core.context_budget import estimate_tokens


class MemoryManager:
    """记忆管理器 — 分层记忆架构 (L0实时对话 | L1短期compact | L2长期合并)"""

    def __init__(self):
        self.conversations_dir = CONVERSATIONS_DIR
        self.notes_dir = NOTES_DIR

    # ── 对话历史 ──

    def save_conversation(self, project: str, messages: list[dict]) -> None:
        """保存对话历史"""
        conv_dir = self.conversations_dir / project
        conv_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = conv_dir / f"{timestamp}.json"
        save_json(path, {
            "project": project,
            "timestamp": timestamp,
            "messages": messages,
        })

    def load_conversation(self, project: str, filename: str) -> list[dict]:
        """加载指定对话"""
        path = self.conversations_dir / project / filename
        data = load_json(path)
        return data.get("messages", [])

    def list_conversations(self, project: str) -> list[dict]:
        """列出项目的所有对话"""
        conv_dir = self.conversations_dir / project
        if not conv_dir.exists():
            return []
        convs = []
        for f in sorted(conv_dir.glob("*.json"), reverse=True):
            data = load_json(f)
            convs.append({
                "filename": f.name,
                "timestamp": data.get("timestamp", ""),
                "message_count": len(data.get("messages", [])),
            })
        return convs

    def list_projects(self) -> list[str]:
        """列出所有有对话记录的项目"""
        if not self.conversations_dir.exists():
            return []
        return [d.name for d in self.conversations_dir.iterdir() if d.is_dir()]

    # ── 项目笔记 ──

    def list_notes(self) -> list[dict]:
        """列出所有项目笔记"""
        if not self.notes_dir.exists():
            return []
        notes = []
        for f in sorted(self.notes_dir.glob("*.md"), reverse=True):
            content = f.read_text(encoding="utf-8")
            # 区分 compact 和长期记忆
            kind = "long_term" if f.name == "long_term_memory.md" else "compact"
            notes.append({
                "name": f.stem,
                "filename": f.name,
                "preview": content[:100],
                "path": str(f),
                "kind": kind,
                "chars": len(content),
                "tokens": estimate_tokens(content),
            })
        return notes

    def delete_note(self, filename: str) -> bool:
        """删除指定的记忆片段文件"""
        # 安全检查：只允许删除 project-notes 目录下的 .md 文件
        safe_name = Path(filename).name  # 防止路径穿越
        if not safe_name.endswith(".md"):
            return False
        path = self.notes_dir / safe_name
        if path.exists():
            path.unlink()
            return True
        return False

    def load_all_notes(self) -> str:
        """加载所有笔记内容，用于注入prompt（旧接口，保留兼容）"""
        notes = self.list_notes()
        if not notes:
            return ""
        parts = ["\n\n# 项目笔记\n"]
        for note in notes:
            path = Path(note["path"])
            content = path.read_text(encoding="utf-8")
            parts.append(f"\n## {note['name']}\n{content}\n")
        return "\n".join(parts)

    # ── 记忆注入：按预算加载（替代全量注入）──

    def load_memory_for_inject(self, max_chars: int = 4000, strategy: str = "latest") -> str:
        """按预算加载记忆，不再全量注入。

        优先级：长期记忆 > 最近compact片段。
        按时间倒序拼接，超出 max_chars 则截断。

        Args:
            max_chars: 注入的最大字符数
            strategy: "latest"(最近优先) | "relevant"(RAG检索，待实现)

        Returns:
            拼接后的记忆文本，供注入 system prompt
        """
        if strategy == "relevant":
            # RAG 检索注入 — 后续迭代实现，当前降级为 latest
            strategy = "latest"

        parts: list[str] = []
        total = 0

        # 1. 长期记忆优先（更浓缩，优先注入）
        long_term_path = MEMORY_DIR / "long_term_memory.md"
        if long_term_path.exists():
            content = long_term_path.read_text(encoding="utf-8")
            if total + len(content) <= max_chars:
                parts.append(content)
                total += len(content)

        # 2. 最近的compact补充
        compacts = sorted(self.notes_dir.glob("auto_compact_*.md"), reverse=True)
        for f in compacts:
            content = f.read_text(encoding="utf-8")
            remaining = max_chars - total
            if remaining <= 100:
                # 剩余空间太小，不值得截断
                break
            if len(content) <= remaining:
                parts.append(content)
                total += len(content)
            else:
                # 最后一个片段截断到预算内
                parts.append(content[:remaining] + "\n...(已截断)")
                break

        return "\n\n---\n\n".join(parts) if parts else ""

    # ── 记忆统计 ──

    def get_memory_stats(self) -> dict:
        """获取记忆系统统计信息"""
        compacts = sorted(self.notes_dir.glob("auto_compact_*.md"))
        compact_count = len(compacts)
        compact_total_chars = sum(f.stat().st_size for f in compacts)
        compact_total_tokens = 0
        for f in compacts:
            compact_total_tokens += estimate_tokens(f.read_text(encoding="utf-8"))

        long_term_path = MEMORY_DIR / "long_term_memory.md"
        long_term_size = long_term_path.stat().st_size if long_term_path.exists() else 0
        long_term_tokens = 0
        if long_term_path.exists():
            long_term_tokens = estimate_tokens(long_term_path.read_text(encoding="utf-8"))

        return {
            "compact_count": compact_count,
            "compact_total_chars": compact_total_chars,
            "compact_total_tokens": compact_total_tokens,
            "long_term_size": long_term_size,
            "long_term_tokens": long_term_tokens,
        }

    # ── 智能检索（复用RAG） ──

    def search_memory(self, query: str, top_k: int = 5) -> list[str]:
        """在记忆中检索相关内容（复用RAG引擎）"""
        from src.core.rag_engine import RAGEngine
        engine = RAGEngine()
        # 确保memory目录已被索引
        # TODO: 自动索引memory目录
        return engine.search(query, top_k)

    # ── 记忆压缩 ──

    async def compact_memory(
        self, messages: list[dict], model_config: dict,
        role: str = "", window: int = 40, max_tokens: int = 800,
    ) -> str | None:
        """将对话压缩为结构化记忆条目并写入文件

        提取对话中的关键信息（决策、偏好、学到的东西），生成简洁的记忆条目。

        Args:
            messages: 需要压缩的对话消息列表（不含 system prompt）
            model_config: 模型配置（用于调用 LLM 做总结）
            role: 当前角色名称
            window: 压缩时取最近 N 条消息做总结（配置化，替代硬编码20）
            max_tokens: 压缩输出 max_tokens（配置化，替代硬编码500）

        Returns:
            生成的文件路径，失败则返回 None
        """
        if not messages or len(messages) < 2:
            return None

        # 去掉 system 消息，只保留 user/assistant/tool
        filtered = [m for m in messages if m.get("role") != "system"]
        if len(filtered) < 2:
            return None

        # 使用配置的 window 而非硬编码20
        conv_text = "\n".join(
            f"[{m['role']}]: {str(m.get('content', ''))[:300]}"
            for m in filtered[-window:]
        )
        prompt = (
            "你是一个对话记忆压缩器。请从以下对话片段中提取关键信息，"
            "用简洁的要点形式总结（每点一行，只记录事实/决策/偏好/学到的东西）。"
            "不要包含闲聊内容，不要重复已经说过的事情。\n\n"
            "【严格禁止】保留角色的说话风格、方言、口头禅、语气词、性格特征。"
            "只输出纯事实，使用标准中文。\n\n"
            f"{conv_text}\n\n"
            "关键要点："
        )

        try:
            from src.core.llm import simple_completion

            summary = await simple_completion(
                model_config=model_config,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,  # 使用配置的 max_tokens 而非硬编码500
            )
            if not summary.strip():
                return None

            # 写入记忆文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.notes_dir.mkdir(parents=True, exist_ok=True)
            filename = f"auto_compact_{timestamp}.md"
            path = self.notes_dir / filename
            header = (
                f"# 自动记忆压缩 {timestamp}\n\n"
                f"角色: {role}\n\n"
                f"---\n\n"
            )
            path.write_text(header + summary, encoding="utf-8")
            return str(path)
        except Exception:
            return None

    # ── 记忆合并：碎片整合 ──

    async def merge_compacts(self, model_config: dict) -> str | None:
        """合并所有短期compact为长期记忆

        读取 project-notes/ 下所有 auto_compact_*.md 文件，
        用 LLM 合并为一份连贯的长期记忆摘要，写入 long_term_memory.md，
        然后删除已合并的 compact 文件。

        Args:
            model_config: 模型配置（用于调用 LLM 做合并）

        Returns:
            生成的长期记忆文件路径，失败或无可合并内容则返回 None
        """
        compacts = sorted(self.notes_dir.glob("auto_compact_*.md"))
        if not compacts:
            return None

        # 读取所有compact内容
        all_content: list[str] = []
        for f in compacts:
            content = f.read_text(encoding="utf-8")
            if content.strip():
                all_content.append(content)

        if not all_content:
            return None

        merged_text = "\n\n---片段分隔---\n\n".join(all_content)

        # 合并 prompt
        prompt = (
            "你是一个记忆整合器。以下是多段对话记忆压缩片段，它们来自不同时间的对话。\n\n"
            "请将所有内容整合为一份连贯的长期记忆摘要：\n"
            "- 合并重复信息，保留最新版本\n"
            "- 按主题分类（技术决策/用户偏好/项目进度/其他）\n"
            "- 删除已过时或自相矛盾的信息\n"
            "- 每个主题下用要点形式记录\n\n"
            "格式：\n"
            "## [主题名]\n"
            "- 要点1\n"
            "- 要点2\n\n"
            f"片段内容：\n{merged_text}"
        )

        try:
            from src.core.llm import simple_completion

            summary = await simple_completion(
                model_config=model_config,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
            )
            if not summary or not summary.strip():
                return None

            # 写入长期记忆（覆盖式，每次合并都是全量重写）
            long_term_path = MEMORY_DIR / "long_term_memory.md"
            header = "# 长期记忆（自动合并）\n\n"
            long_term_path.write_text(header + summary, encoding="utf-8")

            # 删除已合并的compact
            for f in compacts:
                f.unlink()

            return str(long_term_path)
        except Exception:
            return None
