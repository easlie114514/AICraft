"""WebSocket 聊天处理器 — 流式 LLM 对话 + 工具调用"""

import asyncio
import json
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.deps import get_deps
from src.core.agent_loop import agent_loop
from src.core.chat_history import save_conversation, load_conversation, get_recent_messages
from src.core.llm import get_current_model_config, get_model_config, simple_completion
from src.core.model_selector import select_model_for_task, select_model_auto
from src.core.context_budget import ContextBudget
from src.core.permission_guard import PermissionGuard
from src.core.token_tracker import token_tracker
from src.utils.config import get_context_config, NOTES_DIR


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

async def _compact_current_scene(
    history: list[dict],
    model_config: dict,
    role_name: str,
) -> None:
    """场景切换时全量压缩 — 不限 window，归档整个场景"""
    try:
        from src.core.llm import simple_completion

        # 全量文本（不限制 window）
        conv_text = "\n".join(
            f"[{m.get('role', '?')}]: {str(m.get('content', ''))[:300]}"
            for m in history
            if m.get('role') in ('user', 'assistant', 'tool')
        )
        if not conv_text.strip():
            return

        prompt = (
            "你是一个场景记忆归档器。以下是一段完整对话场景的全部内容。\n\n"
            "请提取：\n"
            "1. 用户的核心目标/任务\n"
            "2. 已完成的进度和关键决策\n"
            "3. 值得跨场景记住的用户偏好\n"
            "4. 技术细节（如果涉及代码/配置）\n\n"
            "【严格禁止】\n"
            "- 保留任何角色的说话风格、方言、口头禅、语气词\n"
            "- 保留角色的性格特征或情绪表达\n"
            "- 使用非标准普通话的表述\n\n"
            "用要点形式输出，每点一行。不要包含闲聊。\n\n"
            f"{conv_text}\n\n"
            "场景归档："
        )

        summary = await simple_completion(
            model_config=model_config,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
        )

        if summary and summary.strip():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            NOTES_DIR.mkdir(parents=True, exist_ok=True)
            path = NOTES_DIR / f"scene_compact_{timestamp}.md"
            path.write_text(
                f"# 场景记忆归档 {timestamp}\n"
                f"角色: {role_name}\n\n---\n\n{summary}",
                encoding="utf-8",
            )
    except Exception:
        pass


router = APIRouter(tags=["chat"])


