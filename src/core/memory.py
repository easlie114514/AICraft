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
