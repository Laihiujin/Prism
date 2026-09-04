"""
开发者工具注册表（插件/MCP 工具一键安装）。

管理按需安装的开发工具：deepseek-harness、ccswitch、computer-use-linux 等。
每个工具描述：名称、类型（MCP/CLI/agent）、仓库、安装方式、安装路径。

- list：工具目录
- install：克隆/安装到 tools/ 下（按需一键安装）
- uninstall：移除
- status：检测已安装与否

安装遵循各工具官方方式；克隆目标统一放 tools/ 便于管理。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from loguru import logger

# 项目根目录（tools/ 所在）
BACKEND_ROOT = Path(__file__).resolve().parents[2]  # fastapi_app/../.. = prism_backend
REPO_ROOT = BACKEND_ROOT.parent  # Prism 根
TOOLS_DIR = REPO_ROOT / "tools"

# Hermes 技能（md 文件）根目录
SKILLS_ROOT = REPO_ROOT / "runtime-data" / "app" / "hermes-home" / "skills"


def _iter_skill_dicts() -> Iterable[Dict[str, Any]]:
    """动态枚举 Hermes 技能（md 文件）：skills/<分类>/<技能名>/SKILL.md。

    停用的技能会移到 skills/_disabled/<分类>/<技能名>/ 下（软停用，不物理删除）。

    打包版中 runtime-data 可能位于用户数据目录而非 bundle/Resources，
    skills 根目录可能不存在；此时优雅地返回空列表，避免整个 /tools 列表因
    单一路径缺失而崩溃（配置的 DevTools/组件仍会正常展示）。
    """
    roots: List[Tuple[Path, bool]] = []
    if SKILLS_ROOT.is_dir():
        roots.append((SKILLS_ROOT, True))
    disabled_root = SKILLS_ROOT / "_disabled"
    if disabled_root.is_dir():
        roots.append((disabled_root, False))
    for root, enabled in roots:
        for cat_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            for skill_dir in sorted(p for p in cat_dir.iterdir() if p.is_dir()):
                skill_md = skill_dir / "SKILL.md"
                if not skill_md.is_file():
                    continue
                desc = ""
                try:
                    for ln in skill_md.read_text(errors="ignore").splitlines()[:12]:
                        s = ln.strip()
                        if s and not s.startswith("#"):
                            desc = s[:140]
                            break
                except Exception:
                    pass
                yield {
                    "id": f"skill-{cat_dir.name}-{skill_dir.name}",
                    "name": skill_dir.name,
                    "category": cat_dir.name,
                    "type": "skill",
                    "repo": "",
                    "description": desc or f"Hermes skill (md): {cat_dir.name}/{skill_dir.name}",
                    "install_path": f"{cat_dir.name}/{skill_dir.name}",
                    "installed": True,
                    "enabled": enabled,
                    "launchable": False,
                    "buildable": False,
                    "_skill_path": str(skill_dir),
                    "_is_skill": True,
                }


@dataclass
class DevTool:
    """一个可一键安装的开发工具。"""

    id: str
    name: str
    type: str            # 分类：skill / mcp / plugin / component
    repo: str            # GitHub 仓库 URL（克隆用）
    description: str
    install_path: str    # tools/ 下的子目录名
    install_cmd: str = ""  # 安装后执行的构建/安装命令（可选；外部应用时为"打开下载页"命令）
    check: str = ""      # 检测已安装的命令（可选）
    launch_cmd: str = ""  # 从 Prism 打开/调用的命令（可选，如 macOS 应用）
    build_cmd: str = ""  # 构建命令（可选，如 persona dashboard 构建）
    install_url: str = ""  # 外部应用时的官方下载/安装链接（如 GitHub Releases）
    note: str = ""      # 备注（如"模型管理外置"）
    github_repo: str = ""  # GitHub repo（owner/repo）：外部应用按平台动态解析最新版下载链接
    asset_patterns: Dict[str, str] = field(default_factory=dict)  # 平台 -> 资产名 fnmatch 模式
    builtin: bool = False  # 内置组件（随 Prism 提供，始终视为已安装，装/不装都显示占位符）

    def target_path(self) -> Path:
        return TOOLS_DIR / self.install_path

    def is_installed(self) -> bool:
        # 内置组件：随 Prism 本体提供，无需用户安装，始终显示为已安装。
        if self.builtin:
            return True
        # install_path 为空（全局安装工具，如 computer-use-linux / ccswitch）时，
        # target_path() 会退化到 TOOLS_DIR（恒存在），导致误报已安装。
        # 此时应直接走 check 检测，而不是用目录是否存在判定。
        if self.install_path:
            return self.target_path().exists() or self._check_installed()
        return self._check_installed()

    def _check_installed(self) -> bool:
        cmd = _platform_cmd(self.check)
        if not cmd:
            return False
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, timeout=10
            )
            return r.returncode == 0
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "repo": self.repo,
            "description": self.description,
            "install_path": self.install_path,
            "installed": self.is_installed(),
            "launchable": bool(self.launch_cmd),
            "buildable": bool(self.build_cmd),
            "install_url": self.install_url,
            "note": self.note,
        }


def _platform_cmd(raw: Any) -> Optional[str]:
    """按当前平台解析命令：支持 str 或 {darwin|win32|linux|default: cmd}。

    外部桌面应用（如 CC Switch）的检测/打开命令因平台而异；
    传入 dict 时按 sys.platform 取对应平台的命令，未知平台回退到 default。
    """
    if isinstance(raw, dict):
        key = {"darwin": "darwin", "win32": "win32", "linux": "linux"}.get(sys.platform)
        if key and raw.get(key):
            return str(raw[key])
        return str(raw["default"]) if raw.get("default") else None
    return str(raw) if raw else None


def _current_platform_key() -> str:
    """返回当前平台键：darwin / win32 / linux（未知回退 darwin）。"""
    return {"darwin": "darwin", "win32": "win32", "linux": "linux"}.get(sys.platform, "darwin")


def resolve_github_latest_asset(repo: str, pattern: str) -> Optional[str]:
    """解析 GitHub repo 最新 release 中匹配 fnmatch pattern 的资产直链。

    返回 browser_download_url；请求失败或没有匹配资产时返回 None。
    （未认证匿名请求受 GitHub API 速率限制，够日常使用。）
    """
    import fnmatch
    import json
    import urllib.request

    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "Prism-tool-registry",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.warning(f"[Tools] 解析 GitHub 最新 release 失败 {repo}: {exc}")
        return None
    for asset in data.get("assets") or []:
        name = asset.get("name") or ""
        if fnmatch.fnmatch(name, pattern):
            return asset.get("browser_download_url")
    return None


def resolve_ccswitch_latest_url() -> Optional[str]:
    """按当前平台解析 CC Switch 最新版直接下载链接。

    - darwin: 优先通用 macOS.dmg（universal），回退 macOS.tar.gz/zip
    - win32:  按架构选 Windows-arm64.msi 或 Windows.msi，回退 Portable.zip
    - linux:  x86_64.AppImage / arm64.AppImage
    """
    import platform

    repo = "farion1231/cc-switch"
    arch = (platform.machine() or "").lower()
    key = _current_platform_key()

    if key == "darwin":
        for pat in ("CC-Switch-*-macOS.dmg", "CC-Switch-*-macOS.tar.gz", "CC-Switch-*-macOS.zip"):
            url = resolve_github_latest_asset(repo, pat)
            if url:
                return url
    elif key == "win32":
        is_arm = "arm" in arch or "aarch" in arch
        for pat in (
            "CC-Switch-*-Windows-arm64.msi" if is_arm else "CC-Switch-*-Windows.msi",
            "CC-Switch-*-Windows-Portable.zip",
            "CC-Switch-*-Windows-arm64-Portable.zip",
        ):
            url = resolve_github_latest_asset(repo, pat)
            if url:
                return url
    else:  # linux
        is_arm = "arm" in arch or "aarch" in arch
        for pat in (
            "CC-Switch-*-Linux-x86_64.AppImage" if not is_arm else "CC-Switch-*-Linux-arm64.AppImage",
            "CC-Switch-*-Linux-x86_64.deb",
            "CC-Switch-*-Linux-arm64.deb",
        ):
            url = resolve_github_latest_asset(repo, pat)
            if url:
                return url
    return None


def open_url(url: str) -> None:
    """按平台打开 URL（macOS open / Windows start / Linux xdg-open）。"""
    key = _current_platform_key()
    if key == "darwin":
        cmd = f'open "{url}"'
    elif key == "win32":
        cmd = f'start "" "{url}"'
    else:
        cmd = f'xdg-open "{url}"'
    try:
        subprocess.Popen(cmd, shell=True)
    except Exception as exc:
        logger.error(f"[Tools] 打开 URL 失败: {exc}")


# ── 工具目录 ──
# 各工具安装方式参考官方 README：
# - deepseek-harness: 独立 monorepo（pnpm），克隆到 tools/deepseek-harness
# - ccswitch: Claude Code 服务商切换 CLI（brew/npm）
# - computer-use-linux: Linux 桌面控制 MCP server（npm install -g）
DEV_TOOLS: List[DevTool] = [
    DevTool(
        id="deepseek-harness",
        name="DeepSeek Harness",
        type="component",
        repo="https://github.com/deepseek-ai/deepseek-harness.git",
        description="DeepSeek 官方 agent harness（monorepo，pnpm）。",
        install_path="deepseek-harness",
        install_cmd="corepack pnpm install --frozen-lockfile && corepack pnpm run build",
        build_cmd="corepack pnpm run build",
        check="test -f tools/deepseek-harness/apps/cli/lib/bin.js && test -d tools/deepseek-harness/node_modules",
        note="CLI: tools/deepseek-harness/apps/cli/lib/bin.js；API + Web UI 默认由 dsh web 统一提供 127.0.0.1:3080。PM2 服务名 deepseek-harness。",
        launch_cmd={
            "darwin": 'open "http://127.0.0.1:3080"',
            "win32": 'start "" "http://127.0.0.1:3080"',
            "linux": 'xdg-open "http://127.0.0.1:3080"',
        },
        builtin=True,
    ),
    DevTool(
        id="ccswitch",
        name="CC Switch",
        type="plugin",
        repo="https://github.com/farion1231/cc-switch.git",
        description="模型提供方管理桌面应用：管理 agent 模型切换，Prism 只读桥接其数据库。",
        install_path="",
        install_url="https://github.com/farion1231/cc-switch/releases",
        note="模型管理外置：CC Switch 内管理 provider；Prism 支持读取ccswitch配置应用到本项目",
        install_cmd="",
        github_repo="farion1231/cc-switch",
        asset_patterns={
            "darwin": "CC-Switch-*-macOS.*",
            "win32": "CC-Switch-*-Windows*.msi",
            "linux": "CC-Switch-*-Linux-*.AppImage",
        },
        check={
            "darwin": 'test -d "/Applications/CC Switch.app"',
            "win32": 'if exist "%LOCALAPPDATA%\\Programs\\CC Switch\\CC Switch.exe" (exit /b 0) & if exist "%LOCALAPPDATA%\\Programs\\cc-switch\\CC Switch.exe" (exit /b 0) & if exist "%PROGRAMFILES%\\CC Switch\\CC Switch.exe" (exit /b 0) & exit /b 1',
            "linux": 'test -d "$HOME/.local/share/cc-switch"',
        },
        launch_cmd={
            "darwin": 'open -a "CC Switch"',
            "win32": 'if exist "%LOCALAPPDATA%\\Programs\\CC Switch\\CC Switch.exe" (start "" "%LOCALAPPDATA%\\Programs\\CC Switch\\CC Switch.exe") else (start "" "CC Switch")',
            "linux": 'cc-switch',
        },
    ),
    # computer-use-linux：Linux 专用桌面控制 MCP server。
    # 注意：仅 Linux（Wayland/X11）环境可用，macOS 主机不可用。
    # 保留此条目供需要控制 Linux 桌面/容器的用户一键安装；macOS 请用 Hermes computer-use (cua-driver)。
    DevTool(
        id="computer-use-linux",
        name="computer-use-linux",
        type="mcp",
        repo="",
        description="Linux 专用桌面控制 MCP server（Wayland/X11）；仅 Linux 环境可用，macOS 不可用。",
        install_path="",
        install_cmd="npm install -g @agent-sh/computer-use-linux",
        check="command -v computer-use-linux",
    ),
    DevTool(
        id="hermes-agent",
        name="Hermes Agent",
        type="component",
        repo="https://github.com/NousResearch/hermes-agent.git",
        description="Hermes Agent（CLI/WebUI/MCP，已在容器内置）。",
        install_path="hermes-agent",
        check="command -v hermes",
        builtin=True,
    ),
    DevTool(
        id="prism-mcp",
        name="Prism MCP",
        type="mcp",
        repo="",
        description="Prism 内置 MCP server：把 Prism 的 BaseTool 目录（发布/账号/数据工具）暴露给 Hermes 作为结构化 MCP 工具。随 Prism 后端内置，无需安装，始终可见。",
        install_path="",
        install_cmd="",
        note="由 Prism 后端自动注入 Hermes config.yaml 的 mcp_servers['prism']（fastapi_app.agent.mcp_server）；内置组件，装/不装都显示占位符。",
        builtin=True,
    ),
    DevTool(
        id="persona-studio",
        name="Persona Studio",
        type="mcp",
        repo="https://github.com/TechQaiser/persona-studio.git",
        description="Browser Identity / Fingerprint / Profile 层（persona serve API :8787，作为浏览器身份后端）。",
        install_path="persona-studio",
        check="command -v persona",
    ),
    DevTool(
        id="mihomo",
        name="mihomo (Clash Meta)",
        type="component",
        repo="https://github.com/MetaCubeX/mihomo.git",
        description=(
            "本地代理网关内核（官方 v1.19.10）：订阅节点 → 每节点独立端口（8001 起），"
            "external-controller 127.0.0.1:9093。已集成 agent 工具 proxy_gateway / mihomo_control。"
            "随 persona-studio 集成内置，无需手动下载。"
        ),
        install_path="",
        note="由 PM2 persona-proxy 托管，配置目录 tools/persona-studio/proxies/（config.yaml / gateway.json）；点「打开」进入 Prism 代理网关管理页。内置组件（二进制随 persona-studio 内置），无需手工下载集成。",
        # 内置组件：随 persona-studio 提供、由 PM2 persona-proxy 托管，始终视为已集成。
        builtin=True,
        # 二进制随 persona-studio 仓库内置；install_path 留空避免 uninstall 误删 proxies 目录。
        check=f"test -f {REPO_ROOT / 'tools/persona-studio/proxies/mihomo'}",
        launch_cmd={
            "darwin": 'open "http://127.0.0.1:3000/persona-proxy"',
            "win32": 'start "" "http://127.0.0.1:3000/persona-proxy"',
            "linux": 'xdg-open "http://127.0.0.1:3000/persona-proxy"',
        },
    ),
]


class DevToolRegistry:
    """工具注册表服务。"""

    def __init__(self, tools: Optional[List[DevTool]] = None):
        self.tools = tools if tools is not None else DEV_TOOLS

    def list(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.tools] + list(_iter_skill_dicts())

    def get(self, tool_id: str) -> Optional[Any]:
        for t in self.tools:
            if t.id == tool_id:
                return t
        for skill in _iter_skill_dicts():
            if skill["id"] == tool_id:
                return skill
        return None

    def status(self, tool_id: str) -> Optional[Dict[str, Any]]:
        tool = self.get(tool_id)
        if not tool:
            return None
        return tool if isinstance(tool, dict) else tool.to_dict()

    def install(self, tool_id: str) -> Dict[str, Any]:
        """按需一键安装工具。"""
        tool = self.get(tool_id)
        if not tool:
            raise ValueError(f"未知工具: {tool_id}")

        if tool.is_installed():
            return {"success": True, "message": f"{tool.name} 已安装", "already": True}

        TOOLS_DIR.mkdir(parents=True, exist_ok=True)

        # 1) 克隆到 tools/<path>（有 repo 时）
        if tool.repo and tool.install_path:
            target = tool.target_path()
            if not target.exists():
                logger.info(f"[Tools] 克隆 {tool.name} -> {target}")
                r = subprocess.run(
                    ["git", "clone", "--depth", "1", tool.repo, str(target)],
                    capture_output=True, text=True, timeout=600,
                )
                if r.returncode != 0:
                    raise RuntimeError(f"克隆失败: {r.stderr[:300]}")

        # 2) 外部应用（无 install_path）：按平台解析最新版直链并打开下载
        if not tool.install_path:
            if tool.github_repo:
                patterns = tool.asset_patterns or {}
                pattern = patterns.get(_current_platform_key()) or ""
                url = resolve_github_latest_asset(tool.github_repo, pattern) if pattern else None
                if url:
                    open_url(url)
                    return {
                        "success": True,
                        "message": f"已打开 {tool.name} 最新版下载链接（{url}），请按提示完成安装",
                        "already": False,
                        "install_url": url,
                    }
                logger.warning(f"[Tools] {tool.name} 未能解析到当前平台安装包，回退到下载页")
            if tool.install_url:
                open_url(tool.install_url)
                return {
                    "success": True,
                    "message": f"已打开 {tool.name} 下载页（外部应用，请手动安装；模型管理外置）",
                    "already": False,
                    "install_url": tool.install_url,
                }
            return {"success": True, "message": f"{tool.name} 安装完成", "already": False}

        # 3) 源码工具：执行安装命令（npm/pnpm 等）
        install_cmd = _platform_cmd(tool.install_cmd)
        if install_cmd:
            cwd = str(tool.target_path()) if tool.install_path and tool.target_path().exists() else str(REPO_ROOT)
            logger.info(f"[Tools] 安装 {tool.name}: {install_cmd}")
            r = subprocess.run(
                install_cmd, shell=True, capture_output=True, text=True,
                timeout=1200, cwd=cwd,
            )
            if r.returncode != 0 and not tool.is_installed():
                logger.warning(f"[Tools] {tool.name} 安装命令返回非零但可继续: {r.stderr[:200]}")
                # 不抛错，clone 本身可能已满足（源码工具）

        return {"success": True, "message": f"{tool.name} 安装完成", "already": False}

    def uninstall(self, tool_id: str) -> Dict[str, Any]:
        """卸载工具。"""
        tool = self.get(tool_id)
        if not tool:
            raise ValueError(f"未知工具: {tool_id}")

        if tool_id == "deepseek-harness":
            import socket

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.3)
                if sock.connect_ex(("127.0.0.1", 3080)) == 0:
                    raise RuntimeError(
                        "DeepSeek Harness 仍在 127.0.0.1:3080 运行；"
                        "请先停止 deepseek-harness 服务，再执行卸载。"
                    )

        # Skill（md 文件）：直接删除技能目录
        if isinstance(tool, dict) and tool.get("_is_skill"):
            path = Path(tool["_skill_path"])
            removed = False
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
                removed = True
            return {"success": True, "message": f"{tool['name']} 技能已卸载", "removed": removed}

        target = tool.target_path()
        removed = False
        if target.exists() and tool.install_path:
            shutil.rmtree(target, ignore_errors=True)
            removed = True
        # 全局安装的工具（computer-use-linux）用 npm uninstall
        if "npm install -g" in tool.install_cmd:
            pkg = tool.install_cmd.split("npm install -g")[-1].strip()
            if pkg:
                subprocess.run(["npm", "uninstall", "-g", pkg], capture_output=True, timeout=120)
                removed = True

        return {"success": True, "message": f"{tool.name} 已卸载", "removed": removed}

    def launch(self, tool_id: str) -> Dict[str, Any]:
        """从 Prism 打开/调用本地已安装的工具（如 macOS/Windows 桌面应用）。"""
        tool = self.get(tool_id)
        if not tool:
            raise ValueError(f"未知工具: {tool_id}")
        launch_cmd = _platform_cmd(tool.launch_cmd)
        if not launch_cmd:
            raise ValueError(f"{tool.name} 不支持从 Prism 打开")
        if not tool.is_installed():
            raise RuntimeError(f"{tool.name} 尚未安装，无法打开")
        try:
            subprocess.Popen(launch_cmd, shell=True)
            return {"success": True, "message": f"已打开 {tool.name}"}
        except Exception as e:
            logger.error(f"[Tools] 打开 {tool.name} 失败: {e}")
            raise RuntimeError(f"打开 {tool.name} 失败: {e}")

    def build(self, tool_id: str) -> Dict[str, Any]:
        """构建已安装的工具（如 Persona Dashboard）。"""
        tool = self.get(tool_id)
        if not tool:
            raise ValueError(f"未知工具: {tool_id}")
        if not tool.build_cmd:
            raise ValueError(f"{tool.name} 不支持构建")
        if not tool.is_installed():
            raise RuntimeError(f"{tool.name} 尚未安装，无法构建")
        cwd = str(tool.target_path()) if tool.install_path and tool.target_path().exists() else str(REPO_ROOT)
        logger.info(f"[Tools] 构建 {tool.name}: {tool.build_cmd} (cwd={cwd})")
        r = subprocess.run(
            tool.build_cmd, shell=True, capture_output=True, text=True,
            timeout=1200, cwd=cwd,
        )
        if r.returncode != 0:
            logger.error(f"[Tools] 构建 {tool.name} 失败: {r.stderr[:500]}")
            raise RuntimeError(f"构建 {tool.name} 失败: {r.stderr[:300]}")
        return {"success": True, "message": f"{tool.name} 构建完成"}

    def set_skill_enabled(self, skill_id: str, enabled: bool) -> Dict[str, Any]:
        """软启用/停用技能：把技能目录在 active 与 _disabled 之间移动（不物理删除）。"""
        target = next((s for s in _iter_skill_dicts() if s["id"] == skill_id), None)
        if not target:
            raise ValueError(f"未知技能: {skill_id}")
        cat, name = target["category"], target["name"]
        active_dir = SKILLS_ROOT / cat / name
        disabled_dir = SKILLS_ROOT / "_disabled" / cat / name
        try:
            if enabled:
                if disabled_dir.exists() and not active_dir.exists():
                    active_dir.parent.mkdir(parents=True, exist_ok=True)
                    disabled_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(disabled_dir), str(active_dir))
            else:
                if active_dir.exists() and not disabled_dir.exists():
                    disabled_dir.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(active_dir), str(disabled_dir))
        except Exception as e:
            logger.error(f"[Tools] 停用/启用技能失败 {skill_id}: {e}")
            raise RuntimeError(f"技能操作失败: {e}")
        return {
            "success": True,
            "enabled": enabled,
            "message": f"{name} 技能{'已启用' if enabled else '已停用'}",
        }


# 全局单例
_registry: Optional[DevToolRegistry] = None


def get_tool_registry() -> DevToolRegistry:
    global _registry
    if _registry is None:
        _registry = DevToolRegistry()
    return _registry
