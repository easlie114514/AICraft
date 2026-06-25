"""AICraft - 个人桌面AI能力启动器

主入口文件，启动Flet应用。
Phase 1: 对话页 + 模型页 + 角色页 完整实现
"""

import asyncio
import os
import subprocess
from datetime import datetime
from pathlib import Path

import flet as ft

from src.core.chat_history import (
    delete_conversation as delete_chat,
    get_recent_messages,
    list_conversations,
    load_conversation,
    save_conversation,
)
from src.core.memory import MemoryManager
from src.core.rag_engine import RAGEngine
from src.core.web_search import format_search_results, web_search
from src.core.llm import (
    get_available_models,
    get_current_model_config,
    test_connection,
)
from src.core.agent_loop import agent_loop
from src.core.mcp_client import MCPManager
from src.core.role_loader import RoleLoader
from src.core.skill_loader import SkillLoader
from src.utils.config import (
    MEMORY_DIR,
    MODELS_DIR,
    ROLES_DIR,
    SKILLS_DIR,
    delete_model_config,
    get_current_role_name,
    save_model_config,
    set_current_model_id,
    set_current_role_name,
    set_default_model,
    resolve_path,
)

# ── PyInstaller 隐式导入标记 ──
# 这些模块通过 --mcp-server CLI 动态加载，静态分析无法发现，
# 必须在此显式导入以确保 PyInstaller 将其打包进 exe。
import src.mcp_servers.code_executor  # noqa: F401
import src.mcp_servers.file_manager  # noqa: F401


# ============================================================
# 辅助函数
# ============================================================

def _make_message_bubble(role: str, text: str | ft.Control) -> ft.Container:
    """创建聊天气泡"""
    is_user = role == "user"
    return ft.Container(
        content=ft.Column([
            ft.Text(
                "You" if is_user else "AI",
                size=11,
                color=ft.Colors.ON_SURFACE_VARIANT,
                weight=ft.FontWeight.BOLD,
            ),
            text if isinstance(text, ft.Control) else ft.Text(
                text, size=14, selectable=True,
                color=ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE,
            ),
        ]),
        bgcolor=ft.Colors.PRIMARY_CONTAINER if is_user else ft.Colors.SURFACE_CONTAINER,
        border_radius=12,
        padding=ft.Padding(left=14, top=10, right=14, bottom=10),
        margin=ft.Margin(
            left=60 if is_user else 0,
            right=0 if is_user else 60,
            top=0,
            bottom=8,
        ),
        animate_opacity=300,
    )


def _make_tool_card(name: str, detail: str, card_type: str = "calling") -> ft.Container:
    """创建工具调用/结果卡片，显示在对话流中"""
    import json as _json

    is_calling = card_type == "calling"
    icon = "🔧" if is_calling else "✅"
    label = "调用工具" if is_calling else "工具返回"

    # 格式化参数或结果
    if is_calling:
        try:
            detail_str = _json.dumps(detail, ensure_ascii=False, indent=2) if isinstance(detail, dict) else str(detail)
        except Exception:
            detail_str = str(detail)
    else:
        detail_str = str(detail)

    if len(detail_str) > 250:
        detail_str = detail_str[:250] + "..."

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(icon, size=14),
                ft.Text(f"{label}: ", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Text(name, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.TERTIARY),
            ]),
            ft.Text(detail_str, size=11, color=ft.Colors.ON_SURFACE_VARIANT,
                    font_family="monospace", selectable=True,
                    max_lines=6),
        ], spacing=2),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border=ft.Border(
            left=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            right=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
            bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT),
        ),
        border_radius=8,
        padding=ft.Padding(left=12, top=8, right=12, bottom=8),
        margin=ft.Margin(left=60, top=2, right=60, bottom=2),
    )


def _open_folder(path: Path) -> None:
    """在资源管理器中打开文件夹"""
    if os.name == "nt":
        os.startfile(str(path))
    else:
        subprocess.Popen(["open" if os.uname().sysname == "Darwin" else "xdg-open", str(path)])


# ============================================================
# 对话页
# ============================================================