@router.websocket("/chat/ws")
async def chat_websocket(ws: WebSocket):
    await ws.accept()
    deps = get_deps()
    loop = asyncio.get_event_loop()

    # ── 权限守卫 ──
    permission_guard = PermissionGuard()
    permission_guard.set_ws_send_fn(lambda data: ws.send_json(data))
    # 同一个 WS 会话内的对话历史（保持连续对话上下文）
    session_history: list[dict] = []
    current_role: str = ""  # 追踪当前角色，用于检测角色切换
    current_conv_id: str = ""  # 追踪当前会话 ID，防御前端残留旧 conv_id 导致历史被重新加载

    # ── 记忆压缩状态（独立于聊天历史）──
    memory_char_counter = 0   # 自上次压缩以来的对话增量字符数
    memory_msg_counter = 0    # 自上次压缩以来的对话增量消息数
    ctx_config = get_context_config()

    # ── 消息队列：后台 Reader 持续读取 WS 消息，权限响应即时处理 ──
    # 关键设计：permission_response 必须在后台即时处理，因为主循环
    # 可能在 agent_loop 中阻塞等待权限 future，无法回到 while 顶部接收消息。
    message_queue: asyncio.Queue = asyncio.Queue()
    _stop_event = asyncio.Event()

    async def ws_reader():
        """后台任务：持续读取 WebSocket 消息"""
        try:
            while not _stop_event.is_set():
                raw = await ws.receive_text()
                data = json.loads(raw)
                msg_type = data.get("type", "")

                # 权限响应 → 立即处理，不进入队列（避免主循环阻塞时积压）
                if msg_type == "permission_response":
                    req_id = data.get("id", "")
                    action = data.get("action", "deny")
                    found = permission_guard.handle_response(req_id, action)
                    if not found:
                        await ws.send_json({
                            "type": "inject_info",
                            "items": [f"权限请求 {req_id} 已过期或不存在"]
                        })
                    continue

                await message_queue.put(data)
        except WebSocketDisconnect:
            await message_queue.put({"type": "_disconnect"})
        except Exception:
            await message_queue.put({"type": "_disconnect"})

    reader_task = asyncio.create_task(ws_reader())

    try:
        while True:
            data = await message_queue.get()
            msg_type = data.get("type", "")

            if msg_type == "_disconnect":
                break

            if msg_type == "stop":
                await ws.send_json({"type": "done"})
                continue

            if msg_type == "new_scene":
                # 场景切换：全量压缩当前对话 → 清空上下文 → 新 conv_id
                if session_history:
                    sc_role = current_role
                    sc_history = list(session_history)
                    # 使用当前配置的模型做压缩（降级到 Flash）
                    try:
                        sc_model_config = get_current_model_config()
                        compact_model = select_model_for_task("memory_compact", sc_model_config)
                        asyncio.create_task(_compact_current_scene(sc_history, compact_model, sc_role))
                    except Exception:
                        pass

                session_history.clear()
                memory_char_counter = 0
                memory_msg_counter = 0
                token_tracker.reset_current()
                new_conv_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                current_conv_id = new_conv_id  # 更新会话级 conv_id，防御前端残留旧 ID

                await ws.send_json({
                    "type": "token_stats",
                    "data": token_tracker.get_stats(),
                })
                await ws.send_json({
                    "type": "conv_id",
                    "id": new_conv_id,
                })
                await ws.send_json({
                    "type": "inject_info",
                    "items": [f"新场景已创建，上下文已重置"]
                })
                continue

            if msg_type == "load_conv":
                # ── 加载指定对话（用于重启后恢复显示）──
                load_conv_id = data.get("conv_id", "")
                if not load_conv_id:
                    # 没有指定 conv_id → 自动找最近的对话
                    from src.core.chat_history import list_conversations
                    conv_list = await loop.run_in_executor(None, list_conversations)
                    if conv_list:
                        load_conv_id = conv_list[0]["id"]
                if load_conv_id:
                    try:
                        saved = await loop.run_in_executor(None, load_conversation, load_conv_id)
                        if saved and saved.get("messages"):
                            # 发送消息给前端展示（排除 tool，前端不单独展示工具调用）
                            # 旧对话可能没有每条消息的 timestamp，用对话 created 兜底
                            fallback_ts = saved.get("created", "")
                            display_msgs: list[dict] = []
                            for m in saved["messages"]:
                                r = m.get("role", "")
                                if r in ("user", "assistant"):
                                    display_msgs.append({
                                        "role": r,
                                        "content": m.get("content", ""),
                                        "timestamp": m.get("timestamp", "") or fallback_ts,
                                    })
                            if display_msgs:
                                await ws.send_json({
                                    "type": "conv_loaded",
                                    "conv_id": load_conv_id,
                                    "role": saved.get("role", ""),
                                    "model": saved.get("model", ""),
                                    "messages": display_msgs,
                                })
                                # 同时填充 session_history，确保后续对话上下文连贯
                                current_role = saved.get("role", "")
                                session_history.clear()
                                for m in saved["messages"]:
                                    r = m.get("role", "")
                                    if r in ("user", "assistant", "tool"):
                                        session_history.append(m)
                        else:
                            await ws.send_json({"type": "error", "content": f"对话 {load_conv_id} 不存在"})
                    except Exception:
                        await ws.send_json({"type": "error", "content": "加载对话失败"})
                continue

            if msg_type == "get_token_stats":
                stats = token_tracker.get_stats()
                await ws.send_json({"type": "token_stats", "data": stats})
                continue

            if msg_type == "reset_token_stats":
                token_tracker.reset_current()
                stats = token_tracker.get_stats()
                await ws.send_json({"type": "token_stats", "data": stats})
                continue

            if msg_type == "message":
                user_text = data.get("content", "")
                model_id = data.get("model_id", "")
                role_name = data.get("role", "")
                toggles = data.get("toggles", {})
                thinking_enabled = toggles.get("thinking", False)
                conv_id = data.get("conversation_id", "")

                if not user_text.strip():
                    continue

                # ── 获取模型配置 ──
                model_config = get_model_config(model_id) if model_id else get_current_model_config()

                # ── Auto路由 ──
                if model_id == "auto":
                    has_mcp_tools = bool(deps.mcp_manager.get_enabled_tools())
                    model_config, auto_reason = select_model_auto(
                        user_message=user_text,
                        toggles=toggles,
                        has_mcp_tools=has_mcp_tools,
                        user_model_config=model_config or get_current_model_config(),
                    )
                    tier_name = (
                        "Pro" if model_config.get("tier") == "pro"
                        else "Flash" if model_config.get("tier") == "flash"
                        else ""
                    )
                    await ws.send_json({
                        "type": "inject_info",
                        "items": [f"⚡ Auto路由 → {model_config.get('name', tier_name)}（{auto_reason}）"]
                    })

                if not model_config or not model_config.get("model_id"):
                    await ws.send_json({"type": "error", "content": "未配置模型，请先在模型页添加API配置"})
                    continue

                # ── 会话 ID 管理 ──
                if not conv_id:
                    conv_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                    current_conv_id = conv_id
                    await ws.send_json({"type": "conv_id", "id": conv_id})
                elif current_conv_id and conv_id != current_conv_id:
                    # 前端残留旧 conv_id（new_scene 后 localStorage 未更新），用当前 ID 覆盖
                    conv_id = current_conv_id
                elif not session_history:
                    # WS 重连后恢复历史（仅当角色匹配）
                    try:
                        saved = await loop.run_in_executor(None, load_conversation, conv_id)
                        if saved and saved.get("messages"):
                            saved_role = saved.get("role", "")
                            if saved_role == role_name:
                                for m in saved["messages"]:
                                    r = m.get("role", "")
                                    if r in ("user", "assistant", "tool"):
                                        session_history.append(m)
                                if session_history:
                                    current_conv_id = conv_id  # 恢复后记录当前 ID
                                    await ws.send_json({
                                        "type": "inject_info",
                                        "items": [f"已恢复对话 ({len(session_history)} 条消息)"]
                                    })
                            else:
                                # 角色变了，旧消息风格不兼容，生成新 conv_id
                                conv_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                                current_conv_id = conv_id
                                await ws.send_json({"type": "conv_id", "id": conv_id})
                    except Exception:
                        pass

                # ── 刷新上下文配置（支持热更新）──
                ctx_config = get_context_config()
                max_history_chars = int(ctx_config["max_history_chars"])
                memory_compact_enabled = bool(ctx_config["memory_compact_enabled"])
                memory_compact_trigger = str(ctx_config["memory_compact_trigger"])
                memory_compact_interval_chars = int(ctx_config["memory_compact_interval_chars"])
                memory_compact_interval_msgs = int(ctx_config["memory_compact_interval_msgs"])
                memory_compact_window = int(ctx_config["memory_compact_window"])
                memory_compact_max_tokens = int(ctx_config["memory_compact_max_tokens"])
                memory_merge_threshold = int(ctx_config["memory_merge_threshold"])
                memory_inject_max_chars = int(ctx_config["memory_inject_max_chars"])
                cross_session_inject_count = int(ctx_config["cross_session_inject_count"])
                context_budget_enabled = bool(ctx_config["context_budget_enabled"])
                context_window_override = int(ctx_config["context_window_override"])
                output_reserve_ratio = float(ctx_config["output_reserve_ratio"])
                budget_alert_threshold = float(ctx_config["budget_alert_threshold"])

                # ── 角色切换检测 ──
                new_role = role_name or str(deps.role_loader.get_default_role())
                if current_role and new_role != current_role:
                    await ws.send_json({
                        "type": "inject_info",
                        "items": [f"角色切换: {current_role} → {new_role}（正在提取对话记忆...）"]
                    })

                    # 用 LLM 提取对话中的事实信息（彻底去掉语气/风格/方言/角色口癖）
                    context_summary = ""
                    if session_history:
                        try:
                            conv_text = "\n".join(
                                f"[{'用户' if m.get('role') == 'user' else '上一角色'}]: {str(m.get('content', ''))[:500]}"
                                for m in session_history[-30:]
                                if m.get("role") in ("user", "assistant")
                            )
                            summary_prompt = (
                                "从以下对话中提取纯事实信息。\n\n"
                                "【必须保留的内容】\n"
                                "- 用户在说什么话题/问题/任务\n"
                                "- 已经做了哪些操作、有什么结果\n"
                                "- 用户表达了什么偏好/需求\n"
                                "- 任何需要跨角色记住的上下文信息\n\n"
                                "【严格禁止保留的内容】\n"
                                "- 任何角色的说话风格、方言（如粤语、东北话）\n"
                                "- 语气词和口头禅（如喵喵、呜哇、哈哈哈）\n"
                                "- 角色的性格特征和情绪表达方式\n"
                                "- 上一角色的任何形式特征、口癖、习惯用语\n"
                                "- 禁止使用任何非标准普通话的表述\n\n"
                                "用要点形式输出，只写纯事实。如果对话中没有值得跨角色记住的内容，"
                                "只输出「无重要信息」。\n\n"
                                f"{conv_text}"
                            )
                            # 角色切换摘要 → 使用用户当前模型（不用 Flash，确保去风格彻底）
                            context_summary = await simple_completion(
                                model_config=model_config,
                                messages=[{"role": "user", "content": summary_prompt}],
                                max_tokens=400,
                            )
                            # 如果 LLM 返回 "无重要信息"，直接丢弃摘要
                            if context_summary and "无重要信息" in context_summary:
                                context_summary = ""
                        except Exception:
                            context_summary = ""

                    # 清空旧历史（丢掉旧角色语气）
                    session_history.clear()

                    # 重建 system prompt：角色事实摘要 + 新角色设定 + 风格防火墙
                    system_pieces: list[tuple[str, str, int]] = []
                    system_pieces.append((
                        "role_switch_notice",
                        f"【角色切换】你现在的身份是 '{new_role}'，必须 100% 按此角色行事。\n"
                        f"完全丢弃上一角色的说话方式、方言、口头禅、语气词、性格特征。\n"
                        f"不要模仿、继承、混合任何旧角色的风格。你只拥有新角色的设定。",
                        1
                    ))
                    if context_summary:
                        system_pieces.append((
                            "role_summary",
                            f"[之前的对话内容摘要（纯事实，不含角色风格）]\n{context_summary}\n---",
                            1
                        ))
                    system_pieces.append((
                        "role_prompt",
                        deps.role_loader.build_system_prompt(role_name or None),
                        1
                    ))
                    system_pieces.append((
                        "date_info",
                        f"当前日期时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}",
                        1
                    ))

                    await ws.send_json({
                        "type": "inject_info",
                        "items": [f"角色切换完成: {current_role} → {new_role}（记忆已保留，风格已重置）"]
                    })
                else:
                    system_pieces: list[tuple[str, str, int]] = []
                    system_pieces.append((
                        "role_prompt",
                        deps.role_loader.build_system_prompt(role_name or None),
                        1
                    ))
                    system_pieces.append((
                        "date_info",
                        f"当前日期时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}",
                        1
                    ))
                current_role = new_role

                # 注入技能 prompt
                skill_prompt = deps.skill_loader.build_skill_prompt()
                if skill_prompt:
                    system_pieces.append(("skill_prompt", skill_prompt, 2))
                inject_items = []

                if toggles.get("rag"):
                    try:
                        rag_results = await loop.run_in_executor(None, deps.rag_engine.search, user_text, 5)
                        if rag_results:
                            rag_text = "\n\n".join(rag_results)
                            system_pieces.append((
                                "rag_results",
                                "[知识库内容 — 以下是从你的知识库中检索到的相关文档片段，"
                                "这些内容就是用户的知识库。请基于这些内容直接回答用户问题。"
                                "不要使用工具去查找其他文件或目录，知识库的内容已经在这里了。"
                                "如果检索结果确实与问题无关，如实告知即可。]\n"
                                + rag_text,
                                3
                            ))
                            inject_items.append(f"RAG检索: {len(rag_results)} 条片段")
                    except Exception as e:
                        inject_items.append(f"RAG检索失败: {e}")

                if toggles.get("memory"):
                    try:
                        # 跨会话记忆：注入其他会话的最近用户消息（仅 user，避免其他角色风格污染）
                        cross_memories = await loop.run_in_executor(None, get_recent_messages, cross_session_inject_count * 2)
                        # 只保留 user 消息（assistant 来自不同角色会污染风格）
                        cross_memories = [m for m in cross_memories if m.get("role") == "user"]
                        # 过滤掉当前session已包含的消息（按内容去重）
                        session_contents = {m.get("content", "") for m in session_history if m.get("role") == "user"}
                        unique_memories = [m for m in cross_memories if m.get("content", "") not in session_contents]
                        if unique_memories:
                            mem_text = "\n".join(
                                f"[用户]: {m.get('content', '')[:200]}"
                                for m in unique_memories[:cross_session_inject_count]
                            )
                            system_pieces.append((
                                "cross_session_memory",
                                "[跨会话记忆 — 之前的对话片段，供参考，"
                                "不要在回复中提及你看到了这些内容，自然运用即可。]\n"
                                + mem_text,
                                5
                            ))
                            inject_items.append(f"记忆: 已注入 {len(unique_memories)} 条历史")

                        # 项目笔记：按预算注入（替代全量注入）
                        notes = await loop.run_in_executor(
                            None, deps.memory_manager.load_memory_for_inject, memory_inject_max_chars
                        )
                        if notes:
                            system_pieces.append((
                                "memory_notes",
                                "[项目笔记 — 供参考，"
                                "不要在回复中提及你看到了笔记，自然运用相关信息即可。]\n"
                                + notes,
                                4
                            ))
                            inject_items.append("记忆: 已注入项目笔记")
                    except Exception as e:
                        inject_items.append(f"记忆注入失败: {e}")

                # ── 行为约束（固定尾部约束，防止幻觉和失控）──
                system_pieces.append((
                    "behavior_constraints",
                    "# 行为约束\n"
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
                    "- 不知道权威源时，优先引用gov.cn/.edu.cn/官方域名的内容",
                    1
                ))

                # ── 深度思考引导（thinking 开关开启时注入，与角色解耦）──
                if thinking_enabled:
                    system_pieces.append((
                        "thinking_guidance",
                        "# 深度思考模式\n"
                        "请在思考过程中使用中文。思考是内部推理过程，不会展示给用户，用于提升最终回答质量。\n"
                        "按以下结构组织思考：\n"
                        "1. 拆解：用户真正想知道什么？识别核心问题。\n"
                        "2. 盘点：列出你已经掌握的相关知识和事实。\n"
                        "3. 缺口：标记可能过时、不确定或缺失的信息。\n"
                        "4. 策略：决定是否需要搜索。如果需要，构建精确的搜索关键词；如果不需要，说明原因。\n"
                        "注意：思考过程要详细展示分析推理，不要用'我将基于我的知识回答'这样一句话结束。",
                        1
                    ))

                # 当没有 MCP 工具可用时注入提示
                mcp_tools = deps.mcp_manager.get_enabled_tools() or []
                if not mcp_tools:
                    system_pieces.append((
                        "tool_status",
                        "# 工具状态\n"
                        "你当前没有 MCP 外部工具可用（读写文件、执行命令等），不要编造工具调用。"
                        "如果需要执行本地操作，请告知用户需要启用对应 MCP 工具。"
                        "你可以使用快捷数据源工具（天气/金价/汇率/热搜）查询实时信息，"
                        "也可以使用联网搜索功能查找最新信息。",
                        1
                    ))

                # ── 组装 system_content（ContextBudget 统筹）──
                if context_budget_enabled:
                    # 用户手动覆盖 context window
                    if context_window_override > 0:
                        model_config["context_window"] = context_window_override

                    budget = ContextBudget(
                        model_config=model_config,
                        output_reserve_ratio=output_reserve_ratio,
                    )

                    # 添加所有 system pieces（P1-P5）
                    for name, content, priority in system_pieces:
                        budget.add_slice(name, content, priority)

                    # 添加会话历史作为 P6（最低优先级）
                    history_text = ""
                    if session_history:
                        history_text = "\n".join(
                            f"[{m.get('role', '?')}]: {str(m.get('content', ''))[:300]}"
                            for m in session_history
                        )
                        budget.add_slice("session_history", history_text, priority=6)

                    # ── 执行预算约束 ──
                    trimmed_items = budget.enforce_budget()

                    # 如果 P6 被裁剪，同步裁剪实际的 session_history
                    if history_text:
                        history_slice = next((s for s in budget.slices if s.name == "session_history"), None)
                        if history_slice and history_slice.trimmed:
                            # 按比例裁剪 session_history（保留最近的消息）
                            keep_ratio = max(len(history_slice.content) / max(len(history_text), 1), 0.25)
                            keep_count = max(int(len(session_history) * keep_ratio), 1)
                            session_history = session_history[-keep_count:]

                    # 用裁剪后的内容重新组装 system_content
                    system_content = "\n\n".join(
                        s.content for s in budget.slices if s.content and s.name != "session_history"
                    )

                    if trimmed_items:
                        inject_items.append(f"⚠ 上下文预算裁剪: {', '.join(trimmed_items)}")

                    # 预算使用报告（超过告警阈值时显示）
                    report = budget.get_budget_report()
                    if report["usage_ratio"] >= budget_alert_threshold:
                        pct = int(report["usage_ratio"] * 100)
                        inject_items.append(
                            f"📊 上下文: {pct}% ({report['total_tokens']:,}/{report['input_budget']:,} tokens)"
                        )
                else:
                    # 未启用预算管理时，直接拼接
                    system_content = "\n\n".join(content for _, content, _ in system_pieces)

                if inject_items:
                    await ws.send_json({"type": "inject_info", "items": inject_items})

                # ── 组装消息列表 ──
                # 结构: system_prompt + session_history + current_user_message
                messages: list[dict] = [{"role": "system", "content": system_content}]
                messages.extend(session_history)
                messages.append({"role": "user", "content": user_text, "timestamp": datetime.now().isoformat()})

                # ── Agent Loop ──
                tools: list[dict] = list(deps.mcp_manager.get_enabled_tools() or [])
                # 快捷数据源和 server-side 搜索工具在 agent_loop 内部根据 provider 自动添加

                all_tools = tools if tools else None  # None 表示无工具，减少 litellm 开销

                try:
                    async for event in agent_loop(
                        messages=messages,
                        tools=all_tools,
                        model_config=model_config,
                        mcp_manager=deps.mcp_manager,
                        thinking_enabled=thinking_enabled,
                        permission_guard=permission_guard,
                    ):
                        await ws.send_json(event)

                    await ws.send_json({"type": "done"})

                    # ── 更新会话历史（只追加本轮新消息，避免修复后重复）──
                    # messages = [system] + session_history_old + [本轮 user/assistant/tool]
                    # 只取本轮新增部分：跳过 system(1) + 旧历史(len(session_history_old))
                    old_len = len(session_history)
                    new_char_count = 0
                    for m in messages[1 + old_len:]:
                        role = m.get("role", "")
                        if role in ("user", "assistant", "tool"):
                            session_history.append(m)
                            new_char_count += len(str(m.get("content", "")) or "")

                    # ── 聊天历史裁剪（按字符数，替代硬编码40条）──
                    session_history = _trim_history(session_history, max_history_chars)

                    # ── 保存对话到磁盘（完整保存，不受裁剪影响）──
                    save_data_msgs = [messages[0]] + session_history
                    # 为没有时间戳的消息补充时间戳（系统提示、assistant/tool 消息等）
                    now_ts = datetime.now().isoformat()
                    for m in save_data_msgs:
                        if "timestamp" not in m:
                            m["timestamp"] = now_ts
                    save_conversation(
                        messages=save_data_msgs,
                        model=model_config.get("model_id", ""),
                        role=role_name or str(deps.role_loader.get_default_role()),
                        conv_id=conv_id,
                    )

                    # ── 记忆压缩（双计数器 + 三种触发模式）──
                    if memory_compact_enabled:
                        memory_char_counter += new_char_count
                        memory_msg_counter += 1  # 新增：消息数计数

                        # 三种触发模式：chars / messages / both
                        trigger_chars = memory_compact_trigger in ("chars", "both") and memory_char_counter >= memory_compact_interval_chars
                        trigger_msgs = memory_compact_trigger in ("messages", "both") and memory_msg_counter >= memory_compact_interval_msgs

                        if trigger_chars or trigger_msgs:
                            memory_char_counter = 0  # 先重置，避免并发触发
                            memory_msg_counter = 0

                            async def _compact():
                                try:
                                    # 记忆压缩 → 使用 Flash 模型（降级）
                                    compact_model = select_model_for_task("memory_compact", model_config)
                                    path = await deps.memory_manager.compact_memory(
                                        list(session_history),
                                        compact_model,
                                        role_name or str(deps.role_loader.get_default_role()),
                                        window=memory_compact_window,
                                        max_tokens=memory_compact_max_tokens,
                                    )
                                    if path:
                                        await ws.send_json({
                                            "type": "inject_info",
                                            "items": [f"记忆: 已压缩到 memory/project-notes/{Path(path).name}"]
                                        })

                                        # ── 检查是否需要自动合并 ──
                                        compact_count = len(list(deps.memory_manager.notes_dir.glob("auto_compact_*.md")))
                                        if compact_count >= memory_merge_threshold:
                                            merge_path = await deps.memory_manager.merge_compacts(compact_model)
                                            if merge_path:
                                                await ws.send_json({
                                                    "type": "inject_info",
                                                    "items": [f"记忆: 已将 {compact_count} 个片段合并为长期记忆"]
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
    finally:
        # 停止后台 Reader
        _stop_event.set()
        if reader_task and not reader_task.done():
            reader_task.cancel()
            try:
                await reader_task
            except asyncio.CancelledError:
                pass
        # 清理所有待处理的权限请求
        permission_guard.cancel_all()
