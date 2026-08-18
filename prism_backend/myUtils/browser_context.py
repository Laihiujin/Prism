from typing import Dict, Any, Optional, List
import os
from pathlib import Path

DEFAULT_CONTEXT_OPTS: Dict[str, Any] = {
    # 禁用位置权限（不在 permissions 列表中 = 拒绝）
    # 移除 geolocation 以禁止浏览器请求位置信息
    # "permissions": ["geolocation"],  # 已禁用
    # "geolocation": {"longitude": 0, "latitude": 0},  # 已禁用
    "locale": "zh-CN",
    "timezone_id": "Asia/Shanghai",
    # 忽略HTTPS错误（某些平台可能需要）
    "ignore_https_errors": True,
}


def build_context_options(**overrides: Any) -> Dict[str, Any]:
    """返回带默认权限/时区的 context 配置，可用 storage_state 等覆盖。"""
    opts = DEFAULT_CONTEXT_OPTS.copy()
    opts.update(overrides)
    return opts



def build_browser_args() -> Dict[str, Any]:
    """
    返回 Playwright browser.launch() 的参数配置
    包括代理绕过设置以解决 ERR_PROXY_CONNECTION_FAILED

    注意：不要添加 --disable-extensions，这会导致浏览器崩溃或扩展无法加载
    """
    args = {
        "headless": False,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            # 禁用地理位置相关功能
            "--disable-features=Geolocation",
            "--disable-geolocation",
        ],
    }

    # 如果环境变量中没有明确设置代理，则禁用代理
    # 这样可以避免 ERR_PROXY_CONNECTION_FAILED 错误
    if not os.getenv("HTTP_PROXY") and not os.getenv("HTTPS_PROXY"):
        args["args"].extend([
            "--no-proxy-server",
            "--proxy-bypass-list=*",
        ])

    # 自动配置 Chrome 路径（支持相对路径）
    # 优先使用配置文件中的 LOCAL_CHROME_PATH
    try:
        from config.conf import LOCAL_CHROME_PATH, APP_ROOT
        if LOCAL_CHROME_PATH:
            chrome_path = Path(str(LOCAL_CHROME_PATH))

            # 如果是相对路径，从项目根目录解析（BASE_DIR.parent）
            if not chrome_path.is_absolute():
                # BASE_DIR 是 syn_backend，需要上一级到项目根目录
                chrome_path = APP_ROOT / chrome_path

            if chrome_path.is_file():
                args["executable_path"] = str(chrome_path.resolve())
                print(f"✅ 已加载Chrome")
            else:
                print(f"⚠️ LOCAL_CHROME_PATH 路径无效: {LOCAL_CHROME_PATH}")
        else:
            print("ℹ️ LOCAL_CHROME_PATH 未配置，将使用 Playwright 默认的 Chromium")
    except Exception as e:
        print(f"⚠️ 加载 LOCAL_CHROME_PATH 配置失败: {e}")

    return args


def build_firefox_args() -> Dict[str, Any]:
    """
    返回 Firefox browser.launch() 的参数配置（视频号专用）
    """
    args = {
        "headless": False,
        "args": [],
    }

    # 自动配置 Firefox 路径（支持相对路径）
    # 优先使用环境变量 LOCAL_FIREFOX_PATH
    try:
        firefox_path_str = os.getenv("LOCAL_FIREFOX_PATH")
        if not firefox_path_str:
            # 如果环境变量没设置，尝试从 config 读取
            try:
                from config.conf import APP_ROOT
                # 默认 Firefox 路径
                firefox_path_str = "browsers/firefox/firefox-1495/firefox/firefox.exe"
            except Exception:
                pass

        if firefox_path_str:
            from config.conf import APP_ROOT
            firefox_path = Path(str(firefox_path_str))

            # 如果是相对路径，从项目根目录解析（BASE_DIR.parent）
            if not firefox_path.is_absolute():
                # BASE_DIR 是 syn_backend，需要上一级到项目根目录
                firefox_path = APP_ROOT / firefox_path

            if firefox_path.is_file():
                args["executable_path"] = str(firefox_path.resolve())
                print(f"✅ 使用 Firefox 浏览器（项目根目录相对路径）")
            else:
                print(f"⚠️ LOCAL_FIREFOX_PATH 路径无效: {firefox_path_str}")
                print(f"   完整路径: {firefox_path}")
        else:
            print("ℹ️ LOCAL_FIREFOX_PATH 未配置，将使用 Playwright 默认的 Firefox")
    except Exception as e:
        print(f"⚠️ 加载 LOCAL_FIREFOX_PATH 配置失败: {e}")

    return args


# ============================================
# 单账号绑定持久化浏览器
# ============================================

