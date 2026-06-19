"""WebSocket 聊天处理器 — 流式 LLM 对话 + 工具调用"""

import asyncio
import json
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.deps import get_deps
from src.core.agent_loop import agent_loop
from src.core.chat_history import save_conversation, get_recent_messages
from src.core.llm import get_current_model_config, get_model_config
from src.core.web_search import WEB_SEARCH_TOOL
from src.utils.config import get_context_config


def _count_chars(messages: list[dict]) -> int:
    """计算消息列表的总字符数（用于裁剪判断）"""
    total = 0
    for m in messages:
        content = m.get("content", "") or ""
        total += len(content)
    return total


def _trim_history(history: list[dict], max_chars: int) -> list[dict]:
    """从旧到新保留消息，直到超出 max_chars，返回保留的部分"""
    if not history:
        return history
    kept: list[dict] = []
    total = 0
    for m in reversed(history):
        content = m.get("content", "") or ""
        total += len(content)
        if total > max_chars and kept:
            break
        kept.insert(0, m)
    return kept

router = APIRouter(tags=["chat"])


@router.websocket("/chat/ws")
async def chat_websocket(ws: WebSocket):
    await ws.accept()
    deps = get_deps()
    loop = asyncio.get_event_loop()
    # 同一个 WS 会话内的对话历史（保持连续对话上下文）
    session_history: list[dict] = []
    current_role: str = ""  # 追踪当前角色，用于检测角色切换

    # ── 记忆压缩状态（独立于聊天历史）──
    memory_char_counter = 0  # 自上次压缩以来的对话增量字符数
    ctx_config = get_context_config()

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

                # ── 刷新上下文配置（支持热更新）──
                ctx_config = get_context_config()
                max_history_chars = int(ctx_config["max_history_chars"])
                memory_compact_interval = int(ctx_config["memory_compact_interval_chars"])
                memory_compact_enabled = bool(ctx_config["memory_compact_enabled"])

                # ── 角色切换检测 ──
                new_role = role_name or str(deps.role_loader.get_default_role())
                if current_role and new_role != current_role:
                    await ws.send_json({
                        "type": "inject_info",
                        "items": [f"角色切换: {current_role} → {new_role}（正在提取对话记忆...）"]
                    })

                    # 用 LLM 提取对话中的事实信息（去掉语气/风格/角色口癖）
                    context_summary = ""
                    if session_history:
                        try:
                            conv_text = "\n".join(
                                f"[{m.get('role', '?')}]: {str(m.get('content', ''))[:500]}"
                                for m in session_history[-30:]
                                if m.get("role") in ("user", "assistant")
                            )
                            summary_prompt = (
                                "从以下对话中提取纯事实信息（不要任何风格/语气/角色特征）：\n"
                                "- 用户在说什么话题/问题/任务\n"
                                "- 已经做了哪些操作、有什么结果\n"
                                "- 用户表达了什么偏好/需求\n"
                                "- 任何需要记住的上下文信息\n"
                                "用要点形式输出，只写事实，不要任何角色的口吻。\n\n"
                                f"{conv_text}"
                            )
                            summary_kwargs: dict = {
                                "model": model_config.get("model_id", ""),
                                "messages": [{"role": "user", "content": summary_prompt}],
                                "max_tokens": 400,
                            }
                            for key in ("api_key", "api_base"):
                                val = model_config.get(key, "")
                                if val:
                                    summary_kwargs[key] = val
                            import litellm as _litellm
                            response = await _litellm.acompletion(**summary_kwargs)
                            context_summary = response.choices[0].message.content or ""
                        except Exception:
                            context_summary = ""

                    # 清空旧历史（丢掉旧角色语气）
                    session_history.clear()

                    # 重建 system prompt：角色事实摘要 + 新角色设定
                    system_content = (
                        f"【角色切换】你现在是 '{new_role}'，100% 按此角色行事。\n"
                        f"忘记之前的所有角色设定和说话方式。\n"
                    )
                    if context_summary:
                        system_content += (
                            f"\n[之前的对话内容摘要（纯事实，不含角色风格）]\n"
                            f"{context_summary}\n"
                            f"---\n\n"
                        )
                    system_content += deps.role_loader.build_system_prompt(role_name or None)
                    system_content += f"\n\n当前日期时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}"

                    await ws.send_json({
                        "type": "inject_info",
                        "items": [f"角色切换完成: {current_role} → {new_role}（记忆已保留，风格已重置）"]
                    })
                else:
                    system_content = deps.role_loader.build_system_prompt(role_name or None)
                    system_content += f"\n\n当前日期时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}"
                current_role = new_role

                # 注入技能 prompt
                skill_prompt = deps.skill_loader.build_skill_prompt()
                if skill_prompt:
                    system_content += "\n" + skill_prompt
                inject_items = []

                if toggles.get("rag"):
                    try:
                        rag_results = await loop.run_in_executor(None, deps.rag_engine.search, user_text, 5)
                        if rag_results:
                            rag_text = "\n\n".join(rag_results)
                            system_content += (
                                "\n\n[知识库检索结果 — 供参考，基于这些信息回答。"
                                "如果片段中没有相关信息请如实说明，不要编造。]\n"
                                + rag_text
                            )
                            inject_items.append(f"RAG检索: {len(rag_results)} 条片段")
                    except Exception as e:
                        inject_items.append(f"RAG检索失败: {e}")

                if toggles.get("memory"):
                    try:
                        # 跨会话记忆：注入其他会话的最近消息，排除当前session已包含的
                        cross_memories = await loop.run_in_executor(None, get_recent_messages, 10)
                        # 过滤掉当前session已包含的消息（按内容去重）
                        session_contents = {m.get("content", "") for m in session_history if m.get("role") in ("user", "assistant")}
                        unique_memories = [m for m in cross_memories if m.get("content", "") not in session_contents]
                        if unique_memories:
                            mem_text = "\n".join(
                                f"[{m['role']}]: {m.get('content', '')[:200]}"
                                for m in unique_memories[:10]
                            )
                            system_content += (
                                "\n\n[跨会话记忆 — 之前的对话片段，供参考，"
                                "不要在回复中提及你看到了这些内容，自然运用即可。]\n"
                                + mem_text
                            )
                            inject_items.append(f"记忆: 已注入 {len(unique_memories)} 条历史")

                        # 项目笔记
                        notes = await loop.run_in_executor(None, deps.memory_manager.load_all_notes)
                        if notes:
                            system_content += (
                                "\n\n[项目笔记 — 供参考，"
                                "不要在回复中提及你看到了笔记，自然运用相关信息即可。]\n"
                                + notes
                            )
                            inject_items.append("记忆: 已注入项目笔记")
                    except Exception as e:
                        inject_items.append(f"记忆注入失败: {e}")

                # ── 行为约束（固定尾部约束，防止幻觉和失控）──
                system_content += (
                    "\n\n# 行为约束\n"
                    "- 不要编造你不知道的信息，不知道就说不知道\n"
                    "- 不要编造工具调用结果，只有真正执行了工具才能报告结果\n"
                    "- 如果工具调用失败，如实告知用户失败原因\n"
                    "- 不要在回复中提及你看到了注入的笔记、搜索结果等内容\n"
                    f"- 当前时间是{datetime.now().strftime('%Y年%m月%d日 %H:%M')}，不要编造日期和时间\n\n"
                    "# 搜索权威源指引\n"
                    "调用web_search时，关键词必须包含该领域的权威来源站名，确保搜索到可靠数据：\n"
                    "- 天气：关键词加'中国天气网'或'weather.com.cn'\n"
                    "- 金价/贵金属：关键词加'东方财富'或'上海黄金交易所'\n"
                    "- 股票/基金：关键词加'东方财富'或'同花顺'\n"
                    "- 汇率：关键词加'中国银行'或'东方财富'\n"
                    "- 国内新闻：关键词加'新华社'或'央视新闻'或'人民日报'\n"
                    "- 国际新闻：关键词加'央视新闻'或'环球时报'\n"
                    "- 科技资讯：关键词加'36氪'或'虎嗅'或'IT之家'\n"
                    "- 百科/科普：关键词加'维基百科'或'百度百科'\n"
                    "- 学术论文：关键词加'中国知网'或'Google Scholar'\n"
                    "- 政策法规：关键词加'中国政府网'或'国务院'\n"
                    "- 不知道权威源时，优先引用gov.cn/.edu.cn/官方域名的内容"
                )

                if inject_items:
                    await ws.send_json({"type": "inject_info", "items": inject_items})

                # ── 组装消息列表 ──
                # 结构: system_prompt + session_history + current_user_message
                messages: list[dict] = [{"role": "system", "content": system_content}]
                messages.extend(session_history)
                messages.append({"role": "user", "content": user_text})

                # ── Agent Loop ──
                tools: list[dict] = list(deps.mcp_manager.get_enabled_tools() or [])
                # 联网搜索始终作为 function-calling 工具可用，模型自行判断是否需要搜索
                tools.append(WEB_SEARCH_TOOL)

                # 当没有 MCP 工具可用时注入提示
                mcp_tools = deps.mcp_manager.get_enabled_tools() or []
                if not mcp_tools:
                    system_content += (
                        "\n\n# 工具状态\n"
                        "你当前没有 MCP 外部工具可用（读写文件、执行命令等），不要编造工具调用。"
                        "如果需要执行本地操作，请告知用户需要启用对应 MCP 工具。"
                        "你仍然可以使用联网搜索功能来查找信息。"
                    )

                all_tools = tools if tools else None  # None 表示无工具，减少 litellm 开销

                try:
                    async for event in agent_loop(
                        messages=messages,
                        tools=all_tools,
                        model_config=model_config,
                        mcp_manager=deps.mcp_manager,
                    ):
                        await ws.send_json(event)

                    await ws.send_json({"type": "done"})

                    # ── 更新会话历史（只保留 user 和 assistant 消息）──
                    new_char_count = 0
                    for m in messages[1:]:  # 跳过 system prompt
                        role = m.get("role", "")
                        if role in ("user", "assistant", "tool"):
                            session_history.append(m)
                            new_char_count += len(str(m.get("content", "")) or "")

                    # ── 聊天历史裁剪（按字符数，替代硬编码40条）──
                    session_history = _trim_history(session_history, max_history_chars)

                    # ── 保存对话到磁盘（完整保存，不受裁剪影响）──
                    save_data_msgs = [messages[0]] + session_history
                    save_conversation(
                        messages=save_data_msgs,
                        model=model_config.get("model_id", ""),
                        role=role_name or str(deps.role_loader.get_default_role()),
                        conv_id=conv_id or datetime.now().strftime("%Y%m%d_%H%M%S"),
                    )

                    # ── 记忆压缩（独立于聊天历史，每 N 字符触发一次）──
                    if memory_compact_enabled:
                        memory_char_counter += new_char_count
                        if memory_char_counter >= memory_compact_interval:
                            memory_char_counter = 0  # 先重置，避免并发触发

                            async def _compact():
                                try:
                                    path = await deps.memory_manager.compact_memory(
                                        list(session_history),
                                        model_config,
                                        role_name or str(deps.role_loader.get_default_role()),
                                    )
                                    if path:
                                        await ws.send_json({
                                            "type": "inject_info",
                                            "items": [f"记忆: 已压缩到 memory/project-notes/{Path(path).name}"]
                                        })
                                except Exception:
                                    pass

                            asyncio.create_task(_compact())
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
