"""数据导出/导入工具 — 纯 I/O 函数，无框架依赖

导出：将 USER_DIR 下指定目录/文件打包为 ZIP，写入 manifest.json
导入：从 ZIP 合并到 USER_DIR，跳过已存在文件，防护路径遍历
"""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from src.utils.config import (
    USER_DIR,
    ROLES_DIR,
    SKILLS_DIR,
    USER_ROLES_DIR,
    USER_SKILLS_DIR,
    VERSION_FILE,
    CURRENT_VERSION,
    load_json,
)

# ═══════════════════════════════════════════════════════════
# 出厂数据检测（带缓存）
# ═══════════════════════════════════════════════════════════

_FACTORY_ROLE_NAMES: set[str] | None = None
_FACTORY_SKILL_NAMES: set[str] | None = None


def _get_factory_role_names() -> set[str]:
    """返回出厂角色名称集合（带缓存）

    打包模式下 ROLES_DIR ≠ USER_ROLES_DIR，扫描 ROLES_DIR 获取出厂列表。
    开发模式下两者相同，使用硬编码基线。
    """
    global _FACTORY_ROLE_NAMES
    if _FACTORY_ROLE_NAMES is not None:
        return _FACTORY_ROLE_NAMES
    names = {"Aiki", "通用助手"}
    if ROLES_DIR.resolve() != USER_ROLES_DIR.resolve() and ROLES_DIR.exists():
        for d in ROLES_DIR.iterdir():
            if d.is_dir() and (d / "role.md").exists():
                names.add(d.name)
    _FACTORY_ROLE_NAMES = names
    return names


def _get_factory_skill_names() -> set[str]:
    """返回出厂 Skill 名称集合（带缓存）"""
    global _FACTORY_SKILL_NAMES
    if _FACTORY_SKILL_NAMES is not None:
        return _FACTORY_SKILL_NAMES
    names: set[str] = set()
    if SKILLS_DIR.resolve() != USER_SKILLS_DIR.resolve() and SKILLS_DIR.exists():
        for d in SKILLS_DIR.iterdir():
            if d.is_dir() and not d.name.startswith(".") and (d / "SKILL.md").exists():
                names.add(d.name)
    _FACTORY_SKILL_NAMES = names
    return names


# ── 导出清单 ──
# 格式: (rel_path, is_dir, exclude_names)
#   rel_path: USER_DIR 下的相对路径
#   is_dir: True=递归目录, False=单文件
#   exclude_names: 目录时排除这些顶层子目录/文件名（factory 角色/Skill），None=全部包含
#
# 注意：
#   - chroma_db/ 不导出（向量分片，可以从 RAG 源重建）
#   - models/onnx/ 不导出（下载的嵌入模型，可重新下载）
#   - models/ 只导出 JSON 配置，排除 onnx/ 子目录
#   - workspace/ 不导出（用户未要求）
#   - 出厂角色和 Skill 不导出

_EXPORT_ITEMS: list[tuple[str, bool, set[str] | None]] = [
    # ── config ──
    ("config/app.json", False, None),
    ("config/permissions.json", False, None),
    ("config/rag_config.json", False, None),
    ("config/projects.json", False, None),
    ("config/profiles", True, None),  # mcp_connections.json, model.json
    # ── models: JSON 配置（含 API Key），排除 onnx/ ──
    ("models", True, {"onnx"}),
    # ── memory: 对话历史 + 短期/长期记忆 + 反馈 ──
    ("memory", True, None),
    # ── roles: 仅用户自建，排除出厂角色 ──
    ("roles", True, _get_factory_role_names()),
    # ── skills: 仅用户自建，排除出厂 Skill ──
    ("skills", True, _get_factory_skill_names()),
    # ── rag: 数据源配置 + 源文件（不含 chroma_db 分片）──
    ("rag", True, None),
    # ── 单文件 ──
    ("app.md", False, None),
    (".version", False, None),
]


# ── 迁移清单（从旧版目录拷贝用户数据）──
# 与 _EXPORT_ITEMS 互为镜像，差异：
#   - 包含 chroma_db/ 和 workspace/（export 因体积原因跳过）
#   - 包含 exports/（历史备份归档）
#   - config/ 按整目录处理，不做单文件枚举
#   - 同样排除 onnx/（嵌入模型）和出厂角色/Skill

_MIGRATION_ITEMS: list[tuple[str, bool, set[str] | None]] = [
    ("config", True, None),
    ("models", True, {"onnx"}),
    ("memory", True, None),
    ("chroma_db", True, None),
    ("workspace", True, None),
    ("roles", True, _get_factory_role_names()),
    ("skills", True, _get_factory_skill_names()),
    ("rag", True, None),
    ("exports", True, None),
    ("app.md", False, None),
    (".version", False, None),
]


