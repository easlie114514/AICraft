"""对话历史管理 - 按日期保存/加载对话JSON"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.utils.config import CONVERSATIONS_DIR


def _ensure_dir() -> Path:
    """确保对话历史目录存在"""
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    return CONVERSATIONS_DIR


def list_conversations() -> list[dict[str, Any]]:
    """列出所有对话历史文件，按时间倒序"""
    _ensure_dir()
    files = sorted(CONVERSATIONS_DIR.glob("*.json"), reverse=True)
    result = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "id": f.stem,
                "file": str(f),
                "created": data.get("created", ""),
                "model": data.get("model", ""),
                "role": data.get("role", ""),
                "message_count": len(data.get("messages", [])),
            })
        except (json.JSONDecodeError, KeyError):
            pass
    return result


def load_conversation(conv_id: str) -> dict[str, Any] | None:
    """加载指定对话"""
    _ensure_dir()
    path = CONVERSATIONS_DIR / f"{conv_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_conversation(
    messages: list[dict[str, str]],
    model: str = "",
    role: str = "",
    conv_id: str | None = None,
) -> str:
    """保存对话历史，返回对话ID"""
    _ensure_dir()
    if conv_id is None:
        conv_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 保留原始创建时间（不因后续保存而覆盖）
    path = CONVERSATIONS_DIR / f"{conv_id}.json"
    if path.exists():
        try:
            old_data = json.loads(path.read_text(encoding="utf-8"))
            created = old_data.get("created", datetime.now().isoformat())
        except (json.JSONDecodeError, KeyError):
            created = datetime.now().isoformat()
    else:
        created = datetime.now().isoformat()

    data = {
        "id": conv_id,
        "created": created,
        "model": model,
        "role": role,
        "messages": messages,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return conv_id


def delete_conversation(conv_id: str) -> bool:
    """删除指定对话"""
    _ensure_dir()
    path = CONVERSATIONS_DIR / f"{conv_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def get_recent_messages(limit: int = 20) -> list[dict[str, str]]:
    """获取最近的对话消息（跨所有对话），用于注入上下文"""
    _ensure_dir()
    all_msgs = []
    files = sorted(CONVERSATIONS_DIR.glob("*.json"), reverse=True)
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            msgs = data.get("messages", [])
            # 去掉system消息，只保留user/assistant
            msgs = [m for m in msgs if m.get("role") != "system"]
            all_msgs = msgs + all_msgs
            if len(all_msgs) >= limit:
                break
        except (json.JSONDecodeError, KeyError):
            pass
    return all_msgs[-limit:]