def build_chat_view(page: ft.Page, app_state: dict) -> ft.Column:
    """构建对话页"""
    chat_list = ft.ListView(expand=True, spacing=4, padding=10, auto_scroll=True)
    streaming_ref = [False]  # mutable ref for closure access

    def _get_streaming() -> bool:
        return streaming_ref[0]

    def _set_streaming(v: bool) -> None:
        streaming_ref[0] = v

    def on_send_click(e):
        """发送/停止 按钮调度"""
        if _get_streaming():
            # 点击「停止」：设置标志位，流式循环会退出
            _set_streaming(False)
            send_btn.text = "发送"
            send_btn.icon = ft.Icons.SEND
            send_btn.bgcolor = None
            send_btn.update()
        else:
            user_text = input_field.value.strip()
            if not user_text:
                return
            # 使用 page.run_task 调度异步任务（Flet 官方推荐方式）
            page.run_task(
                _on_send, page, chat_list, input_field, send_btn,
                _get_streaming, _set_streaming, app_state,
            )

    send_btn = ft.FilledButton(
        "发送",
        icon=ft.Icons.SEND,
        on_click=on_send_click,
    )

    input_field = ft.TextField(
        hint_text="输入消息... (Ctrl+Enter 发送)",
        expand=True,
        multiline=True,
        min_lines=1,
        max_lines=5,
        text_size=14,
        border_radius=10,
        on_submit=on_send_click,
    )

    # 欢迎消息
    chat_list.controls.append(
        ft.Container(
            content=ft.Column([
                ft.Text("👋 欢迎使用 AICraft", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "这是你的个人AI桌面启动器。\n先在「模型」页添加API配置，然后在「角色」页选择角色，就可以开始对话了。",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ]),
            alignment=ft.Alignment.CENTER,
            padding=30,
        )
    )

    # 三个开关
    web_search_switch = ft.Switch(label="联网搜索", value=False, label_text_style=ft.TextStyle(size=12))
    rag_switch = ft.Switch(label="RAG检索", value=True, label_text_style=ft.TextStyle(size=12))
    memory_switch = ft.Switch(label="记忆注入", value=True, label_text_style=ft.TextStyle(size=12))

    # 存入 app_state 供 _on_send 读取
    app_state["chat_toggles"] = {
        "web_search": web_search_switch,
        "rag": rag_switch,
        "memory": memory_switch,
    }

    toggles_row = ft.Row(
        [web_search_switch, rag_switch, memory_switch],
        alignment=ft.MainAxisAlignment.START,
    )

    return ft.Column(
        [
            toggles_row,
            ft.Divider(height=1),
            chat_list,
            ft.Divider(height=1),
            ft.Row(
                [input_field, send_btn],
                vertical_alignment=ft.CrossAxisAlignment.END,
            ),
        ],
        expand=True,
    )


async def _on_send(
    page: ft.Page,
    chat_list: ft.ListView,
    input_field: ft.TextField,
    send_btn: ft.FilledButton,
    get_streaming,
    set_streaming,
    app_state: dict,
) -> None:
    """处理发送消息 — 使用 Agent 循环支持多轮工具调用"""
    if get_streaming():
        return  # 正在流式输出中，忽略

    user_text = input_field.value.strip()
    if not user_text:
        return

    # 检查模型配置
    model_config = get_current_model_config()
    if not model_config or not model_config.get("model_id"):
        chat_list.controls.append(
            _make_message_bubble("assistant",
                "⚠️ 请先在「模型」页添加并配置一个可用的模型。")
        )
        input_field.value = ""
        input_field.update()
        page.update()
        return

    # 清空输入框
    input_field.value = ""
    input_field.update()

    # 禁用发送按钮，改为停止按钮
    set_streaming(True)
    send_btn.text = "停止"
    send_btn.icon = ft.Icons.STOP
    send_btn.bgcolor = ft.Colors.ERROR
    send_btn.update()

    # 添加用户消息气泡
    chat_list.controls.append(_make_message_bubble("user", user_text))

    # 创建AI回复气泡（用Text控件以支持流式更新）
    response_text = ft.Text("思考中...", size=14, selectable=True)
    assistant_bubble = _make_message_bubble("assistant", response_text)
    chat_list.controls.append(assistant_bubble)

    # 记录 AI 气泡在 chat_list 中的位置（用于在其前插入工具调用卡片）
    assistant_idx = len(chat_list.controls) - 1

    page.update()

    # ── 构建消息列表 ──
    role_loader = RoleLoader()
    role_loader.scan()
    role_name = get_current_role_name()
    system_prompt = role_loader.build_system_prompt(role_name)

    # 注入已启用的Skill prompts
    skill_loader: SkillLoader | None = app_state.get("skill_loader") if app_state else None
    if skill_loader:
        skill_prompt = skill_loader.build_skill_prompt()
        if skill_prompt:
            system_prompt = system_prompt + skill_prompt

    # ── Phase 3 注入：联网搜索 / RAG / 记忆 ──
    toggles = app_state.get("chat_toggles", {}) if app_state else {}
    injected_info = []  # 记录注入了什么，用于最后展示

    # 1. 联网搜索注入
    if toggles.get("web_search") and toggles["web_search"].value:
        try:
            search_results = web_search(user_text)
            formatted = format_search_results(search_results)
            if search_results and not search_results[0].get("title") == "搜索失败":
                system_prompt += formatted
                injected_info.append(f"联网搜索: {len(search_results)} 条结果")
        except Exception:
            pass

    # 2. RAG 检索注入
    if toggles.get("rag") and toggles["rag"].value:
        rag_engine: RAGEngine | None = app_state.get("rag_engine") if app_state else None
        if rag_engine:
            try:
                fragments = rag_engine.search(user_text)
                if fragments:
                    system_prompt += "\n\n# 相关知识库片段\n" + "\n---\n".join(fragments)
                    injected_info.append(f"RAG检索: {len(fragments)} 条片段")
                else:
                    injected_info.append("RAG检索: 未找到相关片段")
            except Exception as ex:
                injected_info.append(f"RAG检索失败: {ex}")

    # 3. 记忆注入（笔记 + 最近对话）
    if toggles.get("memory") and toggles["memory"].value:
        mm: MemoryManager | None = app_state.get("memory_manager") if app_state else None
        if mm:
            try:
                notes = mm.load_all_notes()
                if notes:
                    system_prompt += notes
                    injected_info.append("记忆: 已注入笔记")
            except Exception:
                pass
            try:
                recent = get_recent_messages(limit=10)
                if recent:
                    parts = ["\n\n# 最近对话历史\n"]
                    for m in recent:
                        role_label = "用户" if m.get("role") == "user" else "AI"
                        parts.append(f"**{role_label}**: {m.get('content', '')}")
                    system_prompt += "\n".join(parts)
                    injected_info.append(f"记忆: {len(recent)} 条历史")
            except Exception:
                pass

    # ── 拼装 messages（含近期对话历史）──
    messages = [
        {"role": "system", "content": system_prompt},
    ]
    # 添加最近对话历史（跨对话，帮助 LLM 理解上下文）
    try:
        history_msgs = get_recent_messages(limit=20)
        for m in history_msgs:
            role = m.get("role", "")
            # 只保留 user/assistant 消息（过滤 tool/system），content 可能为 None
            if role in ("user", "assistant"):
                content = m.get("content") or ""
                messages.append({"role": role, "content": content})
    except Exception:
        pass
    messages.append({"role": "user", "content": user_text})

    # ── 获取 MCP 工具列表 ──
    mcp_tools = None
    mcp_manager: MCPManager | None = app_state.get("mcp_manager") if app_state else None
    if mcp_manager:
        mcp_tools = mcp_manager.get_enabled_tools() or None

    # ── Agent 循环 ──
    full_text = ""
    error_occurred = False
    tool_call_count = 0

    try:
        async for event in agent_loop(
            messages=messages,
            tools=mcp_tools,
            model_config=model_config,
            mcp_manager=mcp_manager,
            max_rounds=10,
        ):
            # 检查是否被用户停止
            if not get_streaming():
                break

            event_type = event.get("type", "")

            if event_type == "text":
                # 流式文本 → 更新响应气泡
                full_text += event.get("content", "")
                response_text.value = full_text
                response_text.update()

            elif event_type == "tool_call":
                tool_call_count += 1
                tool_name = event.get("name", "未知工具")
                tool_args = event.get("args", {})
                # 在 AI 气泡之前插入工具调用卡片
                tc_card = _make_tool_card(tool_name, tool_args, "calling")
                chat_list.controls.insert(assistant_idx, tc_card)
                assistant_idx += 1
                page.update()

            elif event_type == "tool_result":
                tool_name = event.get("name", "未知工具")
                result = event.get("result", "")
                # 在 AI 气泡之前插入工具结果卡片
                tr_card = _make_tool_card(tool_name, result, "result")
                chat_list.controls.insert(assistant_idx, tr_card)
                assistant_idx += 1
                page.update()

    except Exception as ex:
        error_occurred = True
        response_text.value = f"❌ 调用失败: {str(ex)}"
        response_text.update()
    else:
        # Agent 循环正常结束 — 追加注入信息摘要
        if full_text and injected_info:
            suffix_parts = ["", "─" * 30]
            for info in injected_info:
                suffix_parts.append(f"📎 {info}")
            full_text += "\n" + "\n".join(suffix_parts)
            response_text.value = full_text
            response_text.update()
        elif full_text == "":
            if tool_call_count > 0:
                response_text.value = "（工具调用已完成）"
            elif get_streaming():
                response_text.value = "（模型未返回内容）"
            response_text.update()

    # ── 保存对话历史 ──
    if full_text and not error_occurred:
        try:
            # 保存完整的 messages 历史（含 system/user/assistant/tool 消息）
            save_conversation(
                messages,
                model=model_config.get("model_id", ""),
                role=role_name,
            )
        except Exception:
            pass  # 保存失败不阻塞

    # ── 恢复发送按钮 ──
    set_streaming(False)
    send_btn.text = "发送"
    send_btn.icon = ft.Icons.SEND
    send_btn.bgcolor = None
    send_btn.update()
    page.update()


# ============================================================
# 模型页
# ============================================================

def _build_model_card(
    model: dict,
    page: ft.Page,
    refresh_fn,
) -> ft.Container:
    """构建单个模型卡片"""
    name = model.get("name", "未命名")
    model_id = model.get("model_id", "")
    api_base = model.get("api_base", "")
    provider = model.get("provider", "")
    is_default = model.get("is_default", False)
    api_key_set = bool(model.get("api_key", ""))

    status_text = ft.Text(
        "● 默认" if is_default else "○ 可用",
        size=12,
        color=ft.Colors.PRIMARY if is_default else ft.Colors.ON_SURFACE_VARIANT,
    )

    def on_test(e):
        async def _test():
            status_text.value = "⏳ 测试中..."
            status_text.color = ft.Colors.AMBER
            status_text.update()
            ok, msg = await test_connection(model)
            if ok:
                status_text.value = f"✅ {msg[:60]}"
                status_text.color = ft.Colors.GREEN
            else:
                status_text.value = f"❌ {msg[:80]}"
                status_text.color = ft.Colors.ERROR
            status_text.update()
            page.update()

        asyncio.ensure_future(_test())

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.PRIMARY),
                ft.Column([
                    ft.Text(name, size=15, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        f"{model_id}  |  {api_base or '无自定义端点'}  |  {'🔑 已配置' if api_key_set else '⚠ 未配置Key'}",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    status_text,
                ], expand=True, spacing=2),
                ft.IconButton(
                    icon=ft.Icons.NETWORK_CHECK,
                    tooltip="测试连接",
                    icon_size=18,
                    on_click=on_test,
                ),
                ft.IconButton(
                    icon=ft.Icons.STAR_OUTLINE if not is_default else ft.Icons.STAR,
                    tooltip="设为默认",
                    icon_size=18,
                    on_click=lambda e, m=model: _on_set_default(m, page, refresh_fn),
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="删除",
                    icon_size=18,
                    icon_color=ft.Colors.ERROR,
                    on_click=lambda e, m=model: _on_delete_model(m, page, refresh_fn),
                ),
            ]),
        ]),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=10,
        padding=12,
        margin=ft.Margin(top=0, left=0, right=0, bottom=8),
    )