# ═══════════════════════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════════════════════


@dataclass
class ExportResult:
    path: Path
    file_count: int = 0
    size_bytes: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    extracted: int = 0    # 新增文件
    overwritten: int = 0  # 覆盖还原
    failed: list[str] = field(default_factory=list)


@dataclass
class MigrationResult:
    migrated: list[str] = field(default_factory=list)   # 已迁移的相对路径
    skipped: list[str] = field(default_factory=list)    # 目标已存在的路径
    errors: list[str] = field(default_factory=list)     # 拷贝失败的错误信息
    old_version: str = ""                                # 检测到的旧版本号


# ═══════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════


def create_export_zip(destination: Path, user_dir: Path = USER_DIR) -> ExportResult:
    """单遍导出：遍历 _EXPORT_ITEMS，写入 ZIP 并累计统计，最后写入 manifest.json

    Args:
        destination: 目标 ZIP 文件路径（调用方确保父目录存在）
        user_dir: 用户数据根目录，默认 USER_DIR

    Returns:
        ExportResult(path, file_count, size_bytes, errors)
    """
    result = ExportResult(path=destination)
    errors: list[str] = []

    try:
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zf:
            for rel_path, is_dir, exclude_names in _EXPORT_ITEMS:
                src = user_dir / rel_path
                if not src.exists():
                    continue
                try:
                    if not is_dir:
                        # 单文件
                        zf.write(src, f"data/{rel_path}")
                        result.file_count += 1
                        result.size_bytes += src.stat().st_size
                    else:
                        # 递归目录，可选排除指定顶层名称
                        for f in src.rglob("*"):
                            if not f.is_file():
                                continue
                            # 检查是否在排除列表中
                            if exclude_names:
                                rel_to_src = f.relative_to(src)
                                top_name = rel_to_src.parts[0] if rel_to_src.parts else ""
                                if top_name in exclude_names:
                                    continue
                            try:
                                arcname = f"data/{rel_path}/{f.relative_to(src).as_posix()}"
                                zf.write(f, arcname)
                                result.file_count += 1
                                result.size_bytes += f.stat().st_size
                            except OSError as e:
                                errors.append(f"跳过文件 {f}: {e}")
                except OSError as e:
                    errors.append(f"跳过 {rel_path}: {e}")

            # 写入 manifest
            app_version = CURRENT_VERSION
            if VERSION_FILE.exists():
                vdata = load_json(VERSION_FILE)
                app_version = vdata.get("version", CURRENT_VERSION)

            manifest = {
                "format": "aicraft-backup",
                "app_version": app_version,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "file_count": result.file_count,
            }
            zf.writestr("manifest.json", _json_dumps(manifest))

        # 更新最终 ZIP 大小
        if destination.exists():
            result.size_bytes = destination.stat().st_size
        result.errors = errors

    except Exception as e:
        result.errors.append(f"导出失败: {e}")

    return result


# ═══════════════════════════════════════════════════════════
# 导入
# ═══════════════════════════════════════════════════════════


def extract_import_zip(zip_path: Path, target_dir: Path = USER_DIR) -> ImportResult:
    """从 ZIP 恢复到 target_dir。先验证 manifest.json，逐文件落地，覆盖已存在

    导入即为还原——已存在的文件会被覆盖，确保配置状态完整恢复。

    Args:
        zip_path: 源 ZIP 文件路径
        target_dir: 目标数据根目录，默认 USER_DIR

    Returns:
        ImportResult(extracted, overwritten, failed)
    """
    result = ImportResult()

    if not zip_path.exists():
        result.failed.append("文件不存在")
        return result

    try:
        zf = zipfile.ZipFile(zip_path, "r")
    except zipfile.BadZipFile:
        result.failed.append("文件损坏，不是有效的 ZIP 压缩包")
        return result

    try:
        with zf:
            # 1. 验证 manifest
            if not _validate_manifest(zf):
                result.failed.append("不是有效的 AICraft 备份文件（缺少 manifest.json）")
                return result

            # 2. 确保目标目录存在
            target_dir.mkdir(parents=True, exist_ok=True)
            target_resolved = target_dir.resolve()

            # 3. 逐文件处理
            for name in zf.namelist():
                # 跳过 manifest 和目录条目
                if name == "manifest.json" or name.endswith("/"):
                    continue

                # 去掉 "data/" 前缀得到相对路径
                if not name.startswith("data/"):
                    continue
                rel_path = name[len("data/"):]

                # 计算目标绝对路径并防护路径遍历
                target = (target_dir / rel_path).resolve()
                try:
                    target.relative_to(target_resolved)
                except ValueError:
                    result.failed.append(f"{rel_path}: 非法的文件路径（路径遍历）")
                    continue

                # 覆盖已存在文件，新增不存在文件
                existed = target.exists()

                # 确保父目录存在
                target.parent.mkdir(parents=True, exist_ok=True)

                # 解压文件
                try:
                    with zf.open(name) as src_f:
                        target.write_bytes(src_f.read())
                    if existed:
                        result.overwritten += 1
                    else:
                        result.extracted += 1
                except Exception as e:
                    result.failed.append(f"{rel_path}: {e}")

    except Exception as e:
        result.failed.append(f"导入失败: {e}")

    return result