class PersistentBrowserManager:
    """
    持久化浏览器管理器
    为每个账号创建独立的浏览器用户数据目录，实现持久化

    特点：
    - 每个账号有独立的 user_data_dir
    - 保留 Cookie、LocalStorage、登录状态等
    - 自动集成设备指纹
    """

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            try:
                from fastapi_app.core.config import settings
                base_dir = Path(settings.BROWSER_PROFILES_DIR)
            except Exception:
                try:
                    from config.conf import BASE_DIR
                    base_dir = Path(BASE_DIR) / "browser_profiles"
                except Exception:
                    base_dir = Path(__file__).resolve().parents[1] / "browser_profiles"

        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_user_data_dir(self, account_id: str, platform: str, user_id: Optional[str] = None) -> Path:
        """
        获取账号的持久化浏览器数据目录

        Args:
            account_id: 账号 ID（兜底使用）
            platform: 平台名称
            user_id: 平台用户ID（优先使用，确保账号唯一性）

        Returns:
            Path: 用户数据目录路径

        Note:
            每个账号只有一个持久化目录，格式：{platform}_{user_id} 或 {platform}_{account_id}
        """
        if not user_id:
            raise ValueError("user_id is required for persistent profile naming")
        identifier = user_id
        user_dir = self.base_dir / f"{platform}_{identifier}"
        user_dir.mkdir(parents=True, exist_ok=True)

        return user_dir

    def build_persistent_context_options(
        self,
        account_id: str,
        platform: str,
        user_id: Optional[str] = None,
        apply_fingerprint: bool = True,
        **overrides: Any
    ) -> Dict[str, Any]:
        """
        构建持久化浏览器上下文配置

        Args:
            account_id: 账号 ID（兜底使用）
            platform: 平台名称
            user_id: 平台用户ID（优先使用）
            apply_fingerprint: 是否应用设备指纹
            **overrides: 额外的配置覆盖

        Returns:
            Dict: Playwright 上下文配置
        """
        # 基础配置
        opts = DEFAULT_CONTEXT_OPTS.copy()

        # 应用设备指纹
        if apply_fingerprint:
            try:
                from myUtils.device_fingerprint import device_fingerprint_manager

                fingerprint = device_fingerprint_manager.get_or_create_fingerprint(
                    account_id=account_id,
                    platform=platform,
                    user_id=user_id
                )

                opts = device_fingerprint_manager.apply_to_context(fingerprint, opts)
            except Exception as e:
                print(f"⚠️ 应用设备指纹失败: {e}")

        # 应用额外配置
        opts.update(overrides)

        return opts

    async def get_init_scripts(
        self,
        account_id: str,
        platform: str,
        user_id: Optional[str] = None
    ) -> list[str]:
        """
        获取需要注入的初始化脚本

        Args:
            account_id: 账号 ID（兜底使用）
            platform: 平台名称
            user_id: 平台用户ID（优先使用）

        Returns:
            List[str]: 初始化脚本列表
        """
        scripts = []

        # 添加设备指纹脚本
        try:
            from myUtils.device_fingerprint import device_fingerprint_manager

            fingerprint = device_fingerprint_manager.get_or_create_fingerprint(
                account_id=account_id,
                platform=platform,
                user_id=user_id
            )

            script = device_fingerprint_manager.get_init_script(fingerprint)
            scripts.append(script)
        except Exception as e:
            print(f"⚠️ 获取设备指纹脚本失败: {e}")

        return scripts

    def cleanup_user_data(self, account_id: str, platform: str, user_id: Optional[str] = None) -> bool:
        """
        清理账号的浏览器数据（谨慎使用）

        Args:
            account_id: 账号 ID（兜底使用）
            platform: 平台名称
            user_id: 平台用户ID（优先使用）

        Returns:
            bool: 是否成功
        """
        import shutil

        if not user_id:
            print("WARNING: missing user_id; skip persistent profile cleanup")
            return False
        identifier = user_id
        user_dir = self.base_dir / f"{platform}_{identifier}"

        try:
            if user_dir.exists():
                shutil.rmtree(user_dir)
                print(f"✅ 已删除持久化配置: {user_dir}")
                return True
            else:
                print(f"⚠️ 持久化配置不存在: {user_dir}")
                return False
        except Exception as e:
            print(f"❌ 清理失败: {e}")
            return False

    def list_all_profiles(self) -> List[Dict[str, Any]]:
        """
        列出所有持久化浏览器配置文件

        Returns:
            List[Dict]: 包含 platform, account_id, path, size_mb 的列表
        """
        import os
        profiles = []

        if not self.base_dir.exists():
            return profiles

        for item in self.base_dir.iterdir():
            if not item.is_dir():
                continue

            # 解析目录名 (格式: platform_account_id)
            parts = item.name.split('_', 1)
            if len(parts) == 2:
                platform, account_id = parts

                # 计算目录大小
                total_size = 0
                try:
                    for dirpath, dirnames, filenames in os.walk(item):
                        for filename in filenames:
                            filepath = Path(dirpath) / filename
                            if filepath.exists():
                                total_size += filepath.stat().st_size
                except Exception:
                    total_size = 0

                profiles.append({
                    "platform": platform,
                    "account_id": account_id,
                    "path": str(item),
                    "size_bytes": total_size,
                    "size_mb": round(total_size / 1024 / 1024, 2)
                })

        return profiles

    def cleanup_old_profiles(self, days: int = 30) -> int:
        """
        清理超过指定天数未使用的持久化配置

        Args:
            days: 天数阈值

        Returns:
            int: 清理的目录数量
        """
        import time
        import shutil

        if not self.base_dir.exists():
            return 0

        current_time = time.time()
        threshold = days * 24 * 3600
        cleaned = 0

        for item in self.base_dir.iterdir():
            if not item.is_dir():
                continue

            try:
                # 检查最后修改时间
                mtime = item.stat().st_mtime
                if current_time - mtime > threshold:
                    shutil.rmtree(item)
                    print(f"✅ 已清理旧配置: {item.name} (超过{days}天未使用)")
                    cleaned += 1
            except Exception as e:
                print(f"❌ 清理失败 {item.name}: {e}")

        return cleaned

    def get_total_size(self) -> Dict[str, Any]:
        """
        获取所有持久化配置的总大小

        Returns:
            Dict: 包含 total_bytes, total_mb, total_gb, profile_count
        """
        profiles = self.list_all_profiles()
        total_bytes = sum(p["size_bytes"] for p in profiles)

        return {
            "total_bytes": total_bytes,
            "total_mb": round(total_bytes / 1024 / 1024, 2),
            "total_gb": round(total_bytes / 1024 / 1024 / 1024, 2),
            "profile_count": len(profiles),
            "profiles": profiles
        }


# 全局实例
persistent_browser_manager = PersistentBrowserManager()

