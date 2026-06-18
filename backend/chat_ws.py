"""WebSocket 聊天处理器 — 流式 LLM 对话 + 工具调用"""

import asyncio
import json
import traceback
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.deps import get_deps
from src.core.agent_loop import agent_loop
from src.core.chat_history import save_conversation, get_recent_messages
from src.core.llm import get_current_model_config, get_model_config
from src.core.web_search import web_search, format_search_results

router = APIRouter(tags=["chat"])


@router.websocket("/chat/ws")
async def chat_websocket(ws: WebSocket):
    await ws.accept()
    deps = get_deps()
    loop = asyncio.get_event_loop()
    # 同一个 WS 会话内的对话历史（保持连续对话上下文）
    session_history: list[dict] = []

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "")

            if msg_type == "stop":
                await ws.send_json({"type": "done"})
                continue

            if msg_type == "message":
                user_text = data.get("content", "")
                model_id = data.get("model_id", "")
                role_name = data.get("role", "")
                toggles = data.get("toggles", {})
                conv_id = data.get("conversation_id", "")

                if not user_text.strip():
                    continue

                # ── 获取模型配置 ──
                model_config = get_model_config(model_id) if model_id else get_current_model_config()
                if not model_config or not model_config.get("model_id"):
                    await ws.send_json({"type": "error", "content": "未配置模型，请先在模型页添加API配置"})
                    continue

                # ── 构建 System Prompt ──
                system_content = deps.role_loader.build_system_prompt(role_name or None)
                skill_prompt = deps.skill_loader.build_skill_prompt()
                if skill_prompt:
                    system_content += "\n" + skill_prompt

                # ── Phase 3 注入 ──
                inject_items = []

                if toggles.get("web_search"):
                    try:
                        results = await loop.run_in_executor(None, web_search, user_text, 5)
                        formatted = format_search_results(results)
                        if formatted:
                            system_content += f"\n\n[联网搜索结果]\n{formatted}"
                            inject_items.append(f"联网搜索: {len(results)} 条结果")
                    except Exception as e:
                        inject_items.append(f"联网搜索失败: {e}")

                if toggles.get("rag"):
                    try:
                        rag_results = await loop.run_in_executor(None, deps.rag_engine.search, user_text, 5)
                        if rag_results:
                            rag_text = "\n\n".join(rag_results)
                            system_content += f"\n\n[RAG检索结果]\n{rag_text}"
                            inject_items.append(f"RAG检索: {len(rag_results)} 条片段")
                    except Exception as e:
                        inject_items.append(f"RAG检索失败: {e}")

                if toggles.get("memory"):
                    try:
                        # 跨会话记忆：从其他历史对话中抽取最近消息
                        cross_memories = await loop.run_in_executor(None, get_recent_messages, 20)
                        if cross_memories:
                            mem_text = "\n".join(
                                f"[{m['role']}]: {m.get('content', '')[:200]}"
                                for m in cross_memories[:10]
                            )
                            system_content += f"\n\n[跨会话记忆]\n{mem_text}"
                            inject_items.append(f"记忆: 已注入 {len(cross_memories)} 条历史")

                        # 项目笔记
                        notes = await loop.run_in_executor(None, deps.memory_manager.load_all_notes)
                        if notes:
                            system_content += f"\n\n[项目笔记]\n{notes}"
                            inject_items.append("记忆: 已注入项目笔记")
                    except Exception as e:
                        inject_items.append(f"记忆注入失败: {e}")

                if inject_items:
                    await ws.send_json({"type": "inject_info", "items": inject_items})

                # ── 组装消息列表 ──
                # 结构: system_prompt + session_history + current_user_message
                messages: list[dict] = [{"role": "system", "content": system_content}]
                messages.extend(session_history)
                messages.append({"role": "user", "content": user_text})

                # ── Agent Loop ──
                mcp_tools = deps.mcp_manager.get_enabled_tools() or None

                try:
                    async for event in agent_loop(
                        messages=messages,
                        tools=mcp_tools,
                        model_config=model_config,
                        mcp_manager=deps.mcp_manager,
                    ):
                        await ws.send_json(event)

                    await ws.send_json({"type": "done"})

                    # ── 更新会话历史（只保留 user 和 assistant 消息）──
                    for m in messages[1:]:  # 跳过 system prompt
                        role = m.get("role", "")
                        if role in ("user", "assistant", "tool"):
                            session_history.append(m)

                    # 裁剪历史：只保留最近 40 条，防止 token 溢出
                    if len(session_history) > 40:
                        session_history = session_history[-40:]

                    # ── 保存对话到磁盘 ──
                    save_data_msgs = [messages[0]] + session_history  # system + 历史
                    save_conversation(
                        messages=save_data_msgs,
                        model=model_config.get("model_id", ""),
                        role=role_name or str(deps.role_loader.get_default_role()),
                        conv_id=conv_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
                    )
                except Exception as e:
                    traceback.print_exc()
                    await ws.send_json({"type": "error", "content": f"对话出错: {str(e)}"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        traceback.print_exc()
        try:
            await ws.send_json({"type": "error", "content": f"服务错误: {str(e)}"})
        except Exception:
            pass
