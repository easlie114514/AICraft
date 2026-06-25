"""MCP 工具权限守卫 — 路径策略 + 用户审批

权限层级:
  1. denied_paths  → 直接拒绝，不可豁免
  2. trusted_paths → 自动放行，无需确认
  3. 其他路径      → 需用户确认（通过 WebSocket 弹窗）

路径匹配:
  - 精确前缀匹配: C:/Users/Easlie 匹配 C:/Users/Easlie/Desktop/...
  - Glob 模式: **/node_modules/**, **/.git/**
  - 大小写不敏感 (Windows), 大小写敏感 (Linux)
"""

from __future__ import annotations

import asyncio
import fnmatch
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Awaitable

from src.utils.config import load_json, save_json, CONFIG_DIR, APP_DIR


# ═══════════════════════════════════════════════════════════
# 操作风险等级
# ═══════════════════════════════════════════════════════════

READ_OPS: set[str] = {
    "read_file",
    "list_directory",
    "search_files",
    "get_file_info",
}

WRITE_OPS: set[str] = {
    "write_file",
    "edit_file",
    "create_directory",
    "move_file",
}

DELETE_OPS: set[str] = {
    "delete_file",
}

# 工具名 → 需要提取的路径参数名
TOOL_PATH_ARGS: dict[str, list[str]] = {
    "read_file":        ["path"],
    "write_file":       ["path"],
    "edit_file":        ["path"],
    "delete_file":      ["path"],
    "create_directory":  ["path"],
    "list_directory":   ["path"],
    "search_files":     ["path"],
    "move_file":        ["source", "destination"],
    "get_file_info":    ["path"],
}

# 所有需要权限检查的工具名
GUARDED_TOOLS: set[str] = set(TOOL_PATH_ARGS.keys())


# ═══════════════════════════════════════════════════════════
# 配置持久化
# ═══════════════════════════════════════════════════════════

PERMISSION_CONFIG_PATH = CONFIG_DIR / "permissions.json"


def _get_default_config() -> dict:
    """生成默认权限配置"""
    if os.name == "nt":
        # Windows 默认拒绝路径
        denied = [
            "C:/Windows/**",
            "C:/Program Files/**",
            "C:/Program Files (x86)/**",
            "**/System32/**",
            "**/WinSxS/**",
            "**/.git/config",
            "**/.ssh/**",
        ]
    else:
        denied = [
            "/etc/**",
            "/sys/**",
            "/proc/**",
            "/boot/**",
            "**/.git/config",
            "**/.ssh/**",
        ]

    return {
        "trusted_paths": ["{PROJECT_ROOT}"],
        "denied_paths": denied,
        "prompt_timeout_seconds": 60,
    }


def load_permission_config() -> dict:
    """加载权限配置，不存在则创建默认配置"""
    cfg = load_json(PERMISSION_CONFIG_PATH)
    if not cfg:
        cfg = _get_default_config()
        save_json(PERMISSION_CONFIG_PATH, cfg)
    # 补齐缺失的 key
    defaults = _get_default_config()
    for k, v in defaults.items():
        if k not in cfg:
            cfg[k] = v
    return cfg


def save_permission_config(cfg: dict) -> None:
    save_json(PERMISSION_CONFIG_PATH, cfg)


# ═══════════════════════════════════════════════════════════
# Data types
# ═══════════════════════════════════════════════════════════

@dataclass
class PermissionResult:
    allowed: bool
    reason: str = ""
    path: str = ""
    operation: str = ""


@dataclass
class PermissionRequest:
    """一次权限请求"""
    id: str
    tool_name: str
    paths: list[str]
    operation: str          # "read" | "write" | "delete"
    risk: str               # "low" | "medium" | "high"
    preview: str = ""       # 写入/删除操作的内容预览
    future: asyncio.Future = field(default_factory=asyncio.Future)


# ═══════════════════════════════════════════════════════════
# PermissionGuard
# ═══════════════════════════════════════════════════════════