def _on_set_default(model: dict, page: ft.Page, refresh_fn) -> None:
    """设为默认模型"""
    model_id = model.get("model_id", "")
    if model_id:
        set_default_model(model_id)
        refresh_fn()


def _on_delete_model(model: dict, page: ft.Page, refresh_fn) -> None:
    """删除模型配置"""
    name = model.get("name", "")
    if name:
        delete_model_config(name)
        # 如果删除的是当前使用的模型，清除选择
        current = get_current_model_config()
        if not current:
            set_current_model_id("")
        refresh_fn()


def build_model_view(page: ft.Page, app_state: dict) -> ft.Column:
    """构建模型页"""
    model_list = ft.Column(spacing=0)

    def refresh_model_list():
        """刷新模型列表"""
        model_list.controls.clear()
        models = get_available_models()
        if models:
            for m in models:
                model_list.controls.append(_build_model_card(m, page, refresh_model_list))
        else:
            model_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("尚未配置任何模型", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "点击下方「添加模型」按钮，填写API信息开始使用",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                )
            )
        page.update()

    # 添加模型表单字段
    name_field = ft.TextField(label="模型名称", hint_text="例如: DeepSeek-V4 Pro", text_size=13)
    provider_field = ft.TextField(label="Provider", hint_text="litellm provider，如 openai / deepseek", text_size=13, value="openai")
    model_id_field = ft.TextField(label="Model ID", hint_text="litellm模型ID，如 openai/deepseek-v4-pro", text_size=13)
    api_base_field = ft.TextField(label="API Base URL", hint_text="https://api.deepseek.com/v1", text_size=13)
    api_key_field = ft.TextField(label="API Key", hint_text="sk-...", text_size=13, password=True, can_reveal_password=True)
    form_status = ft.Text("", size=12)

    # 回调函数必须定义在 form_expand 之前（Python 作用域规则）
    def toggle_form(e):
        form_expand.visible = not form_expand.visible
        form_expand.update()
        page.update()

    def on_save_model(e):
        # 验证必填项
        name = name_field.value.strip()
        model_id = model_id_field.value.strip()
        if not name:
            form_status.value = "❌ 模型名称不能为空"
            form_status.color = ft.Colors.ERROR
            form_status.update()
            return
        if not model_id:
            form_status.value = "❌ Model ID 不能为空"
            form_status.color = ft.Colors.ERROR
            form_status.update()
            return

        data = {
            "name": name,
            "provider": provider_field.value.strip() or "openai",
            "model_id": model_id,
            "api_base": api_base_field.value.strip(),
            "api_key": api_key_field.value.strip(),
            "is_default": len(get_available_models()) == 0,  # 第一个模型自动设为默认
        }

        try:
            save_model_config(data)
            # 如果是第一个模型，更新 profile
            if data["is_default"]:
                set_current_model_id(model_id)
            # 清空表单
            name_field.value = ""
            provider_field.value = "openai"
            model_id_field.value = ""
            api_base_field.value = ""
            api_key_field.value = ""
            form_expand.visible = False
            form_status.value = ""
            refresh_model_list()
        except Exception as ex:
            form_status.value = f"❌ 保存失败: {ex}"
            form_status.color = ft.Colors.ERROR
            form_status.update()

    # 可展开的添加模型表单
    form_expand = ft.Column(
        [
            ft.Text("新增模型配置", size=15, weight=ft.FontWeight.BOLD),
            name_field,
            ft.Row([provider_field, model_id_field], expand=True),
            api_base_field,
            api_key_field,
            form_status,
            ft.Row([
                ft.FilledButton("保存", icon=ft.Icons.SAVE, on_click=on_save_model),
                ft.TextButton("取消", on_click=toggle_form),
            ]),
        ],
        visible=False,
    )

    # 初始加载
    refresh_model_list()

    return ft.Column(
        [
            ft.Row([
                ft.Button(
                    "＋ 添加模型",
                    icon=ft.Icons.ADD,
                    on_click=toggle_form,
                ),
                ft.Text(
                    f"模型配置文件目录: {MODELS_DIR}",
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    size=12,
                ),
            ]),
            # 添加模型表单（可展开/收起）
            ft.Container(
                content=form_expand,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=16,
                margin=ft.Margin(top=0, left=0, right=0, bottom=12),
            ),
            ft.Divider(),
            ft.Text("已配置的模型", size=14, weight=ft.FontWeight.BOLD),
            model_list,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
    )


# ============================================================
# 角色页
# ============================================================

def build_role_view(page: ft.Page, app_state: dict) -> ft.Column:
    """构建角色页"""
    role_loader = RoleLoader()
    role_list = ft.Column(spacing=4)

    def refresh_role_list():
        """刷新角色列表"""
        role_list.controls.clear()
        roles = role_loader.scan()
        current_name = get_current_role_name()

        if roles:
            for role in roles:
                is_current = role.name == current_name
                # 角色内容预览（前80字）
                preview = role.content.replace("\n", " ")[:80] + ("..." if len(role.content) > 80 else "")

                role_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE if is_current else ft.Icons.CIRCLE_OUTLINED,
                                color=ft.Colors.PRIMARY if is_current else ft.Colors.ON_SURFACE_VARIANT,
                                size=20,
                            ),
                            ft.Column([
                                ft.Text(
                                    f"{role.name} {'(当前)' if is_current else ''}",
                                    size=14,
                                    weight=ft.FontWeight.BOLD if is_current else ft.FontWeight.NORMAL,
                                ),
                                ft.Text(preview, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ], expand=True, spacing=2),
                            ft.IconButton(
                                icon=ft.Icons.OPEN_IN_BROWSER,
                                tooltip="查看角色内容",
                                icon_size=16,
                                on_click=lambda e, r=role: _view_role_content(page, r, role_loader, refresh_role_list),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                tooltip="编辑角色",
                                icon_size=16,
                                on_click=lambda e, r=role: _edit_role_dialog(page, r, role_loader, refresh_role_list),
                            ),
                        ]),
                        bgcolor=ft.Colors.SURFACE_CONTAINER if is_current else None,
                        border_radius=10,
                        padding=10,
                        margin=ft.Margin(top=0, left=0, right=0, bottom=4),
                        on_click=lambda e, r=role: _select_role(r, page, refresh_role_list),
                    )
                )
        else:
            role_list.controls.append(
                ft.Text("暂无角色文件，请创建或放入 .md 文件", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
            )

        page.update()

    def on_new_role(e):
        _show_new_role_dialog(page, role_loader, refresh_role_list)

    refresh_role_list()

    return ft.Column(
        [
            ft.Row([
                ft.Button(
                    "＋ 新建角色",
                    icon=ft.Icons.ADD,
                    on_click=on_new_role,
                ),
                ft.Button(
                    "打开角色文件夹",
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda e: _open_folder(ROLES_DIR),
                ),
            ]),
            ft.Divider(),
            ft.Text("角色列表", size=14, weight=ft.FontWeight.BOLD),
            role_list,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
    )


def _select_role(role, page: ft.Page, refresh_fn) -> None:
    """选择一个角色作为当前角色"""
    set_current_role_name(role.name)
    refresh_fn()


def _view_role_content(page: ft.Page, role, role_loader: RoleLoader, refresh_fn) -> None:
    """查看角色完整内容"""

    def close_dlg(e):
        dlg.open = False
        page.update()

    def on_edit(e):
        dlg.open = False
        page.update()
        _edit_role_dialog(page, role, role_loader, refresh_fn)

    dlg = ft.AlertDialog(
        title=ft.Text(f"角色: {role.name}"),
        content=ft.Container(
            content=ft.Column([
                ft.Text(role.content, selectable=True, size=13),
            ], scroll=ft.ScrollMode.AUTO),
            width=500,
            height=350,
        ),
        actions=[
            ft.FilledButton("编辑", on_click=on_edit),
            ft.TextButton("关闭", on_click=close_dlg),
        ],
        actions_padding=ft.padding.only(left=16, right=16, bottom=12),
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


def _edit_role_dialog(page: ft.Page, role, role_loader: RoleLoader, refresh_fn) -> None:
    """编辑已有角色"""
    name_field = ft.TextField(label="角色名称", value=role.name, text_size=13)
    content_field = ft.TextField(
        label="角色描述（System Prompt）",
        hint_text="描述这个角色的特点、输出风格、关注重点...",
        multiline=True,
        min_lines=5,
        max_lines=12,
        text_size=13,
        value=role.content,
    )
    status_text = ft.Text("", size=12)

    def on_save(e):
        name = name_field.value.strip()
        content = content_field.value.strip()
        if not name:
            status_text.value = "❌ 角色名称不能为空"
            status_text.color = ft.Colors.ERROR
            status_text.update()
            return

        # 如果名称变了，删除旧文件
        if name != role.name:
            old_path = role.path
            if old_path.exists():
                old_path.unlink()

        # 保存为新文件
        path = ROLES_DIR / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content or f"你是{name}，请用中文回答问题。", encoding="utf-8")

        dlg.open = False
        page.update()
        refresh_fn()

    def close_dlg(e):
        dlg.open = False
        page.update()

    dlg = ft.AlertDialog(
        title=ft.Text(f"编辑角色: {role.name}"),
        content=ft.Container(
            content=ft.Column([
                name_field,
                content_field,
                status_text,
            ], scroll=ft.ScrollMode.AUTO, spacing=10),
            width=480,
            height=380,
        ),
        actions=[
            ft.FilledButton("保存", on_click=on_save),
            ft.TextButton("取消", on_click=close_dlg),
        ],
        actions_padding=ft.padding.only(left=16, right=16, bottom=12),
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


def _show_new_role_dialog(page: ft.Page, role_loader: RoleLoader, refresh_fn) -> None:
    """显示新建角色对话框"""
    name_field = ft.TextField(label="角色名称", hint_text="例如: 代码审查员", text_size=13)
    content_field = ft.TextField(
        label="角色描述（System Prompt）",
        hint_text="描述这个角色的特点、输出风格、关注重点...",
        multiline=True,
        min_lines=5,
        max_lines=12,
        text_size=13,
    )
    status_text = ft.Text("", size=12)

    def on_save(e):
        name = name_field.value.strip()
        content = content_field.value.strip()
        if not name:
            status_text.value = "❌ 角色名称不能为空"
            status_text.color = ft.Colors.ERROR
            status_text.update()
            return

        # 保存为md文件
        path = ROLES_DIR / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content or f"你是{name}，请用中文回答问题。", encoding="utf-8")

        dlg.open = False
        page.update()
        refresh_fn()

    def close_dlg(e):
        dlg.open = False
        page.update()

    dlg = ft.AlertDialog(
        title=ft.Text("新建角色"),
        content=ft.Container(
            content=ft.Column([
                name_field,
                content_field,
                status_text,
            ], scroll=ft.ScrollMode.AUTO, spacing=10),
            width=480,
            height=380,
        ),
        actions=[
            ft.FilledButton("保存", on_click=on_save),
            ft.TextButton("取消", on_click=close_dlg),
        ],
        actions_padding=ft.padding.only(left=16, right=16, bottom=12),
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


# ============================================================
# 占位页（Phase 2-3 开发）
# ============================================================

def build_skill_view(page: ft.Page, app_state: dict) -> ft.Column:
    """构建Skill页"""
    loader: SkillLoader = app_state["skill_loader"]
    skill_list = ft.Column(spacing=0)

    def refresh_skill_list():
        """刷新Skill列表"""
        skill_list.controls.clear()
        skills = loader.scan()
        if skills:
            for s in skills:
                skill_list.controls.append(_build_skill_card(s, loader, page, refresh_skill_list))
        else:
            # 空状态
            skill_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.BUILD, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("暂无Skill", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "在 skills/ 目录下创建文件夹，放入 SKILL.md 文件即可自动识别",
                            size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "例如: skills/my-skill/SKILL.md",
                            size=11, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                )
            )
        page.update()

    refresh_skill_list()

    # 注册刷新函数供导航回调使用
    app_state["refresh_skill_list"] = refresh_skill_list

    return ft.Column(
        [
            ft.Row([
                ft.Button("打开Skill文件夹", icon=ft.Icons.FOLDER_OPEN,
                          on_click=lambda e: _open_folder(SKILLS_DIR)),
                ft.IconButton(icon=ft.Icons.REFRESH, tooltip="刷新", on_click=lambda e: refresh_skill_list()),
            ]),
            ft.Divider(),
            ft.Text("Skill列表", size=14, weight=ft.FontWeight.BOLD),
            skill_list,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
    )


def _build_skill_card(skill, loader: SkillLoader, page: ft.Page, refresh_fn) -> ft.Container:
    """构建单个Skill卡片"""
    def on_toggle(e):
        loader.toggle(skill.name, e.control.value)
        refresh_fn()

    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.BUILD, color=ft.Colors.PRIMARY, size=20),
            ft.Column([
                ft.Text(skill.name, size=14, weight=ft.FontWeight.BOLD),
                ft.Text(skill.description, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], expand=True, spacing=2),
            ft.Switch(value=skill.enabled, on_change=on_toggle),
        ]),
        bgcolor=ft.Colors.SURFACE_CONTAINER if skill.enabled else None,
        border_radius=10,
        padding=12,
        margin=ft.Margin(top=0, left=0, right=0, bottom=8),
    )


