# -*- mode: python ; coding: utf-8 -*-
"""AICraft PyInstaller 打包配置 — OneDir 模式"""

import sys
from pathlib import Path
ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / 'run.py')],
    pathex=[],
    binaries=[],
    datas=[
        # 出厂只读数据 → _internal/data/
        (str(ROOT / 'skills'), 'data/skills'),
        (str(ROOT / 'roles'), 'data/roles'),
        (str(ROOT / 'rag'), 'data/rag'),
        (str(ROOT / 'models' / 'onnx'), 'data/models/onnx'),
        (str(ROOT / 'frontend' / 'dist'), 'data/frontend/dist'),
        (str(ROOT / 'config' / 'defaults'), 'data/config/defaults'),
        # MCP stdio server 脚本（打包后 sys.path 中找不到，需作为文件暴露）
        (str(ROOT / 'src' / 'mcp_servers' / 'code_executor.py'), 'data/src/mcp_servers'),
    ],
    hiddenimports=[
        # Web 框架
        'fastapi', 'uvicorn', 'websockets', 'starlette',
        # ChromaDB（chromadb.api.rust 等通过 importlib 动态加载）
        'chromadb', 'chromadb.api.rust', 'chromadb.api.segment',
        'chromadb.telemetry.product.posthog', 'chromadb.telemetry.product.events',
        'chromadb.db.impl.sqlite',
        'onnxruntime', 'tokenizers', 'tqdm',
        # HTTP
        'httpx', 'httpcore',
        # 文档解析
        'langchain_text_splitters', 'PyPDF2', 'docx',
        # LLM
        'anthropic',
        # 桌面
        'pywebview', 'pyperclip',
        # 工具
        'watchdog', 'rich', 'tenacity', 'orjson',
        # MCP
        'mcp',
        # AICraft backend (uvicorn 字符串引用，需显式声明)
        'backend', 'backend.main', 'backend.deps', 'backend.chat_ws',
        'backend.routers', 'backend.routers.rag', 'backend.routers.roles',
        'backend.routers.search', 'backend.routers.models', 'backend.routers.memory',
        'backend.routers.mcp', 'backend.routers.skills',
        # AICraft src (部分模块可能被静态分析遗漏)
        'src', 'src.core', 'src.utils', 'src.ui',
        'src.core.llm', 'src.core.agent_loop', 'src.core.openai_client',
        'src.core.mcp_client', 'src.core.role_loader', 'src.core.skill_loader',
        'src.core.memory', 'src.core.rag_engine', 'src.core.embedding',
        'src.core.chat_history', 'src.core.model_selector', 'src.core.context_budget',
        'src.core.web_search',
        'src.utils.config', 'src.utils.env',
        'src.mcp_servers', 'src.mcp_servers.code_executor',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'pandas', 'numpy.tests',
        'scipy', 'PIL', 'cv2',
        # 巨型依赖：chromadb embedding 的 sentence_transformer 路径会拉进来，
        # 但本地 ONNX 模式不需要它们
        'torch', 'transformers', 'sentence_transformers', 'sentence_transformers',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],                   # onedir: 空列表，资源由 COLLECT 管理
    [],
    [],
    [],
    name='AICraft',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'logo_item.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AICraft',
)
