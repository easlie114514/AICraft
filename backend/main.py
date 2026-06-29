"""FastAPI 应用入口"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.deps import init_deps, get_deps
from backend.routers import models, roles, skills, mcp, rag, memory, search, settings, updater
from backend.chat_ws import router as chat_ws_router
from src.utils import config
from src.utils.config import FRONTEND_DIST


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    deps = init_deps()
    asyncio.create_task(deps.rag_engine.warmup())
    connect_task = asyncio.create_task(deps.mcp_manager.connect_all_enabled())
    yield
    # 先取消 connect 任务（避免 anyio cancel scope 跨 task 报错）
    connect_task.cancel()
    try:
        await connect_task
    except (asyncio.CancelledError, Exception):
        pass
    # 然后清理所有 stdio 子进程（在当前 task 中执行 __aexit__）
    try:
        await deps.mcp_manager.disconnect_all()
    except Exception:
        pass


app = FastAPI(title="AICraft API", version=config.CURRENT_VERSION, lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8765",
        "http://127.0.0.1:8765",
        "app://.",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(models.router, prefix="/api")
app.include_router(roles.router, prefix="/api")
app.include_router(skills.router, prefix="/api")
app.include_router(mcp.router, prefix="/api")
app.include_router(rag.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(updater.router, prefix="/api")
app.include_router(chat_ws_router, prefix="/api")

# 生产模式：挂载前端静态资源
frontend_assets = FRONTEND_DIST / "assets"
frontend_fonts = FRONTEND_DIST / "fonts"
if frontend_assets.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_assets)), name="assets")
if frontend_fonts.exists():
    app.mount("/fonts", StaticFiles(directory=str(frontend_fonts)), name="fonts")

# 生产模式：根路径返回 index.html
@app.get("/")
async def root():
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "AICraft API - 开发模式请使用 Vite dev server (localhost:5173)"}


# 生产模式：兜底服务 dist/ 根目录下的静态文件（如 logo.png / favicon 等）
@app.get("/{filename:path}")
async def static_root(filename: str):
    file_path = FRONTEND_DIST / filename
    # 仅服务 dist/ 根目录的直接文件，子目录走 /assets /fonts 挂载
    if file_path.exists() and file_path.is_file() and file_path.parent == FRONTEND_DIST:
        return FileResponse(file_path)
    # 未匹配的文件返回 index.html（SPA fallback）
    index_path = FRONTEND_DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Not found", "path": filename}


@app.get("/api/health")
async def health():
    deps = get_deps()
    return {
        "status": "ok",
        "mcp_connections": len(deps.mcp_manager.connections),
        "rag_sources": len(deps.rag_engine.sources),
    }
