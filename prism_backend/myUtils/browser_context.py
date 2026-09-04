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
                # BASE_DIR 是 prism_backend，需要上一级到项目根目录
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
    返回 Firefox browser.launch() 的参数配置（视频号专用）。

    路径探测走 `_firefox_executable_path()`（静默），找不到也不打印"路径无效"类警告，
    避免在浏览器自适应解析时制造噪音（Firefox 未安装/已卸载在 patchright 下是常态）。
    """
    args: Dict[str, Any] = {
        "headless": False,
        "args": [],
    }
    ep = _firefox_executable_path()
    if ep:
        args["executable_path"] = ep
        print(f"✅ 使用 Firefox 浏览器: {ep}")
    else:
        print("ℹ️ 仓库/系统均未找到可用 Firefox，将使用 Playwright 默认 Firefox")
    return args


# ============================================
# 浏览器自适应「各自匹配兼容」公共入口
# ============================================
# 背景：历史遗留 uploader 里出现了「这个平台用 Firefox、那个用 Chromium」的
# 硬编码选择。patchright 只维护 Chromium（自身 Firefox build 本机常未安装，
# 且 patchright 无法驱动系统 Firefox），因此硬编码 `playwright.firefox` 的平台
# 一旦系统 Firefox 卸载/缺失就会直接失败。
#
# 这里提供统一的自适应启动器：按「本机确实可用的引擎」自动选择，并支持平台级
# 偏好（PRISM_PLATFORM_BROWSER_<PLATFORM>=chromium|firefox），缺引擎则兜底/报错，
# 而不是各自死定浏览器。
#
# 注意：本函数不注入任何 init script（patchright + 本机 Chrome 152 下，任何
# context.add_init_script(...) 都会导致后续 page.goto 报 net::ERR_CONNECTION_REFUSED）。

def _platform_browser_pref(platform: Optional[str]) -> Optional[str]:
    if not platform:
        return None
    name = str(platform).strip().lower()
    value = os.getenv(f"PRISM_PLATFORM_BROWSER_{name.upper()}")
    if value is None and name == "tencent":
        value = os.getenv("PRISM_PLATFORM_BROWSER_TENCENT")
    v = (value or "").strip().lower()
    if v in {"chromium", "firefox"}:
        return v
    return None


def _chromium_available(opts: Dict[str, Any]) -> bool:
    ep = opts.get("executable_path")
    if ep and Path(str(ep)).is_file():
        return True
    # 兜底：任意可用的 Chromium 系浏览器（系统 Chrome / Edge / Brave …）
    try:
        from utils.chrome_detector import get_chrome_executable
        p = Path(get_chrome_executable())
        if p.is_file():
            return True
    except Exception:
        pass
    return False


def _firefox_executable_path() -> Optional[str]:
    """静默探测可用的 patchright Firefox 可执行文件路径（不打印任何警告）。

    优先级与 build_firefox_args() 的探测保持一致，保证「可用」判断与真正 launch 一致：
      仓库内 Firefox(source=repo) -> LOCAL_FIREFOX_PATH/默认仓库路径 -> 任意 detected firefox。
    返回 None 表示本机没有可用的 Firefox。
    """
    # 0) 用户在 Tools 中明确应用的本机/组件 Firefox
    try:
        from tools.browser_provider_registry import active_provider_executable
        active = active_provider_executable("firefox")
        if active:
            return str(active)
    except Exception:
        pass
    # 1) 仓库内 patchright 专用 Firefox
    try:
        from utils.chrome_detector import list_detected_browsers
        for b in list_detected_browsers():
            if b.get("kind") == "firefox" and b.get("source") == "repo":
                p = Path(str(b["path"]))
                if p.is_file():
                    return b["path"]
    except Exception:
        pass
    # 2) LOCAL_FIREFOX_PATH 或默认仓库路径
    try:
        from config.conf import APP_ROOT
        ref = os.getenv("LOCAL_FIREFOX_PATH") or "browsers/firefox/firefox-1495/firefox/firefox.exe"
        fp = Path(str(ref))
        if not fp.is_absolute():
            fp = APP_ROOT / fp
        if fp.is_file():
            return str(fp.resolve())
    except Exception:
        pass
    # 3) 任意 detected firefox（系统/其它来源）
    try:
        from utils.chrome_detector import list_detected_browsers
        for b in list_detected_browsers():
            if b.get("kind") == "firefox":
                p = Path(str(b["path"]))
                if p.is_file():
                    return b["path"]
    except Exception:
        pass
    return None


def _firefox_available() -> bool:
    """直接探测本机是否存在可用的 patchright Firefox（不触发任何打印噪音）。"""
    return _firefox_executable_path() is not None


def _apply_headless(opts: Dict[str, Any], headless: bool) -> Dict[str, Any]:
    merged = dict(opts)
    merged["headless"] = headless
    return merged


_NO_PROXY_ARG_FLAGS = ("--no-proxy-server", "--proxy-bypass-list=*")


def _build_launch_opts(
    engine: str,
    headless: bool,
    extra_args: Optional[List[str]],
    proxy: Optional[Dict[str, Any]],
    extra_launch: Dict[str, Any],
) -> Dict[str, Any]:
    """
    组装 launch() 参数：
    - 以 build_browser_args()/build_firefox_args() 为基座（自动带本机可用的可执行文件、
      常用安全参数、默认直连/no-proxy），保持「现状优先（chromium 可用）」。
    - 显式 proxy 时去掉 no-proxy 参数并透传 proxy（避免代理被绕过）。
    - extra_args 追加到 args。
    - extra_launch（平台自定义 launch 参数：channel/executable_path/args/ignore_default_args/...）最后透传，
      优先于基座；若平台 pin 了 channel/executable_path，则去掉基座里的 executable_path 避免冲突。
    """
    opts = build_browser_args() if engine == "chromium" else build_firefox_args()

    if proxy:
        opts["args"] = [
            a for a in (opts.get("args") or []) if a not in _NO_PROXY_ARG_FLAGS
        ]
        opts["proxy"] = proxy

    if extra_args:
        opts["args"] = list(opts.get("args") or []) + list(extra_args)

    if extra_launch:
        if ("channel" in extra_launch) or ("executable_path" in extra_launch):
            opts.pop("executable_path", None)
        opts.update(extra_launch)

    opts["headless"] = headless
    return opts


def resolve_browser_launch_opts(
    *,
    platform: Optional[str] = None,
    browser: str = "auto",
    headless: bool = False,
    extra_args: Optional[List[str]] = None,
    proxy: Optional[Dict[str, Any]] = None,
    **extra_launch: Any,
) -> tuple[str, Dict[str, Any]]:
    """
    自动解析可用的浏览器引擎与 launch() 参数 —— 「各自匹配兼容」的统一入口。

    返回 (engine, launch_opts)，engine ∈ {'chromium','firefox'}。

    规则：
    - browser='auto'（默认）：先看平台偏好（PRISM_PLATFORM_BROWSER_<PLATFORM>），
      再以「本机确实可用」为准；都可用时优先 chromium，缺 chromium 再兜底 firefox。
    - browser='chromium'/'firefox'：校验该引擎本机可用，缺失则抛清晰错误（而非硬编码坏掉）。
    - proxy / extra_args / **extra_launch 作为「可插拔配置」透传，保证各平台保持现状。
    - 本函数不注入任何 init script。
    """
    normalized = str(browser or "auto").strip().lower()
    if normalized not in {"auto", "chromium", "firefox"}:
        normalized = "auto"

    chr_opts = _build_launch_opts("chromium", headless, extra_args, proxy, extra_launch)
    chr_ok = _chromium_available(chr_opts)

    # Firefox 缺席是常态：先用静默探测判断可用性，仅在真正选中 firefox 时才构建其 opts，
    # 避免每次都因 build_firefox_args() 打印"路径无效"噪音。
    ff_ok = _firefox_available()

    def _ff_opts() -> Dict[str, Any]:
        return _build_launch_opts("firefox", headless, extra_args, proxy, extra_launch)

    if normalized == "auto":
        pref = _platform_browser_pref(platform)
        if pref == "firefox" and ff_ok:
            return ("firefox", _ff_opts())
        if pref == "chromium" and chr_ok:
            return ("chromium", chr_opts)
        if chr_ok:
            return ("chromium", chr_opts)
        if ff_ok:
            return ("firefox", _ff_opts())
        raise RuntimeError(
            "未检测到可用浏览器：既无可用 Chrome/Chromium，也无可用 patchright Firefox。\n"
            "请确认本机安装了 Chrome 且 LOCAL_CHROME_PATH 指向它（或安装 patchright Firefox）。"
        )
    if normalized == "chromium":
        if chr_ok:
            return ("chromium", chr_opts)
        raise RuntimeError("已指定用 chromium，但本机未找到可用 Chrome/Chromium。")
    # firefox
    if ff_ok:
        return ("firefox", _ff_opts())
    raise RuntimeError(
        "已指定用 firefox，但本机未找到可用 patchright Firefox（Firefox 未安装 / 已卸载）。"
    )


def diagnose_launch_failure(exc: Exception) -> str:
    """用自定义算法判断浏览器启动失败的疑似原因（发布失败时优先自查，再套内置方案）。"""
    msg = str(exc)
    low = msg.lower()
    if (
        "executable doesn't exist" in low
        or "executable does not exist" in low
        or "no such file" in low
        or "filenotfounderror" in low.replace(" ", "")
    ):
        return "配置的浏览器可执行文件不存在/路径无效（executable_path）"
    if (
        "has not been installed" in low
        or "browser not found" in low
        or "install" in low
        or "missing browser" in low
    ):
        return "该浏览器引擎未安装（可考虑 install，或改用可用引擎）"
    if (
        "process failed to launch" in low
        or "target closed" in low
        or "browser has been closed" in low
        or "crashed" in low
    ):
        return "浏览器进程启动失败/被关闭（版本或参数不兼容）"
    if "connection" in low and ("refused" in low or "reset" in low):
        return "网络连接被拒（可能是 init script / 代理 / DNS 问题）"
    if "vtable" in low or "renderer" in low or "segmentation" in low:
        return "浏览器渲染内核崩溃（多为版本不兼容）"
    return f"未知的启动失败：{msg[:200]}"


def _chromium_fallback_opts(
    headless: bool,
    extra_args: Optional[List[str]],
    proxy: Optional[Dict[str, Any]],
    channel: bool = False,
) -> Dict[str, Any]:
    opts: Dict[str, Any] = {"headless": headless}
    if channel:
        opts["channel"] = "chromium"
    args = list(extra_args or [])
    if proxy:
        opts["proxy"] = proxy
        args.append("--no-sandbox")
    if args:
        opts["args"] = args
    return opts


async def launch_optional_browser(
    playwright,
    *,
    platform: Optional[str] = None,
    browser: str = "auto",
    headless: bool = False,
    extra_args: Optional[List[str]] = None,
    proxy: Optional[Dict[str, Any]] = None,
    **extra_launch: Any,
) -> Any:
    """按 resolve_browser_launch_opts 启动浏览器；失败时自动诊断并按内置方案回退。

    回退链（保持现状优先，仅失败才兜底）：
      首选引擎+平台配置 → (chromium) 去掉 executable_path 用默认 Chromium → channel=chromium → 另一引擎。
    """
    engine, opts = resolve_browser_launch_opts(
        platform=platform,
        browser=browser,
        headless=headless,
        extra_args=extra_args,
        proxy=proxy,
        **extra_launch,
    )

    attempts: list[tuple[str, Dict[str, Any], str]] = [
        (engine, opts, "首选引擎+平台配置"),
    ]
    if engine == "chromium":
        attempts.append(
            ("chromium", _chromium_fallback_opts(headless, extra_args, proxy), "去掉执行路径/用默认Chromium")
        )
        attempts.append(
            ("chromium", _chromium_fallback_opts(headless, extra_args, proxy, channel=True), "用 channel=chromium")
        )
    else:
        attempts.append(
            ("chromium", _chromium_fallback_opts(headless, extra_args, proxy), "回退到Chromium")
        )

    failures: list[str] = []
    for eng, launch_opts, label in attempts:
        try:
            return await getattr(playwright, eng).launch(**launch_opts)
        except Exception as e:  # pragma: no cover - runtime fallback
            diagnose = diagnose_launch_failure(e)
            failures.append(f"[{label}] {diagnose} -> {e}")
            print(f"⚠️ [browser] {eng} 启动失败（{label}）: {diagnose}")

    raise RuntimeError("所有浏览器启动方案均失败：\n" + "\n".join(failures))


async def launch_persistent_browser_context(
    playwright,
    *,
    platform: Optional[str] = None,
    browser: str = "auto",
    **launch_options: Any,
) -> Any:
    """Capability-aware persistent context launcher."""
    engine, resolved = resolve_browser_launch_opts(
        platform=platform,
        browser=browser,
        headless=bool(launch_options.pop("headless", False)),
        **launch_options,
    )
    return await getattr(playwright, engine).launch_persistent_context(**resolved)


async def connect_browser_over_cdp(playwright, cdp_url: str, *, platform: Optional[str] = None) -> Any:
    """Attach through CDP with an explicit Chromium capability guard."""
    engine, _ = resolve_browser_launch_opts(platform=platform, browser="auto", headless=False)
    if engine != "chromium":
        raise RuntimeError(
            f"平台 {platform or 'unknown'} 当前选择 {engine}，但 CDP attach 仅支持 Chromium；"
            "请将该平台浏览器切换为 Chromium 后重试。"
        )
    return await playwright.chromium.connect_over_cdp(cdp_url)


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
