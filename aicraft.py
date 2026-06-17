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

from src.core.chat_history import save_conversation, load_conversation
from src.core.llm import (
    chat_completion,
    get_available_models,
    get_current_model_config,
    test_connection,
)
from src.core.mcp_client import MCPManager
from src.core.role_loader import RoleLoader
from src.core.skill_loader import SkillLoader
from src.utils.config import (
    MODELS_DIR,
    ROLES_DIR,
    SKILLS_DIR,
    delete_model_config,
    get_current_role_name,
    save_model_config,
    set_current_model_id,
    set_current_role_name,
    set_default_model,
)


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
    toggles_row = ft.Row(
        [
            ft.Switch(label="联网搜索", value=False, label_text_style=ft.TextStyle(size=12)),
            ft.Switch(label="RAG检索", value=True, label_text_style=ft.TextStyle(size=12)),
            ft.Switch(label="记忆注入", value=True, label_text_style=ft.TextStyle(size=12)),
        ],
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
    """处理发送消息"""
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
    page.update()

    # 构建消息列表
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

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    full_text = ""
    error_occurred = False
    tool_calls_pending = {}  # index -> {id, name, arguments}

    # 获取已连接的MCP工具列表
    mcp_tools = None
    mcp_manager: MCPManager | None = app_state.get("mcp_manager") if app_state else None
    if mcp_manager:
        mcp_tools = mcp_manager.get_enabled_tools() or None

    try:
        async for chunk in chat_completion(
            messages,
            model_config=model_config,
            stream=True,
            tools=mcp_tools,
        ):
            # 检查是否被用户停止
            if not get_streaming():
                break

            if isinstance(chunk, str):
                full_text += chunk
                response_text.value = full_text
                response_text.update()
            elif isinstance(chunk, dict) and chunk.get("type") == "tool_call":
                # 累积流式工具调用
                for tc in chunk["data"]:
                    idx = tc.index
                    if idx not in tool_calls_pending:
                        tool_calls_pending[idx] = {"name": "", "arguments": ""}
                        if hasattr(tc, 'id') and tc.id:
                            tool_calls_pending[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_pending[idx]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_pending[idx]["arguments"] += tc.function.arguments
    except Exception as ex:
        error_occurred = True
        response_text.value = f"❌ 调用失败: {str(ex)}"
        response_text.update()
    else:
        # 流式结束后，格式化展示工具调用摘要
        if tool_calls_pending:
            import json as _json
            full_text += "\n\n" + "─" * 30
            for idx in sorted(tool_calls_pending):
                tc = tool_calls_pending[idx]
                full_text += f"\n🔧 工具调用: {tc['name']}\n"
                try:
                    args = _json.loads(tc["arguments"]) if tc["arguments"] else {}
                    full_text += _json.dumps(args, ensure_ascii=False, indent=2) + "\n"
                except Exception:
                    full_text += (tc.get("arguments", "") or "") + "\n"
            response_text.value = full_text
            response_text.update()
        elif full_text == "" and get_streaming():
            response_text.value = "（模型未返回内容）"
            response_text.update()

    # 保存对话历史
    if full_text and not error_occurred:
        try:
            history_msgs = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": full_text},
            ]
            save_conversation(
                history_msgs,
                model=model_config.get("model_id", ""),
                role=role_name,
            )
        except Exception:
            pass  # 保存失败不阻塞

    # 恢复发送按钮
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
                                on_click=lambda e, r=role: _view_role_content(page, r),
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


def _view_role_content(page: ft.Page, role) -> None:
    """查看角色完整内容"""

    def close_dlg(e):
        dlg.open = False
        page.update()

    dlg = ft.AlertDialog(
        title=ft.Text(f"角色: {role.name}"),
        content=ft.Container(
            content=ft.Text(role.content, selectable=True, size=13),
            width=500,
            height=300,
        ),
        actions=[
            ft.TextButton("关闭", on_click=close_dlg),
        ],
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
        content=ft.Column([
            name_field,
            content_field,
            status_text,
        ], width=450, height=320),
        actions=[
            ft.FilledButton("保存", on_click=on_save),
            ft.TextButton("取消", on_click=close_dlg),
        ],
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
    host_field = ft.TextField(label="主机地址", hint_text="例如: 127.0.0.1", text_size=13, value="127.0.0.1")
    port_field = ft.TextField(label="端口", hint_text="例如: 8080", text_size=13, value="8080")
    form_status = ft.Text("", size=12)

    def toggle_form(e):
        form_expand.visible = not form_expand.visible
        form_status.value = ""
        form_expand.update()
        page.update()

    def on_save_mcp(e):
        name = name_field.value.strip()
        host = host_field.value.strip()
        port_str = port_field.value.strip()
        if not name:
            form_status.value = "❌ 连接名称不能为空"
            form_status.color = ft.Colors.ERROR; form_status.update(); return
        if not host:
            form_status.value = "❌ 主机地址不能为空"
            form_status.color = ft.Colors.ERROR; form_status.update(); return
        try:
            port = int(port_str)
        except ValueError:
            form_status.value = "❌ 端口必须是数字"
            form_status.color = ft.Colors.ERROR; form_status.update(); return

        manager.add_connection(name, host, port)
        name_field.value = ""; host_field.value = "127.0.0.1"; port_field.value = "8080"
        form_expand.visible = False; form_status.value = ""
        refresh_mcp_list()

    # 添加表单按钮
    def toggle_form_btn(e):
        form_expand.visible = not form_expand.visible
        form_status.value = ""
        form_expand.update()
        page.update()

    form_expand = ft.Column([
        ft.Text("新增MCP连接", size=15, weight=ft.FontWeight.BOLD),
        name_field,
        ft.Row([host_field, port_field]),
        form_status,
        ft.Row([
            ft.FilledButton("保存", icon=ft.Icons.SAVE, on_click=on_save_mcp),
            ft.TextButton("取消", on_click=toggle_form_btn),
        ]),
    ], visible=False)

    def refresh_mcp_list():
        """刷新MCP连接列表"""
        mcp_list.controls.clear()
        connections = manager.load_connections()
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
                            "点击上方「添加MCP」按钮，填写MCP Server的地址和端口",
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
        size=12,
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
                    ft.Text(conn.name, size=15, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{conn.host}:{conn.port}  |  工具: {len(conn.tools)}",
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
    return ft.Column(
        [
            ft.Row([ft.Button("添加数据源", icon=ft.Icons.ADD)]),
            ft.Divider(),
            ft.Container(
                content=ft.Text("RAG数据源列表 - Phase 3 开发中", size=16),
                expand=True,
                alignment=ft.Alignment.CENTER,
            ),
        ],
        expand=True,
    )


def build_memory_view(page: ft.Page, app_state: dict) -> ft.Column:
    return ft.Column(
        [
            ft.Row([ft.Button("打开记忆文件夹", icon=ft.Icons.FOLDER_OPEN)]),
            ft.Divider(),
            ft.Container(
                content=ft.Text("记忆管理 - Phase 3 开发中", size=16),
                expand=True,
                alignment=ft.Alignment.CENTER,
            ),
        ],
        expand=True,
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
    skill_loader = SkillLoader()
    skill_loader.scan()

    # 共享状态字典
    app_state = {
        "model_dd": model_dd,
        "role_dd": role_dd,
        "refresh_model_dd": _refresh_model_dropdown,
        "refresh_role_dd": _refresh_role_dropdown,
        "mcp_manager": mcp_manager,
        "skill_loader": skill_loader,
    }

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
    # 浏览器模式，无需下载Flet桌面客户端
    ft.run(main, view=ft.AppView.WEB_BROWSER)