class PermissionGuard:
    """MCP 工具调用权限守卫"""

    def __init__(
        self,
        ws_send_fn: Callable[[dict], Awaitable[None]] | None = None,
    ):
        self._ws_send_fn = ws_send_fn
        self._pending: dict[str, PermissionRequest] = {}
        self._config = load_permission_config()

    # ── API 给外部设置 WebSocket 回调 ──

    def set_ws_send_fn(self, fn: Callable[[dict], Awaitable[None]]):
        self._ws_send_fn = fn

    def reload_config(self):
        self._config = load_permission_config()

    @property
    def trusted_paths(self) -> list[str]:
        return self._config.get("trusted_paths", [])

    @property
    def denied_paths(self) -> list[str]:
        return self._config.get("denied_paths", [])

    # ── 核心检查 ──

    def _extract_paths(self, tool_name: str, args: dict) -> list[str]:
        """从工具参数中提取所有文件路径"""
        paths = []
        arg_names = TOOL_PATH_ARGS.get(tool_name, [])
        for name in arg_names:
            val = args.get(name, "")
            if val and isinstance(val, str):
                paths.append(val)
        return paths

    def _expand_pattern(self, pattern: str) -> str:
        """展开模式中的占位符，如 {PROJECT_ROOT} → 实际项目路径"""
        return pattern.replace("{PROJECT_ROOT}", str(APP_DIR).replace("\\", "/"))

    def _match_path(self, real_path: str, policy_pattern: str) -> bool:
        """检查路径是否匹配某个策略模式"""
        # 规范化路径
        rp = str(Path(real_path)).replace("\\", "/")
        pp = self._expand_pattern(policy_pattern).replace("\\", "/")

        # 前缀匹配（精确目录路径匹配子路径）
        pp_clean = pp.rstrip("/")
        if rp == pp_clean or rp.startswith(pp_clean + "/"):
            return True

        # Glob 匹配（** 跨目录通配符）
        if "**" in pp or "*" in pp:
            # 用 fnmatch 逐段匹配
            rp_parts = rp.split("/")
            pp_parts = pp.split("/")

            # 跨平台大小写处理
            if os.name == "nt":
                rp_parts = [p.lower() for p in rp_parts]
                pp_parts = [p.lower() for p in pp_parts]

            return _glob_match_parts(rp_parts, pp_parts)

        # 大小写不敏感（Windows）
        if os.name == "nt":
            return rp.lower() == pp_clean.lower()

        return False

    def _check_rules(self, paths: list[str]) -> tuple[bool, str, str]:
        """检查路径列表，返回 (allowed, reason, matched_path)

        - 任何 path 匹配 denied → 拒绝
        - 所有 paths 匹配 trusted → 放行
        - 否则 → 需确认
        """
        if not paths:
            return True, "", ""

        # 1) 检查 deny 规则（优先级最高）
        for path in paths:
            for policy in self.denied_paths:
                if self._match_path(path, policy):
                    return False, f"路径 '{path}' 被安全策略禁止访问（匹配: {policy}）", path

        # 2) 检查 trust 规则
        all_trusted = True
        for path in paths:
            path_trusted = False
            for policy in self.trusted_paths:
                if self._match_path(path, policy):
                    path_trusted = True
                    break
            if not path_trusted:
                all_trusted = False
                break

        if all_trusted:
            return True, "", ""

        # 3) 需要确认
        return None, "", paths[0]  # type: ignore[return-value]

    # ── 工具调用入口 ──

    def needs_guard(self, tool_name: str) -> bool:
        """检查此工具是否需要权限守卫"""
        return tool_name in GUARDED_TOOLS

    async def check(
        self,
        tool_name: str,
        tool_args: dict,
        preview_content: str = "",
    ) -> PermissionResult:
        """检查工具调用是否需要权限审批

        返回 PermissionResult(allowed=True) → 可直接执行
        返回 PermissionResult(allowed=False) → 拒绝执行

        如果需要用户确认，会通过 WebSocket 发送权限请求并等待响应。

        每次调用时自动重载配置，确保热更新生效。
        """
        # ── 热更新：每次检查前重载配置 ──
        self._config = load_permission_config()

        # 提取路径
        paths = self._extract_paths(tool_name, tool_args)
        if not paths:
            # 没有可识别的路径参数 → 放行（如 read_file path 写错时由工具报错）
            return PermissionResult(allowed=True, reason="无文件路径参数")

        # 检查规则
        allowed, reason, matched_path = self._check_rules(paths)

        if allowed is True:
            return PermissionResult(allowed=True, reason=reason)
        elif allowed is False:
            return PermissionResult(allowed=False, reason=reason, path=matched_path)

        # ── 需要用户确认 ──
        if self._ws_send_fn is None:
            # 无 WebSocket 连接 → 默认拒绝
            return PermissionResult(
                allowed=False,
                reason="需要用户确认但当前无交互通道，默认拒绝",
                path=matched_path,
            )

        # 确定操作类型和风险等级
        if tool_name in DELETE_OPS:
            operation = "delete"
            risk = "high"
        elif tool_name in WRITE_OPS:
            operation = "write"
            risk = "medium"
        else:
            operation = "read"
            risk = "low"

        # 创建权限请求
        req_id = f"perm_{uuid.uuid4().hex[:8]}"
        req = PermissionRequest(
            id=req_id,
            tool_name=tool_name,
            paths=paths,
            operation=operation,
            risk=risk,
            preview=preview_content[:500] if preview_content else "",
        )

        # 发送到前端
        await self._ws_send_fn({
            "type": "permission_request",
            "id": req_id,
            "tool": tool_name,
            "paths": paths,
            "operation": operation,
            "risk": risk,
            "preview": req.preview,
        })

        self._pending[req_id] = req

        # 等待用户响应（带超时）
        timeout = self._config.get("prompt_timeout_seconds", 60)
        try:
            action = await asyncio.wait_for(req.future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            return PermissionResult(
                allowed=False,
                reason=f"权限请求超时（{timeout}秒无响应），自动拒绝",
                path=matched_path,
                operation=operation,
            )

        self._pending.pop(req_id, None)

        if action == "allow_once":
            return PermissionResult(
                allowed=True,
                reason="用户允许（单次）",
                path=matched_path,
                operation=operation,
            )
        elif action == "allow_always":
            # 把路径加入信任列表
            for p in paths:
                parent = str(Path(p).parent)
                if parent not in self.trusted_paths:
                    self._config.setdefault("trusted_paths", []).append(parent)
            save_permission_config(self._config)
            return PermissionResult(
                allowed=True,
                reason="用户允许（始终信任此目录）",
                path=matched_path,
                operation=operation,
            )
        elif action == "deny_always":
            # 把路径加入拒绝列表
            for p in paths:
                parent = str(Path(p).parent)
                if parent not in self.denied_paths:
                    self._config.setdefault("denied_paths", []).append(parent)
            save_permission_config(self._config)
            return PermissionResult(
                allowed=False,
                reason="用户拒绝（始终拒绝此目录）",
                path=matched_path,
                operation=operation,
            )
        else:  # "deny"
            return PermissionResult(
                allowed=False,
                reason="用户拒绝",
                path=matched_path,
                operation=operation,
            )

    # ── 处理用户响应 ──

    def handle_response(self, request_id: str, action: str) -> bool:
        """处理来自前端的用户权限响应

        Returns:
            True 如果成功匹配到等待中的请求
        """
        req = self._pending.get(request_id)
        if req is None:
            return False
        if not req.future.done():
            req.future.set_result(action)
        return True

    # ── 取消所有待处理的请求 ──

    def cancel_all(self):
        """取消所有未完成的权限请求（WebSocket 断开时调用）"""
        for req in self._pending.values():
            if not req.future.done():
                req.future.set_result("deny")
        self._pending.clear()


# ═══════════════════════════════════════════════════════════
# Glob 路径匹配
# ═══════════════════════════════════════════════════════════

def _glob_match_parts(target_parts: list[str], pattern_parts: list[str]) -> bool:
    """用分段的 parts 列表做 glob 匹配（支持 ** 跨段）"""
    ti = 0
    pi = 0
    tlen = len(target_parts)
    plen = len(pattern_parts)

    # backtracking
    star_idx = -1
    match_idx = 0

    while ti < tlen:
        if pi < plen and pattern_parts[pi] == "**":
            # ** 匹配零个或多个段
            star_idx = pi
            match_idx = ti
            pi += 1
        elif pi < plen and _part_match(target_parts[ti], pattern_parts[pi]):
            ti += 1
            pi += 1
        elif star_idx != -1:
            # 回溯：让 ** 多吃一段
            pi = star_idx + 1
            match_idx += 1
            ti = match_idx
        else:
            return False

    # 剩余 pattern parts 必须全是 **
    while pi < plen and pattern_parts[pi] == "**":
        pi += 1

    return pi == plen


def _part_match(target: str, pattern: str) -> bool:
    """单段匹配（调用 fnmatch）"""
    return fnmatch.fnmatch(target, pattern)
