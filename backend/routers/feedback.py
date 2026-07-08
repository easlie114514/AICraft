"""用户反馈 API — 👍👎 评分存储，为后续 Harness 自我改进积累训练信号"""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from src.utils.config import USER_DIR

router = APIRouter(tags=["feedback"])

FEEDBACK_DIR = USER_DIR / "memory" / "feedback"
FEEDBACK_FILE = FEEDBACK_DIR / "feedback.jsonl"


class FeedbackSubmit(BaseModel):
    conv_id: str        # 对话 ID
    message_id: str     # 消息 ID
    rating: str         # "up" | "down"
    message_preview: str = ""   # AI 回复的前 200 字
    user_message: str = ""      # 对应的用户消息


def _ensure_dir() -> None:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/feedback")
async def submit_feedback(body: FeedbackSubmit):
    """提交用户反馈（👍 或 👎）"""
    if body.rating not in ("up", "down"):
        return {"ok": False, "error": "rating 必须为 'up' 或 'down'"}

    _ensure_dir()

    entry = {
        "timestamp": datetime.now().isoformat(),
        "conv_id": body.conv_id,
        "message_id": body.message_id,
        "rating": body.rating,
        "message_preview": body.message_preview[:200],
        "user_message": body.user_message[:200],
    }

    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    return {"ok": True}


@router.get("/feedback/stats")
async def get_feedback_stats():
    """获取反馈统计"""
    _ensure_dir()

    if not FEEDBACK_FILE.exists():
        return {"total": 0, "up": 0, "down": 0}

    total = 0
    up = 0
    down = 0
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                total += 1
                if entry.get("rating") == "up":
                    up += 1
                elif entry.get("rating") == "down":
                    down += 1
            except json.JSONDecodeError:
                continue

    return {"total": total, "up": up, "down": down}