def build_mcp_view(page: ft.Page, app_state: dict) -> ft.Column:
    """构建MCP页"""
    manager: MCPManager = app_state["mcp_manager"]
    mcp_list = ft.Column(spacing=0)

    # 添加MCP表单字段
    name_field = ft.TextField(label="连接名称", hint_text="例如: Jira MCP", text_size=13)

    # 连接类型选择
    type_dd = ft.Dropdown(
        label="连接类型",
        options=[
            ft.dropdown.Option("sse", "SSE (远程服务)"),
            ft.dropdown.Option("stdio", "Stdio (本地脚本)"),
        ],
        value="sse",
        text_size=13,
    )

    # SSE 字段
    url_field = ft.TextField(
        label="完整URL（SSE模式）",
        hint_text="例如: http://172.28.33.101/api/sse",
        text_size=13,
    )
    host_field = ft.TextField(label="主机地址（SSE模式）", hint_text="例如: 127.0.0.1", text_size=13)
    port_field = ft.TextField(label="端口（SSE模式）", hint_text="例如: 8080", text_size=13)

    # Stdio 字段
    command_field = ft.TextField(label="命令（Stdio模式）", hint_text="例如: py 或 python", text_size=13, value="py")
    args_field = ft.TextField(
        label="参数（Stdio模式，空格分隔）",
        hint_text="例如: -3.13 scripts/workshop_mcp.py (相对项目根)",
        text_size=13,
    )

    form_status = ft.Text("", size=12)

    def toggle_form(e):
        form_expand.visible = not form_expand.visible
        form_status.value = ""
        form_expand.update()
        page.update()

    def on_save_mcp(e):
        name = name_field.value.strip()
        conn_type = type_dd.value if type_dd.value else "sse"

        if not name:
            form_status.value = "❌ 连接名称不能为空"
            form_status.color = ft.Colors.ERROR; form_status.update(); return

        if conn_type == "stdio":
            # Stdio 模式
            command = command_field.value.strip()
            args_str = args_field.value.strip()
            if not command:
                form_status.value = "❌ 命令不能为空"
                form_status.color = ft.Colors.ERROR; form_status.update(); return
            args = args_str.split() if args_str else []
            conn = manager.add_connection(name, conn_type="stdio", command=command, args=args)
        else:
            # SSE 模式
            full_url = url_field.value.strip()
            host = host_field.value.strip()
            port_str = port_field.value.strip()
            if full_url:
                conn = manager.add_connection(name, url=full_url)
            else:
                if not host:
                    form_status.value = "❌ 请填写主机地址或完整URL"
                    form_status.color = ft.Colors.ERROR; form_status.update(); return
                try:
                    port = int(port_str) if port_str else 0
                except ValueError:
                    form_status.value = "❌ 端口必须是数字"
                    form_status.color = ft.Colors.ERROR; form_status.update(); return
                conn = manager.add_connection(name, host=host, port=port)

        # 清空表单
        name_field.value = ""; url_field.value = ""; host_field.value = ""; port_field.value = ""
        command_field.value = "py"; args_field.value = ""
        form_expand.visible = False; form_status.value = ""
        refresh_mcp_list()

        # 自动连接
        async def _auto_connect():
            await manager.connect(conn)
            refresh_mcp_list()
        page.run_task(_auto_connect)

    form_expand = ft.Column([
        ft.Text("新增MCP连接", size=15, weight=ft.FontWeight.BOLD),
        name_field,
        type_dd,
        ft.Text("SSE 模式", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
        url_field,
        ft.Text("或使用 host:port", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        ft.Row([host_field, port_field]),
        ft.Divider(),
        ft.Text("Stdio 模式", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.SECONDARY),
        command_field,
        args_field,
        form_status,
        ft.Row([
            ft.FilledButton("保存", icon=ft.Icons.SAVE, on_click=on_save_mcp),
            ft.TextButton("取消", on_click=toggle_form),
        ]),
    ], visible=False)

    def refresh_mcp_list():
        """刷新MCP连接列表（使用内存中的状态，不从磁盘重新加载）"""
        mcp_list.controls.clear()
        connections = manager.connections
        if connections:
            for conn in connections:
                mcp_list.controls.append(_build_mcp_card(conn, manager, page, refresh_mcp_list))
        else:
            # 空状态
            mcp_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.POWER, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("尚未添加任何MCP连接", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "点击上方「添加MCP」按钮，配置 SSE 远程服务或 Stdio 本地脚本",
                            size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                )
            )
        page.update()

    refresh_mcp_list()

    # 注册刷新函数
    app_state["refresh_mcp_list"] = refresh_mcp_list

    return ft.Column(
        [
            ft.Row([
                ft.Button("添加MCP", icon=ft.Icons.ADD, on_click=toggle_form),
            ]),
            # 添加MCP表单
            ft.Container(
                content=form_expand,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=16,
                margin=ft.Margin(top=0, left=0, right=0, bottom=12),
            ),
            ft.Divider(),
            ft.Text("MCP连接列表", size=14, weight=ft.FontWeight.BOLD),
            mcp_list,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
    )


def _build_mcp_card(conn, manager: MCPManager, page: ft.Page, refresh_fn) -> ft.Container:
    """构建单个MCP连接卡片"""
    # 状态映射
    STATUS_MAP = {
        "connected": (ft.Colors.GREEN, "已连接"),
        "connecting": (ft.Colors.AMBER, "连接中..."),
        "error": (ft.Colors.ERROR, conn.error_msg[:30] or "错误"),
        "disconnected": (ft.Colors.ON_SURFACE_VARIANT, "断开"),
    }
    status_color, status_label = STATUS_MAP.get(conn.status,
        (ft.Colors.ON_SURFACE_VARIANT, "未知"))
    status_text = ft.Text(f"● {status_label}", size=12, color=status_color)

    # 开关
    def on_toggle(e):
        manager.toggle_connection(conn.name, e.control.value)
        refresh_fn()
    toggle_switch = ft.Switch(value=conn.enabled, on_change=on_toggle)

    # 工具展开区域
    tools_section = ft.Column(visible=False, spacing=2)
    expand_btn = ft.TextButton(
        f"▶ 工具列表 ({len(conn.tools)})" if conn.tools else "工具列表 (0)",
    )

    def on_toggle_tools(e):
        tools_section.visible = not tools_section.visible
        direction = "▼" if tools_section.visible else "▶"
        count = len(conn.tools)
        expand_btn.text = f"{direction} 工具列表 ({count})" if count else f"{direction} 工具列表 (0)"
        page.update()
    expand_btn.on_click = on_toggle_tools

    # 填充工具列表
    if conn.tools:
        for t in conn.tools:
            tools_section.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"🔧 {t['name']}", size=13, weight=ft.FontWeight.BOLD),
                        ft.Text(t.get("description", "")[:80], size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                    ]),
                    padding=ft.Padding(left=20, top=2, right=8, bottom=2),
                )
            )
    elif conn.status == "connected":
        tools_section.controls.append(ft.Text("未发现工具", size=12, italic=True,
            color=ft.Colors.ON_SURFACE_VARIANT))
    else:
        tools_section.controls.append(ft.Text("连接后可发现工具", size=12, italic=True,
            color=ft.Colors.ON_SURFACE_VARIANT))

    # 连接按钮
    def on_connect(e):
        async def _do_connect():
            status_text.value = "● 连接中..."
            status_text.color = ft.Colors.AMBER
            status_text.update()
            await manager.connect(conn)
            # 填充工具列表
            tools_section.controls.clear()
            if conn.tools:
                for t in conn.tools:
                    tools_section.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"🔧 {t['name']}", size=13, weight=ft.FontWeight.BOLD),
                                ft.Text(t.get("description", "")[:80], size=11,
                                        color=ft.Colors.ON_SURFACE_VARIANT),
                            ]),
                            padding=ft.Padding(left=20, top=2, right=8, bottom=2),
                        )
                    )
            elif conn.status == "connected":
                tools_section.controls.append(ft.Text("未发现工具", size=12, italic=True,
                    color=ft.Colors.ON_SURFACE_VARIANT))
            else:
                tools_section.controls.append(ft.Text("连接失败", size=12, italic=True,
                    color=ft.Colors.ERROR))
            expand_btn.text = f"▶ 工具列表 ({len(conn.tools)})"
            refresh_fn()
        page.run_task(_do_connect)

    # 删除按钮
    def on_delete(e):
        manager.remove_connection(conn.name)
        refresh_fn()

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.POWER, color=ft.Colors.PRIMARY, size=20),
                ft.Column([
                    ft.Row([
                        ft.Text(conn.name, size=15, weight=ft.FontWeight.BOLD),
                        ft.Container(
                            content=ft.Text(conn.type.upper(), size=10, color=ft.Colors.ON_SECONDARY_CONTAINER,
                                            weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.SECONDARY_CONTAINER,
                            border_radius=4,
                            padding=ft.Padding(left=5, top=1, right=5, bottom=1),
                        ),
                    ], spacing=6),
                    ft.Text(f"{conn.display_url}  |  工具: {len(conn.tools)}",
                            size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    status_text,
                ], expand=True, spacing=2),
                ft.IconButton(icon=ft.Icons.REFRESH, tooltip="连接/刷新工具",
                              icon_size=18, on_click=on_connect),
                toggle_switch,
                ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="删除",
                              icon_size=18, icon_color=ft.Colors.ERROR, on_click=on_delete),
            ]),
            ft.Row([expand_btn]),
            tools_section,
        ]),
        bgcolor=ft.Colors.SURFACE_CONTAINER if conn.enabled else None,
        border_radius=10,
        padding=12,
        margin=ft.Margin(top=0, left=0, right=0, bottom=8),
    )


