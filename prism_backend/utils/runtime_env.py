"""
运行时环境自动检测模块
支持 Mac / Windows / Linux / Docker 全平台自动适配
"""
import os
import platform
from pathlib import Path
from typing import Dict, Optional


def load_runtime_env() -> Dict[str, any]:
    """
    自动检测运行时环境
    
    Returns:
        Dict: 包含平台信息的字典
            - platform: 平台名称 (darwin/linux/win32)
            - is_linux: 是否为 Linux
            - is_mac: 是否为 Mac
            - is_windows: 是否为 Windows
            - is_docker: 是否运行在 Docker 中
            - headless: 是否无头模式
            - home_dir: 用户主目录
    """
    system = platform.system().lower()
    
    # 判断是否在 Docker 中运行
    is_docker = (
        Path("/.dockerenv").exists() or
        Path("/run/.containerenv").exists() or
        os.getenv("DOCKER_CONTAINER") == "true"
    )
    
    # 判断是否为无头模式
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    
    return {
        "platform": system,
        "is_linux": system == "linux",
        "is_mac": system == "darwin",
        "is_windows": system == "windows",
        "is_docker": is_docker,
        "headless": headless,
        "home_dir": str(Path.home()),
    }


def get_env_info() -> str:
    """
    获取环境信息的友好字符串
    
    Returns:
        str: 环境描述
    """
    env = load_runtime_env()
    
    platform_name = {
        "darwin": "macOS",
        "linux": "Linux",
        "windows": "Windows"
    }.get(env["platform"], env["platform"])
    
    env_type = "Docker 容器" if env["is_docker"] else "物理机/虚拟机"
    mode = "无头模式" if env["headless"] else "有头模式"
    
    return f"{platform_name} ({env_type}) - {mode}"


if __name__ == "__main__":
    env = load_runtime_env()
    print("=" * 50)
    print("运行时环境检测")
    print("=" * 50)
    print(f"平台: {env['platform']}")
    print(f"Linux: {env['is_linux']}")
    print(f"Mac: {env['is_mac']}")
    print(f"Windows: {env['is_windows']}")
    print(f"Docker: {env['is_docker']}")
    print(f"无头模式: {env['headless']}")
    print(f"主目录: {env['home_dir']}")
    print("=" * 50)
    print(f"环境描述: {get_env_info()}")
    print("=" * 50)
