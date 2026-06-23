"""环境检测工具"""

import shutil
import subprocess


def check_node_env() -> dict:
    """检测 Node.js/npx 运行环境

    Returns:
        dict with keys:
        - available (bool): 是否找到 npx
        - path (str|None): npx 可执行文件路径
        - version (str|None): npx 版本号
    """
    npx_path = shutil.which("npx")
    if not npx_path:
        return {"available": False, "path": None, "version": None}

    try:
        result = subprocess.run(
            ["npx", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        version = result.stdout.strip() or result.stderr.strip() or None
    except Exception:
        version = None

    return {
        "available": True,
        "path": npx_path,
        "version": version,
    }
