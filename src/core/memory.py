"""记忆管理模块 - 对话历史、项目笔记、智能检索"""

import json
from datetime import datetime
from pathlib import Path

from src.utils.config import (
    CONVERSATIONS_DIR, NOTES_DIR, MEMORY_DIR,
    load_json, save_json
)


class MemoryManager:
    """记忆管理器"""

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
        for f in sorted(self.notes_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8")
            notes.append({
                "name": f.stem,
                "filename": f.name,
                "preview": content[:100],
                "path": str(f),
            })
        return notes

    def load_all_notes(self) -> str:
        """加载所有笔记内容，用于注入prompt"""
        notes = self.list_notes()
        if not notes:
            return ""
        parts = ["\n\n# 项目笔记\n"]
        for note in notes:
            path = Path(note["path"])
            content = path.read_text(encoding="utf-8")
            parts.append(f"\n## {note['name']}\n{content}\n")
        return "\n".join(parts)

    # ── 智能检索（复用RAG） ──

    def search_memory(self, query: str, top_k: int = 5) -> list[str]:
        """在记忆中检索相关内容（复用RAG引擎）"""
        from src.core.rag_engine import RAGEngine
        engine = RAGEngine()
        # 确保memory目录已被索引
        # TODO: 自动索引memory目录
        return engine.search(query, top_k)

    # ── 记忆压缩 ──

    async def compact_memory(self, messages: list[dict], model_config: dict, role: str = "") -> str | None:
        """将对话压缩为结构化记忆条目并写入文件

        提取对话中的关键信息（决策、偏好、学到的东西），生成简洁的记忆条目。

        Args:
            messages: 需要压缩的对话消息列表（不含 system prompt）
            model_config: 模型配置（用于调用 LLM 做总结）
            role: 当前角色名称

        Returns:
            生成的文件路径，失败则返回 None
        """
        if not messages or len(messages) < 2:
            return None

        # 去掉 system 消息，只保留 user/assistant/tool
        filtered = [m for m in messages if m.get("role") != "system"]
        if len(filtered) < 2:
            return None

        # 生成压缩提示
        conv_text = "\n".join(
            f"[{m['role']}]: {str(m.get('content', ''))[:300]}"
            for m in filtered[-20:]  # 只取最近20条做总结
        )
        prompt = (
            "你是一个对话记忆压缩器。请从以下对话片段中提取关键信息，"
            "用简洁的要点形式总结（每点一行，只记录事实/决策/偏好/学到的东西）。"
            "不要包含闲聊内容，不要重复已经说过的事情。\n\n"
            f"{conv_text}\n\n"
            "关键要点："
        )

        try:
            import litellm
            api_key = model_config.get("api_key", "")
            api_base = model_config.get("api_base", "")
            kwargs: dict = {
                "model": model_config.get("model_id", ""),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
            }
            if api_key:
                kwargs["api_key"] = api_key
            if api_base:
                kwargs["api_base"] = api_base

            response = await litellm.acompletion(**kwargs)
            summary = response.choices[0].message.content or ""
            if not summary.strip():
                return None

            # 写入记忆文件
            from datetime import datetime
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