# ═══════════════════════════════════════════════════════════
# 从旧版目录迁移用户数据
# ═══════════════════════════════════════════════════════════


def _clear_factory_cache() -> None:
    """重置出厂角色/Skill 名称缓存

    迁移完成后用户目录中可能出现新的角色和 Skill，
    需要清除缓存以便下次检测时重新扫描。
    """
    global _FACTORY_ROLE_NAMES, _FACTORY_SKILL_NAMES
    _FACTORY_ROLE_NAMES = None
    _FACTORY_SKILL_NAMES = None


def migrate_from_old_version(
    old_root: Path,
    target_dir: Path = USER_DIR,
) -> MigrationResult:
    """从旧版 AICraft 目录拷贝用户数据到当前 USER_DIR

    Args:
        old_root: 旧版 AICraft 根目录（包含 .version 文件）
        target_dir: 目标用户数据目录，默认 USER_DIR

    Returns:
        MigrationResult(migrated, skipped, errors, old_version)

    迁移策略：
        - 拷贝（非移动），旧目录原封不动
        - 目标已有文件跳过（不覆盖），保护新版默认配置
        - 出厂角色和 Skill 自动排除
        - 读取旧版 .version 记录来源版本号
    """
    result = MigrationResult()

    # 1. 校验旧目录
    if not old_root.exists():
        result.errors.append(f"目录不存在: {old_root}")
        return result
    if not old_root.is_dir():
        result.errors.append(f"路径不是目录: {old_root}")
        return result

    old_version_file = old_root / ".version"
    if not old_version_file.exists():
        result.errors.append(
            f"所选目录不是有效的 AICraft 用户数据目录（未找到 .version 文件）"
        )
        return result

    # 2. 读取旧版本号
    try:
        vdata = load_json(old_version_file)
        result.old_version = vdata.get("version", "unknown")
    except Exception:
        result.old_version = "unknown"

    # 3. 确保目标目录存在
    target_dir.mkdir(parents=True, exist_ok=True)

    # 4. 遍历迁移清单
    for rel_path, is_dir, exclude_names in _MIGRATION_ITEMS:
        src = old_root / rel_path
        if not src.exists():
            continue

        try:
            if not is_dir:
                # ── 单文件 ──
                dst = target_dir / rel_path
                if dst.exists():
                    result.skipped.append(rel_path)
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    result.migrated.append(rel_path)
            else:
                # ── 目录：递归拷贝文件 ──
                for f in src.rglob("*"):
                    if not f.is_file():
                        continue
                    rel = f.relative_to(src)
                    # 检查排除列表
                    if exclude_names:
                        top_name = rel.parts[0] if rel.parts else ""
                        if top_name in exclude_names:
                            continue
                    dst_file = target_dir / rel_path / rel
                    rel_str = f"{rel_path}/{rel.as_posix()}"
                    if dst_file.exists():
                        result.skipped.append(rel_str)
                    else:
                        dst_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, dst_file)
                        result.migrated.append(rel_str)
        except OSError as e:
            result.errors.append(f"{rel_path}: {e}")

    # 5. 清除出厂缓存（用户目录中可能有了新的角色/Skill）
    _clear_factory_cache()

    return result


# ═══════════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════════


def _validate_manifest(zf: zipfile.ZipFile) -> bool:
    """检查 manifest.json 是否存在且 format 为 aicraft-backup"""
    try:
        info = zf.getinfo("manifest.json")
        with zf.open(info) as f:
            data = json.loads(f.read().decode("utf-8"))
        return data.get("format") == "aicraft-backup"
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError):
        return False


def _json_dumps(data: dict) -> str:
    """JSON 序列化，不带 ensure_ascii（中文可读）"""
    return json.dumps(data, ensure_ascii=False, indent=2)