def build_rag_view(page: ft.Page, app_state: dict) -> ft.Column:
    """构建RAG页 - 数据源管理"""
    engine: RAGEngine = app_state["rag_engine"]
    rag_list = ft.Column(spacing=0)

    def refresh_rag_list():
        """刷新RAG数据源列表"""
        rag_list.controls.clear()
        sources = engine.load_sources()
        if sources:
            for s in sources:
                rag_list.controls.append(_build_rag_card(s, engine, page, refresh_rag_list))
        else:
            rag_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.LOCAL_LIBRARY, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("尚未添加任何数据源", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "点击上方「添加数据源」按钮，指定本地文件夹路径，系统将自动索引其中的文档",
                            size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                )
            )
        page.update()

    def on_add_source(e):
        _show_add_rag_dialog(page, engine, refresh_rag_list)

    refresh_rag_list()
    app_state["refresh_rag_list"] = refresh_rag_list

    return ft.Column(
        [
            ft.Row([
                ft.Button("＋ 添加数据源", icon=ft.Icons.ADD, on_click=on_add_source),
            ]),
            ft.Divider(),
            ft.Text("RAG数据源列表", size=14, weight=ft.FontWeight.BOLD),
            rag_list,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
    )


def _build_rag_card(source, engine: RAGEngine, page: ft.Page, refresh_fn) -> ft.Container:
    """构建单个RAG数据源卡片"""
    stats = engine.get_chroma_stats()
    indexed_count = stats.get(source.name, 0)

    # 状态指示
    if source.indexed:
        status_text = ft.Text(
            f"已索引 {source.file_count} 个文件  |  ChromaDB: {indexed_count} 片段",
            size=12, color=ft.Colors.GREEN,
        )
        idx_label = "重新索引"
    else:
        status_text = ft.Text("未索引", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        idx_label = "索引"

    # 索引状态文字（索引过程中使用）
    index_status = ft.Text(status_text.value, size=12, color=status_text.color)

    def on_toggle(e):
        engine.toggle_source(source.name, e.control.value)
        refresh_fn()

    def on_index(e):
        async def _do_index():
            # 检查是否需要下载模型
            import os as _os
            _model_cache = Path(_os.path.expanduser("~")) / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2" / "onnx.tar.gz"
            if not _model_cache.exists():
                index_status.value = "⏳ 首次使用：正在下载Embedding模型(~80MB)，请耐心等待..."
                index_status.color = ft.Colors.AMBER
                index_status.update()
                page.update()
            else:
                index_status.value = "⏳ 正在索引文档..."
                index_status.color = ft.Colors.AMBER
                index_status.update()
                page.update()
            # 让出事件循环，确保 UI 刷新
            await asyncio.sleep(0.1)
            count = await engine.index_source(source)
            if count > 0:
                index_status.value = f"已索引 {source.file_count} 个文件"
                index_status.color = ft.Colors.GREEN
            else:
                index_status.value = "索引完成（无新文件）"
                index_status.color = ft.Colors.ON_SURFACE_VARIANT
            index_status.update()
            refresh_fn()
        page.run_task(_do_index)

    def on_delete(e):
        engine.remove_source(source.name)
        refresh_fn()

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.FOLDER, color=ft.Colors.PRIMARY, size=20),
                ft.Column([
                    ft.Text(source.name, size=15, weight=ft.FontWeight.BOLD),
                    ft.Text(source.path, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    index_status,
                ], expand=True, spacing=2),
                ft.Switch(value=source.enabled, on_change=on_toggle),
                ft.IconButton(
                    icon=ft.Icons.REFRESH,
                    tooltip=idx_label,
                    icon_size=18,
                    on_click=on_index,
                ),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="删除数据源",
                    icon_size=18,
                    icon_color=ft.Colors.ERROR,
                    on_click=on_delete,
                ),
            ]),
        ]),
        bgcolor=ft.Colors.SURFACE_CONTAINER if source.enabled else None,
        border_radius=10,
        padding=12,
        margin=ft.Margin(top=0, left=0, right=0, bottom=8),
    )


