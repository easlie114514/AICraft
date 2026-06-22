"""AICraft 桌面窗口启动器 — 使用 pywebview 加载前端

开发模式: 需要同时运行 Vite dev server (npm run dev)
生产模式: python run.py (FastAPI 托管前端 dist/)
"""

import os
import threading
import time

# 阻止 litellm 在 import 时同步拉取远程模型价格表（国内 GitHub 被墙会导致超时 30-60s）
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import uvicorn
import webview

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
    """在后台线程启动 FastAPI 服务"""
    os.chdir(ROOT)
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8765,
        log_level="warning",
    )


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
