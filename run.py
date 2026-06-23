"""AICraft 桌面窗口启动器 — 使用 pywebview 加载前端

开发模式: 需要同时运行 Vite dev server (npm run dev)
生产模式: python run.py (FastAPI 托管前端 dist/)
打包模式: AICraft.exe (PyInstaller onedir)
"""

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

    # 创建 frameless 窗口，js_api 暴露给前端 window.pywebview.api
    webview.create_window(
        title="AICraft",
        url=url,
        js_api=WindowAPI(),
        width=1280,
        height=800,
        min_size=(800, 600),
        frameless=True,
        easy_drag=True,
    )

    webview.start(debug=False)


if __name__ == "__main__":
    main()