def _show_add_rag_dialog(page: ft.Page, engine: RAGEngine, refresh_fn) -> None:
    """显示添加RAG数据源对话框"""
    name_field = ft.TextField(label="数据源名称", hint_text="例如: 项目文档", text_size=13)
    path_field = ft.TextField(label="目录路径", hint_text="例如: rag/使用指导 (相对项目根)", text_size=13)
    status_text = ft.Text("", size=12)

    def on_save(e):
        name = name_field.value.strip()
        path = path_field.value.strip()
        if not name:
            status_text.value = "❌ 名称不能为空"
            status_text.color = ft.Colors.ERROR; status_text.update(); return
        if not path:
            status_text.value = "❌ 路径不能为空"
            status_text.color = ft.Colors.ERROR; status_text.update(); return
        if not resolve_path(path).exists():
            status_text.value = "❌ 目录不存在"
            status_text.color = ft.Colors.ERROR; status_text.update(); return

        engine.add_source(name, path)
        dlg.open = False
        page.update()
        refresh_fn()

    def close_dlg(e):
        dlg.open = False
        page.update()

    dlg = ft.AlertDialog(
        title=ft.Text("添加RAG数据源"),
        content=ft.Column([
            name_field,
            path_field,
            status_text,
        ], width=450, height=200),
        actions=[
            ft.FilledButton("保存", on_click=on_save),
            ft.TextButton("取消", on_click=close_dlg),
        ],
    )
    page.overlay.append(dlg)
    dlg.open = True
    page.update()


