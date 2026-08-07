"""AICraft 桌面窗口启动器 — 使用 pywebview 加载前端

开发模式: 需要同时运行 Vite dev server (npm run dev)
生产模式: python run.py (FastAPI 托管前端 dist/)
打包模式: AICraft.exe (PyInstaller onedir)
"""

import ctypes
import logging
import os
import sys
import threading
import time

import pyperclip

# ── 日志配置（写入文件，方便排查问题）──
def _setup_logging():
    """配置根日志：aictaft.log 写入 exe 同级目录"""
    from pathlib import Path
    if getattr(sys, 'frozen', False):
        log_dir = Path(os.path.dirname(os.path.abspath(sys.executable)))
    else:
        log_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    log_file = log_dir / "aicraft.log"
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
        ],
    )
    # 确保 aicraft logger 也传播到 root
    logging.getLogger("aicraft").setLevel(logging.WARNING)

_setup_logging()

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

    def upgrade_restart(self, staging_dir: str, target_dir: str = ""):
        """一键升级：写入升级 bat → 分离启动 → 关闭窗口。

        bat 脚本等待旧进程退出后 robocopy 覆盖文件并重启。
        与 restart() 的区别：增加了 robocopy 镜像同步步骤。

        Args:
            staging_dir: 暂存目录路径
            target_dir: 升级目标目录（空字符串=使用默认 USER_DIR）
        """
        import subprocess
        import tempfile
        from pathlib import Path
        from src.utils.upgrader import build_upgrade_bat

        _target = Path(target_dir) if target_dir else None
        logger = logging.getLogger("aicraft")

        logger.warning("upgrade_restart called: staging=%s target=%s", staging_dir, _target or str(USER_DIR))

        bat_content = build_upgrade_bat(staging_dir, _target, pid=os.getpid())
        logger.warning("bat content built, %d chars", len(bat_content))

        if getattr(sys, 'frozen', False):
            fd, bat_path = tempfile.mkstemp(suffix='.bat', prefix='_aicraft_upgrade_')
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(bat_content)
            logger.warning("bat written (frozen): %s", bat_path)
            subprocess.Popen(
                ['cmd', '/c', bat_path],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            # 开发模式：bat 写到项目根目录
            bat_path = os.path.join(ROOT, "_aicraft_upgrade.bat")
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(bat_content)
            logger.warning("bat written (dev): %s", bat_path)
            subprocess.Popen(
                ['cmd', '/c', bat_path],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )

        logger.warning("bat spawned, closing window...")

        # 关闭当前窗口
        win = webview.active_window()
        if win:
            win.destroy()
        # 暴力退出立即释放文件句柄，让 bat 的 robocopy 能覆盖 exe 和 dll
        os._exit(0)

    def restart(self):
        """重启应用：等旧进程退出后重新启动，新窗口自动置顶"""
        import subprocess

        if getattr(sys, 'frozen', False):
            # 打包模式：pythonw.exe 不存在于 PyInstaller onedir 输出中。
            # 改用临时 bat 文件避免 cmd 嵌套引号冲突，同时设置
            # AICRAFT_RESTART 环境变量让新进程启动后自动置顶窗口。
            import tempfile
            fd, bat_path = tempfile.mkstemp(suffix='.bat', prefix='_aicraft_restart_')
            with os.fdopen(fd, 'w') as f:
                f.write('@echo off\n')
                f.write('timeout /t 2 /nobreak >nul\n')
                f.write('set AICRAFT_RESTART=1\n')
                f.write(f'start "" "{sys.executable}"\n')
            subprocess.Popen(
                ['cmd', '/c', bat_path],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )
        else:
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            helper_code = (
                "import subprocess, sys, time, os\n"
                "time.sleep(2)\n"
                "env = os.environ.copy()\n"
                'env[\"AICRAFT_RESTART\"] = \"1\"\n'
                f"subprocess.Popen({[sys.executable, os.path.join(ROOT, 'run.py')]!r},"
                f" cwd={ROOT!r},"
                " env=env,"
                " creationflags=0x08000000 if sys.platform == 'win32' else 0)\n"
            )
            subprocess.Popen(
                [pythonw, "-c", helper_code],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            )

        # 关闭当前窗口，主进程退出释放端口
        win = webview.active_window()
        if win:
            win.destroy()

    def pick_directory(self) -> str | None:
        """打开原生文件夹选择对话框，返回用户选择的目录路径，取消返回 None"""
        win = webview.active_window()
        if win is None:
            return None
        selected = win.create_file_dialog(webview.FOLDER_DIALOG)
        if selected and len(selected) > 0:
            return selected[0]
        return None

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

    def get_clipboard(self) -> str:
        """读取系统剪贴板文本（通过 pyperclip，无需浏览器权限）"""
        try:
            return pyperclip.paste()
        except Exception:
            return ""


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
    win_w, win_h = 1664, 1040
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

    # 重启后自动将窗口置于最前（AICRAFT_RESTART 由 restart() 中的帮助进程设置）
    if os.environ.get("AICRAFT_RESTART"):
        def _bring_to_front():
            _t = 0.0
            while _t < 3.0:
                hwnd = ctypes.windll.user32.FindWindowW(None, "AICraft")
                if hwnd:
                    # ALT 键技巧绕过 Windows 前台锁定，然后置顶窗口
                    ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # VK_MENU down
                    ctypes.windll.user32.keybd_event(0x12, 0, 0x2, 0)  # VK_MENU up
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                    ctypes.windll.user32.BringWindowToTop(hwnd)
                    break
                time.sleep(0.2)
                _t += 0.2
        threading.Thread(target=_bring_to_front, daemon=True).start()

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
