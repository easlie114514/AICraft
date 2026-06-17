"""AICraft - 个人桌面AI能力启动器

主入口文件，启动Flet应用
"""

import flet as ft
from src.utils.config import BASE_DIR


def main(page: ft.Page):
    """应用主页面"""
    page.title = "AICraft"
    page.window.width = 1200
    page.window.height = 800
    page.window.min_width = 900
    page.window.min_height = 600
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.padding = 0

    # 顶部标题栏
    page.appbar = ft.AppBar(
        title=ft.Text("AICraft", size=20, weight=ft.FontWeight.BOLD),
        center_title=False,
        bgcolor=ft.colors.SURFACE_VARIANT,
        actions=[
            ft.Dropdown(
                width=200,
                label="模型",
                options=[ft.dropdown.Option("未配置")],
                value="未配置",
                text_size=13,
            ),
            ft.Dropdown(
                width=160,
                label="角色",
                options=[ft.dropdown.Option("通用助手"), ft.dropdown.Option("测试工程师")],
                value="通用助手",
                text_size=13,
            ),
        ],
    )

    # 各标签页内容（占位，后续Phase填充）
    def chat_view():
        """对话页"""
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Switch(label="联网搜索", value=False),
                        ft.Switch(label="RAG检索", value=True),
                        ft.Switch(label="记忆注入", value=True),
                    ],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Container(
                    content=ft.Text("对话区域 - Phase 1 开发中", size=16),
                    expand=True,
                    alignment=ft.alignment.center,
                ),
                ft.Row(
                    [
                        ft.TextField(
                            hint_text="输入消息...",
                            expand=True,
                            multiline=True,
                            min_lines=1,
                            max_lines=4,
                        ),
                        ft.FilledButton("发送", icon=ft.icons.SEND),
                    ],
                ),
            ],
            expand=True,
        )

    def skill_view():
        """Skill页"""
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.ElevatedButton("打开Skill文件夹", icon=ft.icons.FOLDER_OPEN),
                        ft.Text("将Skill文件夹放入目录即可自动识别", color=ft.colors.ON_SURFACE_VARIANT),
                    ],
                ),
                ft.Divider(),
                ft.Text("Skill列表 - Phase 2 开发中", size=16),
            ],
            expand=True,
        )

    def mcp_view():
        """MCP页"""
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.ElevatedButton("添加MCP", icon=ft.icons.ADD),
                    ],
                ),
                ft.Divider(),
                ft.Text("MCP连接列表 - Phase 2 开发中", size=16),
            ],
            expand=True,
        )

    def rag_view():
        """RAG页"""
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.ElevatedButton("添加数据源", icon=ft.icons.ADD),
                    ],
                ),
                ft.Divider(),
                ft.Text("RAG数据源列表 - Phase 3 开发中", size=16),
            ],
            expand=True,
        )

    def memory_view():
        """记忆页"""
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.ElevatedButton("打开记忆文件夹", icon=ft.icons.FOLDER_OPEN),
                    ],
                ),
                ft.Divider(),
                ft.Text("记忆管理 - Phase 3 开发中", size=16),
            ],
            expand=True,
        )

    def role_view():
        """角色页"""
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.ElevatedButton("打开角色文件夹", icon=ft.icons.FOLDER_OPEN),
                    ],
                ),
                ft.Divider(),
                ft.Text("角色列表 - Phase 1 开发中", size=16),
            ],
            expand=True,
        )

    def model_view():
        """模型页"""
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.ElevatedButton("添加模型", icon=ft.icons.ADD),
                    ],
                ),
                ft.Divider(),
                ft.Text("模型配置 - Phase 1 开发中", size=16),
            ],
            expand=True,
        )

    # 底部导航标签
    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.icons.CHAT, label="对话"),
            ft.NavigationBarDestination(icon=ft.icons.BUILD, label="Skill"),
            ft.NavigationBarDestination(icon=ft.icons.POWER, label="MCP"),
            ft.NavigationBarDestination(icon=ft.icons.LOCAL_LIBRARY, label="RAG"),
            ft.NavigationBarDestination(icon=ft.icons.PSYCHOLOGY, label="记忆"),
            ft.NavigationBarDestination(icon=ft.icons.THEATER_COMEDY, label="角色"),
            ft.NavigationBarDestination(icon=ft.icons.SETTINGS, label="模型"),
        ],
        selected_index=0,
    )

    # 页面切换
    views = [chat_view, skill_view, mcp_view, rag_view, memory_view, role_view, model_view]
    content_area = ft.Container(content=chat_view(), expand=True)

    def on_nav_change(e):
        idx = e.control.selected_index
        content_area.content = views[idx]()
        page.update()

    page.navigation_bar.on_change = on_nav_change

    page.add(content_area)


if __name__ == "__main__":
    ft.app(target=main)