def build_memory_view(page: ft.Page, app_state: dict) -> ft.Column:
    """构建记忆页 - 对话历史 + 项目笔记 + 智能检索"""
    mm: MemoryManager = app_state["memory_manager"]
    memory_list = ft.Column(spacing=0)

    def refresh_memory_list():
        """刷新记忆列表"""
        memory_list.controls.clear()

        # ── 对话历史 ──
        memory_list.controls.append(
            ft.Text("📁 对话历史", size=14, weight=ft.FontWeight.BOLD)
        )
        convs = list_conversations()
        if convs:
            for c in convs[:20]:  # 最多显示20条
                memory_list.controls.append(_build_history_card(c, page, refresh_memory_list))
        else:
            memory_list.controls.append(
                ft.Text("暂无对话记录", size=12, italic=True,
                        color=ft.Colors.ON_SURFACE_VARIANT)
            )

        memory_list.controls.append(ft.Divider(height=16))

        # ── 项目笔记 ──
        memory_list.controls.append(
            ft.Text("📁 项目笔记", size=14, weight=ft.FontWeight.BOLD)
        )
        notes = mm.list_notes()
        if notes:
            for n in notes:
                memory_list.controls.append(_build_note_card(n, page))
        else:
            memory_list.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text("暂无项目笔记", size=12, italic=True,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            f"在 {mm.notes_dir} 目录下放入 .md 文件即可自动识别",
                            size=11, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ]),
                    padding=ft.Padding(left=0, top=4, right=0, bottom=8),
                )
            )

        memory_list.controls.append(ft.Divider(height=16))

        # ── 智能检索 ──
        memory_list.controls.append(
            ft.Text("🔍 智能检索", size=14, weight=ft.FontWeight.BOLD)
        )
        search_field = ft.TextField(
            hint_text="输入关键词，在记忆中检索相关内容...",
            text_size=13,
            expand=True,
        )
        search_result = ft.Column(spacing=2)

        def on_search(e):
            query = search_field.value.strip()
            if not query:
                return
            search_result.controls.clear()
            results = mm.search_memory(query)
            if results:
                for i, r in enumerate(results[:5], 1):
                    snippet = r[:200] + ("..." if len(r) > 200 else "")
                    search_result.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"{i}.", size=12, color=ft.Colors.PRIMARY),
                                ft.Text(snippet, size=12, selectable=True,
                                        color=ft.Colors.ON_SURFACE_VARIANT),
                            ]),
                            padding=ft.Padding(left=8, top=4, right=8, bottom=4),
                            border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
                        )
                    )
            else:
                search_result.controls.append(
                    ft.Text("未找到相关内容", size=12, italic=True,
                            color=ft.Colors.ON_SURFACE_VARIANT)
                )
            page.update()

        memory_list.controls.append(
            ft.Row([
                search_field,
                ft.IconButton(icon=ft.Icons.SEARCH, tooltip="搜索",
                              on_click=on_search),
            ])
        )
        memory_list.controls.append(search_result)

        page.update()

    refresh_memory_list()

    return ft.Column(
        [
            ft.Row([
                ft.Button("打开记忆文件夹", icon=ft.Icons.FOLDER_OPEN,
                          on_click=lambda e: _open_folder(MEMORY_DIR)),
                ft.IconButton(icon=ft.Icons.REFRESH, tooltip="刷新",
                              on_click=lambda e: refresh_memory_list()),
            ]),
            ft.Divider(),
            memory_list,
        ],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
    )


def _build_history_card(conv: dict, page: ft.Page, refresh_fn) -> ft.Container:
    """构建单个对话历史卡片"""
    created = conv.get("created", "")[:16].replace("T", " ")
    model = conv.get("model", "未知")
    role = conv.get("role", "")
    msg_count = conv.get("message_count", 0)
    conv_id = conv.get("id", "")

    def on_view(e):
        """查看完整对话"""
        data = load_conversation(conv_id)
        if not data:
            return
        messages = data.get("messages", [])
        content_col = ft.Column(spacing=8)

        for m in messages:
            role_label = "You" if m.get("role") == "user" else "AI"
            content_col.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(role_label, size=11, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.PRIMARY if role_label == "You" else ft.Colors.TERTIARY),
                        ft.Text(m.get("content", "")[:500], size=13, selectable=True),
                    ]),
                    padding=8,
                    border_radius=8,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                )
            )

        def close_dlg(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(f"对话详情 ({created})"),
            content=ft.Container(
                content=ft.ListView(
                    [content_col],
                    expand=True,
                ),
                width=550,
                height=400,
            ),
            actions=[ft.TextButton("关闭", on_click=close_dlg)],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def on_delete(e):
        delete_chat(conv_id)
        refresh_fn()

    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.CHAT, color=ft.Colors.PRIMARY, size=18),
            ft.Column([
                ft.Text(
                    f"{created}  |  模型: {model}" + (f"  |  角色: {role}" if role else ""),
                    size=13, weight=ft.FontWeight.BOLD,
                ),
                ft.Text(f"{msg_count} 条消息", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], expand=True, spacing=2),
            ft.IconButton(
                icon=ft.Icons.VISIBILITY,
                tooltip="查看对话",
                icon_size=16,
                on_click=on_view,
            ),
            ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                tooltip="删除",
                icon_size=16,
                icon_color=ft.Colors.ERROR,
                on_click=on_delete,
            ),
        ]),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=10,
        padding=10,
        margin=ft.Margin(top=0, left=0, right=0, bottom=6),
    )


def _build_note_card(note: dict, page: ft.Page) -> ft.Container:
    """构建单个项目笔记卡片"""
    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.DESCRIPTION, color=ft.Colors.TERTIARY, size=18),
            ft.Column([
                ft.Text(note["name"], size=13, weight=ft.FontWeight.BOLD),
                ft.Text(note.get("preview", ""), size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT),
            ], expand=True, spacing=2),
        ]),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border_radius=10,
        padding=10,
        margin=ft.Margin(top=0, left=0, right=0, bottom=6),
    )


# ============================================================
# 主入口
# ============================================================

