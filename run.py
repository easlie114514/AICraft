"""AICraft 桌面窗口启动器 — 使用 pywebview 加载前端

开发模式: 需要同时运行 Vite dev server (npm run dev)
生产模式: python run.py (FastAPI 托管前端 dist/)
打包模式: AICraft.exe (PyInstaller onedir)
"""

import ctypes
import os
import sys
import threading
import time

# 阻止 litellm 在 import 时同步拉取远程模型价格表（国内 GitHub 被墙会导致超时 30-60s）
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import uvicorn
import webview

# 确定运行根目录和前端路径
if getattr(sys, 'frozen', False):
    # PyInstaller 打包模式
    ROOT = os.path.dirname(os.path.abspath(sys.executable))
    from src.utils.config import FRONTEND_DIST as _frontend_dist
    FRONTEND_DIST = str(_frontend_dist)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))
    FRONTEND_DIST = os.path.join(ROOT, "frontend", "dist")

FRONTEND_INDEX = os.path.join(FRONTEND_DIST, "index.html")


class WindowAPI:
    """暴露给前端 JS 的窗口控制 API (通过 window.pywebview.api 调用)"""

    def __init__(self):
        self._hwnd = None
        self._scale = 1.0

    def _ensure_hwnd(self):
        """缓存窗口句柄和 DPI（纯 Win32，线程安全）"""
        if self._hwnd is None:
            self._hwnd = ctypes.windll.user32.GetForegroundWindow()
            if self._hwnd:
                dpi = ctypes.windll.user32.GetDpiForWindow(self._hwnd)
                self._scale = dpi / 96.0
        return self._hwnd

    def minimize(self):
        win = webview.active_window()
        if win:
            win.minimize()

    def toggle_fullscreen(self):
        win = webview.active_window()
        if win:
            win.toggle_fullscreen()

    def close(self):
        win = webview.active_window()
        if win:
            win.destroy()

    def resize_window(self, edge: str, dx: int, dy: int):
        """拖拽边框缩放窗口（纯 Win32 API，线程安全）"""
        hwnd = self._ensure_hwnd()
        if not hwnd:
            return

        user32 = ctypes.windll.user32

        class RECT(ctypes.Structure):
            _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                        ('right', ctypes.c_long), ('bottom', ctypes.c_long)]
        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        x, y = rect.left, rect.top
        w, h = rect.right - rect.left, rect.bottom - rect.top

        # JS 传入逻辑像素 delta → 物理像素
        dx_px = int(dx * self._scale)
        dy_px = int(dy * self._scale)

        if 'left' in edge:
            x += dx_px; w -= dx_px
        elif 'right' in edge:
            w += dx_px
        if 'top' in edge:
            y += dy_px; h -= dy_px
        elif 'bottom' in edge:
            h += dy_px

        # 最小尺寸（逻辑 400×300 → 物理）
        min_w, min_h = int(400 * self._scale), int(300 * self._scale)
        if w < min_w:
            if 'left' in edge: x -= (min_w - w)
            w = min_w
        if h < min_h:
            if 'top' in edge: y -= (min_h - h)
            h = min_h

        # SWP_NOZORDER | SWP_NOACTIVATE 避免焦点切换
        user32.SetWindowPos(hwnd, None, x, y, w, h, 0x0004 | 0x0010)


def start_server():
    """在后台线程启动 FastAPI 服务（端口被占用时自动等待重试）"""
    os.chdir(ROOT)
    max_retries = 10
    for attempt in range(max_retries):
        try:
            uvicorn.run(
                "backend.main:app",
                host="127.0.0.1",
                port=8765,
                log_level="warning",
            )
            return  # 正常退出
        except SystemExit as e:
            if e.code == 1 and attempt < max_retries - 1:
                # exit(1) 通常是端口绑定失败
                print(f"[AICraft] 端口 8765 被占用，等待清理... ({attempt + 1}/{max_retries})")
                time.sleep(3)
            else:
                return  # exit(0) 正常停止，或重试次数耗尽
        except KeyboardInterrupt:
            return


def main():
    # 启动后端服务
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    time.sleep(2)

    # 确定前端 URL
    if os.path.exists(FRONTEND_INDEX):
        url = "http://127.0.0.1:8765"
    else:
        print("[AICraft] 开发模式 — 使用 Vite dev server (请先运行 npm run dev)")
        url = "http://127.0.0.1:5173"

    # 配置拖拽区域：仅 .app-region-drag 的直接命中可拖拽（排除子元素）
    webview.settings['DRAG_REGION_SELECTOR'] = '.app-region-drag'
    webview.settings['DRAG_REGION_DIRECT_TARGET_ONLY'] = True

    # 获取屏幕尺寸，计算窗口居中坐标
    user32 = ctypes.windll.user32
    screen_w = user32.GetSystemMetrics(0)
    screen_h = user32.GetSystemMetrics(1)
    win_w, win_h = 1280, 800
    x = (screen_w - win_w) // 2
    y = (screen_h - win_h) // 2

    # 创建 frameless 窗口，js_api 暴露给前端 window.pywebview.api
    webview.create_window(
        title="AICraft",
        url=url,
        js_api=WindowAPI(),
        width=win_w,
        height=win_h,
        x=x,
        y=y,
        min_size=(800, 600),
        frameless=True,
        easy_drag=False,
    )

    webview.start(debug=False)


if __name__ == "__main__":
    # ── 子进程模式：MCP stdio server / 脚本执行 ──
    # 打包后 exe 通过 --mcp-server <name> 自举启动内置 MCP 服务器，
    # 或通过 --run-script <path> 执行临时脚本。
    # 这些模式必须走纯 stdio 通信，不能启动 webview 窗口。
    if len(sys.argv) >= 2:
        if sys.argv[1] == "--mcp-server" and len(sys.argv) >= 3:
            server_name = sys.argv[2]
            import asyncio as _asyncio
            if server_name == "code_executor":
                from src.mcp_servers.code_executor import main as _mcp_main
                _asyncio.run(_mcp_main())
            elif server_name == "file_manager":
                from src.mcp_servers.file_manager import main as _mcp_main
                _asyncio.run(_mcp_main())
            else:
                print(f"Unknown MCP server: {server_name}", file=sys.stderr)
                sys.exit(1)
            sys.exit(0)

        if sys.argv[1] == "--run-script" and len(sys.argv) >= 3:
            script_path = sys.argv[2]
            sys.path.insert(0, os.path.dirname(os.path.abspath(script_path)))
            sys.argv = sys.argv[1:]  # 让脚本感知到的 argv 以 --run-script 开头
            import runpy as _runpy
            _runpy.run_path(script_path, run_name="__main__")
            sys.exit(0)

    main()
