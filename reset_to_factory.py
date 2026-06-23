"""AICraft 恢复出厂预配置 — 精准清理

保留 (出厂预配置):
  - 4 SKILLs:  代码审查 / 写作助手 / 数据分析 / 翻译助手
  - 2 MCPs:    文件管理 (file_manager.py) / 代码执行 (code_executor.py)
  - 1 RAG源:   使用指导
  - 1 角色:    通用助手
  - ONNX 本地嵌入模型 (models/onnx/)
  - RAG 知识库文档 (rag/使用指导/)

清除:
  - 所有对话历史 + 场景记忆
  - ChromaDB 向量库 (下次启动重建)
  - 额外角色 (大狗等)
  - 用户模型 API 配置
  - 应用设置 / 权限策略 (重建为出厂默认)

用法: python reset_to_factory.py [--yes]
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def reset():
    print("AICraft 恢复出厂预配置")
    print("保留: 4 SKILL | 2 MCP | 1 RAG | 1 角色 | ONNX模型 | RAG文档")
    print()

    # ── 1. 对话 & 记忆 ──
    for d in ["memory/conversations", "memory/project-notes"]:
        dp = ROOT / d
        if dp.exists():
            count = len(list(dp.iterdir()))
            for f in dp.iterdir():
                f.unlink()
            print(f"  [OK] 清空 {count} 文件: {d}")

    # ── 2. ChromaDB 向量库 ──
    chroma = ROOT / "chroma_db"
    if chroma.exists():
        shutil.rmtree(chroma)
        print(f"  [OK] 删除: chroma_db/")

    # ── 3. 额外角色 (只保留 通用助手) ──
    roles_dir = ROOT / "roles"
    keep_roles = {"通用助手.md"}
    for f in roles_dir.glob("*.md"):
        if f.name not in keep_roles:
            f.unlink()
            print(f"  [OK] 删除角色: {f.name}")

    # ── 4. 额外 SKILL (只保留出厂4个) ──
    skills_dir = ROOT / "skills"
    keep_skills = {"代码审查", "写作助手", "数据分析", "翻译助手"}
    for d in skills_dir.iterdir():
        if d.is_dir() and d.name not in keep_skills:
            shutil.rmtree(d)
            print(f"  [OK] 删除技能: {d.name}")

    # ── 5. 用户模型 API 配置 (保留 onnx) ──
    models_dir = ROOT / "models"
    if models_dir.exists():
        for f in models_dir.glob("*.json"):
            f.unlink()
            print(f"  [OK] 删除模型配置: {f.name}")

    # ── 6. 应用配置 ──
    config_files = [
        "config/app.json",
        "config/permissions.json",
        "config/rag_config.json",
        ".version",
    ]
    for f in config_files:
        fp = ROOT / f
        if fp.exists():
            fp.unlink()
            print(f"  [OK] 删除: {f}")

    # ── 7. Profile 配置 ──
    profiles = ROOT / "config/profiles"
    if profiles.exists():
        shutil.rmtree(profiles)
        print(f"  [OK] 删除: config/profiles/")

    # ── 8. RAG sources.json ──
    rag_src = ROOT / "rag/sources.json"
    if rag_src.exists():
        rag_src.unlink()
        print(f"  [OK] 删除: rag/sources.json")

    # ── 9. workspace 清空 (保留 .gitkeep) ──
    ws = ROOT / "workspace"
    if ws.exists():
        for item in ws.iterdir():
            if item.name == ".gitkeep":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        print(f"  [OK] 清空: workspace/")

    # ── 10. 清理 __pycache__ ──
    for pycache in ROOT.rglob("__pycache__"):
        shutil.rmtree(pycache)

    print(f"\n完成! 下次 python run.py 将自动重建出厂配置。")


if __name__ == "__main__":
    if "--yes" in sys.argv or "-y" in sys.argv:
        reset()
    else:
        confirm = input("确认恢复出厂预配置? (y/N): ")
        if confirm.lower() == "y":
            reset()
        else:
            print("已取消。")