def main(page: ft.Page):
    """应用主页面"""
    page.title = "AICraft"
    page.window.width = 1200
    page.window.height = 800
    page.window.min_width = 900
    page.window.min_height = 600
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.padding = 0

    # ----- 顶部 AppBar -----
    def _refresh_model_dropdown():
        """刷新模型下拉框"""
        models = get_available_models()
        model_dd.options = []
        if models:
            current_id = get_current_model_config().get("model_id", "")
            for m in models:
                model_dd.options.append(ft.dropdown.Option(
                    key=m["model_id"],
                    text=m.get("name", m["model_id"]),
                ))
            model_dd.value = current_id if any(
                m["model_id"] == current_id for m in models
            ) else models[0]["model_id"]
        else:
            model_dd.options = [ft.dropdown.Option("__none__", "未配置")]
            model_dd.value = "__none__"

    def _refresh_role_dropdown():
        """刷新角色下拉框"""
        loader = RoleLoader()
        roles = loader.scan()
        role_dd.options = []
        current_name = get_current_role_name()
        if roles:
            for r in roles:
                role_dd.options.append(ft.dropdown.Option(key=r.name, text=r.name))
            role_dd.value = current_name if any(
                r.name == current_name for r in roles
            ) else roles[0].name
        else:
            role_dd.options = [ft.dropdown.Option("通用助手", "通用助手")]
            role_dd.value = "通用助手"

    def on_model_dd_change(e):
        """模型下拉框切换"""
        model_id = e.control.value
        if model_id and model_id != "__none__":
            set_current_model_id(model_id)
            page.update()

    def on_role_dd_change(e):
        """角色下拉框切换"""
        role_name = e.control.value
        if role_name:
            set_current_role_name(role_name)
            page.update()

    model_dd = ft.Dropdown(
        width=200,
        label="模型",
        options=[ft.dropdown.Option("__none__", "未配置")],
        value="__none__",
        text_size=13,
    )

    role_dd = ft.Dropdown(
        width=160,
        label="角色",
        options=[ft.dropdown.Option("通用助手", "通用助手")],
        value="通用助手",
        text_size=13,
    )

    page.appbar = ft.AppBar(
        title=ft.Text("AICraft", size=20, weight=ft.FontWeight.BOLD),
        center_title=False,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        actions=[model_dd, role_dd],
    )

    # 初始化下拉框数据
    _refresh_model_dropdown()
    _refresh_role_dropdown()

    # 下拉框变化时刷新
    model_dd.on_change = on_model_dd_change
    role_dd.on_change = on_role_dd_change

    # ----- 创建核心管理器实例（跨视图共享）-----
    mcp_manager = MCPManager()
    mcp_manager.load_connections()

    # 应用退出时清理 stdio 子进程
    import atexit as _atexit
    _atexit.register(mcp_manager.disconnect_all_sync)

    skill_loader = SkillLoader()
    skill_loader.scan()
    rag_engine = RAGEngine()
    rag_engine.load_sources()
    memory_manager = MemoryManager()

    # 共享状态字典
    app_state = {
        "model_dd": model_dd,
        "role_dd": role_dd,
        "refresh_model_dd": _refresh_model_dropdown,
        "refresh_role_dd": _refresh_role_dropdown,
        "mcp_manager": mcp_manager,
        "skill_loader": skill_loader,
        "rag_engine": rag_engine,
        "memory_manager": memory_manager,
        "chat_toggles": {},
    }

    # ── 检查 RAG Embedding 模型是否已缓存，未缓存则后台下载 ──
    import os as _os
    _model_cache = Path(_os.path.expanduser("~")) / ".cache" / "chroma" / "onnx_models" / "all-MiniLM-L6-v2"
    if not (_model_cache / "onnx.tar.gz").exists():
        # 显示 SnackBar 提示
        page.snack_bar = ft.SnackBar(
            ft.Text("⏳ 首次使用RAG，正在后台下载Embedding模型(~80MB)，期间请勿索引...",
                    size=13),
            duration=30000,  # 30秒
        )
        page.snack_bar.open = True
        page.update()

        def _warmup_thread():
            """在后台线程中触发模型下载"""
            try:
                from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
                ef = SentenceTransformerEmbeddingFunction()
                _ = ef(["warmup"])
            except Exception:
                pass

        import concurrent.futures
        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        _executor.submit(_warmup_thread)

    # ----- 构建所有视图（缓存，避免切换标签时状态丢失）-----
    chat_page = build_chat_view(page, app_state)
    skill_page = build_skill_view(page, app_state)
    mcp_page = build_mcp_view(page, app_state)
    rag_page = build_rag_view(page, app_state)
    memory_page = build_memory_view(page, app_state)
    role_page = build_role_view(page, app_state)
    model_page = build_model_view(page, app_state)

    cached_views = [
        chat_page,    # 0: 对话
        skill_page,   # 1: Skill
        mcp_page,     # 2: MCP
        rag_page,     # 3: RAG
        memory_page,  # 4: 记忆
        role_page,    # 5: 角色
        model_page,   # 6: 模型
    ]

    content_area = ft.Container(content=cached_views[0], expand=True)

    # 导航回调中刷新下拉框及 Skill/MCP 列表
    def on_nav_change(e):
        idx = e.control.selected_index
        content_area.content = cached_views[idx]
        _refresh_model_dropdown()
        _refresh_role_dropdown()
        # 切换到 Skill 页时自动刷新
        if idx == 1 and "refresh_skill_list" in app_state:
            app_state["refresh_skill_list"]()
        # 切换到 MCP 页时自动刷新
        if idx == 2 and "refresh_mcp_list" in app_state:
            app_state["refresh_mcp_list"]()
        # 切换到 RAG 页时自动刷新
        if idx == 3 and "refresh_rag_list" in app_state:
            app_state["refresh_rag_list"]()
        page.update()

    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.CHAT, label="对话"),
            ft.NavigationBarDestination(icon=ft.Icons.BUILD, label="Skill"),
            ft.NavigationBarDestination(icon=ft.Icons.POWER, label="MCP"),
            ft.NavigationBarDestination(icon=ft.Icons.LOCAL_LIBRARY, label="RAG"),
            ft.NavigationBarDestination(icon=ft.Icons.PSYCHOLOGY, label="记忆"),
            ft.NavigationBarDestination(icon=ft.Icons.THEATER_COMEDY, label="角色"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label="模型"),
        ],
        selected_index=0,
    )
    page.navigation_bar.on_change = on_nav_change

    page.add(content_area)


if __name__ == "__main__":
    import sys as _sys

    # ── 打包模式 CLI 入口 ──
    # --mcp-server <name>  : 启动 MCP stdio server（代码执行 / 文件管理）
    # --run-script  <path> : 执行 Python 脚本（代码执行器的 Level 2 子进程）
    if len(_sys.argv) >= 2:
        if _sys.argv[1] == "--mcp-server" and len(_sys.argv) >= 3:
            server_name = _sys.argv[2]
            import asyncio as _asyncio
            if server_name == "code_executor":
                from src.mcp_servers.code_executor import main as _mcp_main
                _asyncio.run(_mcp_main())
            elif server_name == "file_manager":
                from src.mcp_servers.file_manager import main as _mcp_main
                _asyncio.run(_mcp_main())
            else:
                print(f"Unknown MCP server: {server_name}", file=_sys.stderr)
                _sys.exit(1)
            _sys.exit(0)

        if _sys.argv[1] == "--run-script" and len(_sys.argv) >= 3:
            script_path = _sys.argv[2]
            _sys.path.insert(0, os.path.dirname(os.path.abspath(script_path)))
            _sys.argv = _sys.argv[1:]  # 让脚本感知到的 argv 以 --run-script 开头
            import runpy
            runpy.run_path(script_path, run_name="__main__")
            _sys.exit(0)

    ft.app(target=main)
