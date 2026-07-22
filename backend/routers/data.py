"""数据导出/导入 API — /api/data/*"""

from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.utils.config import USER_DIR
from src.utils.data_utils import create_export_zip, extract_import_zip

router = APIRouter(tags=["data"])

# 导出存放目录
EXPORTS_DIR = USER_DIR / "exports"


class ImportFromPathRequest(BaseModel):
    path: str


# ── 导出 ──


@router.post("/data/export")
async def export_data():
    """保存备份 ZIP 到 USER_DIR/exports/，返回本地路径

    不依赖浏览器下载，直接存为本地文件。
    TUI / headless / 脚本场景均可通过 API 调用。
    """
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = EXPORTS_DIR / f"AICraft_Backup_{date_str}.zip"

    result = create_export_zip(output_path)

    if result.errors:
        # 有非致命错误但 ZIP 仍可能部分成功
        pass

    if result.file_count == 0 and result.errors:
        return {
            "ok": False,
            "error": f"导出失败: {'; '.join(result.errors)}",
        }

    size_mb = round(result.size_bytes / (1024 * 1024), 1)
    return {
        "ok": True,
        "path": str(output_path),
        "file_count": result.file_count,
        "size_mb": size_mb,
        "warnings": result.errors if result.errors else None,
    }


# ── 导入（上传文件）──


@router.post("/data/import")
async def import_data(file: UploadFile = File(...)):
    """从上传的 ZIP 文件导入数据到 USER_DIR

    使用 multipart/form-data，适合浏览器直接上传。
    导入策略：目标已存在的文件跳过，不覆盖已有数据。
    """
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="请选择 .zip 格式的备份文件")

    temp_path = Path(tempfile.gettempdir()) / f"aicraft_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"

    try:
        content = await file.read()
        temp_path.write_bytes(content)

        if temp_path.stat().st_size == 0:
            temp_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="上传的文件为空")

        result = extract_import_zip(temp_path)
        return _build_import_response(result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {e}") from e
    finally:
        temp_path.unlink(missing_ok=True)


# ── 导入（本地路径）──


@router.post("/data/import-from-path")
async def import_from_path(body: ImportFromPathRequest):
    """从本地文件路径导入 ZIP 到 USER_DIR

    适合脚本、命令行或非浏览器场景直接指定本地备份文件路径。
    """
    zip_path = Path(body.path)

    if not zip_path.exists():
        raise HTTPException(status_code=400, detail=f"文件不存在: {body.path}")

    if not zip_path.suffix.lower() == ".zip":
        raise HTTPException(status_code=400, detail="请选择 .zip 格式的备份文件")

    try:
        result = extract_import_zip(zip_path)
        return _build_import_response(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {e}") from e


# ── 辅助 ──


def _build_import_response(result) -> dict:
    """将 ImportResult 转为 API 响应"""
    if result.failed and result.extracted == 0 and result.overwritten == 0 and "不是有效的" in str(result.failed[0]):
        raise HTTPException(status_code=400, detail=result.failed[0])

    return {
        "ok": True,
        "extracted": result.extracted,
        "overwritten": result.overwritten,
        "failed": result.failed,
    }
