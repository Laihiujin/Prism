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
    """
    roots = [(SKILLS_ROOT, True)]
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
    install_cmd: str = ""  # 安装后执行的构建/安装命令（可选）
    check: str = ""      # 检测已安装的命令（可选）
    launch_cmd: str = ""  # 从 Prism 打开/调用的命令（可选，如 macOS 应用）
    build_cmd: str = ""  # 构建命令（可选，如 persona dashboard 构建）

    def target_path(self) -> Path:
        return TOOLS_DIR / self.install_path

    def is_installed(self) -> bool:
        return self.target_path().exists() or self._check_installed()

    def _check_installed(self) -> bool:
        if not self.check:
            return False
        try:
            r = subprocess.run(
                self.check, shell=True, capture_output=True, timeout=10
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
        }


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
        install_cmd="pnpm install 2>/dev/null || corepack enable && pnpm install",
        check="test -d tools/deepseek-harness/package.json",
    ),
    DevTool(
        id="ccswitch",
        name="CC Switch",
        type="plugin",
        repo="https://github.com/farion1231/cc-switch.git",
        description="Claude Code 服务商/账号一键切换（macOS 桌面应用，位于 /Applications/CC Switch.app）。",
        install_path="",
        launch_cmd='open -a "CC Switch"',
        check='test -d "/Applications/CC Switch.app"',
    ),
    DevTool(
        id="computer-use-linux",
        name="computer-use-linux",
        type="mcp",
        repo="",
        description="Linux 桌面控制 MCP server（Wayland/X11）。",
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

        # 2) 执行安装命令（npm/pnpm 等）
        if tool.install_cmd:
            cwd = str(tool.target_path()) if tool.install_path and tool.target_path().exists() else str(REPO_ROOT)
            logger.info(f"[Tools] 安装 {tool.name}: {tool.install_cmd}")
            r = subprocess.run(
                tool.install_cmd, shell=True, capture_output=True, text=True,
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
        """从 Prism 打开/调用本地已安装的工具（如 macOS 应用）。"""
        tool = self.get(tool_id)
        if not tool:
            raise ValueError(f"未知工具: {tool_id}")
        if not tool.launch_cmd:
            raise ValueError(f"{tool.name} 不支持从 Prism 打开")
        if not tool.is_installed():
            raise RuntimeError(f"{tool.name} 尚未安装，无法打开")
        try:
            subprocess.Popen(tool.launch_cmd, shell=True)
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
