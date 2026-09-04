"""
BrowserBackend 薄适配层（Browser Identity / Fingerprint / Profile 层）。

最终架构：Prism + Persona Studio + Patchright + Proxy Manager。
- Prism 不自研指纹/BrowserProfile 持久化（交给 Persona Studio）。
- 一个 Prism Account ↔ 一个 Persona Profile（account.persona_profile_id）。
- 平台 Adapter 不感知具体 Browser Backend，只通过本层获取 context/page。

后端：
- patchright：现有生产运行时（persistent context，账号级隔离）
- persona：Persona Studio（预留，待接入后实现 start/stop/get_page）

固定链路：Account → Persona Profile → Fingerprint → Sticky Proxy → Patchright → Platform Adapter
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from loguru import logger


@dataclass
class BrowserSession:
    """一次账号浏览器会话的句柄。release 仅关闭进程，Profile 数据永久保留。"""
    account_id: str
    backend: str
    generation: int = 1
    context: Any = None          # BrowserContext / Persona session
    page: Any = None             # Page
    browser: Any = None          # Browser process handle
    extra: Dict[str, Any] = field(default_factory=dict)

    async def close(self):
        """关闭浏览器进程（保留 profile）。"""
        try:
            if self.context is not None:
                try:
                    await self.context.close()
                except Exception as e:
                    logger.debug(f"[BrowserSession] context close: {e}")
            if self.browser is not None:
                try:
                    await self.browser.close()
                except Exception as e:
                    logger.debug(f"[BrowserSession] browser close: {e}")
        except Exception as e:
            logger.warning(f"[BrowserSession] close 异常 {self.account_id}: {e}")
        finally:
            self.context = None
            self.page = None
            self.browser = None


class BrowserBackend:
    """Browser Backend 统一接口。平台 Adapter 不直接调用底层库。"""

    name = "base"
    capabilities = frozenset()

    async def start(
        self,
        account_id: str,
        profile: Optional[Dict[str, Any]] = None,
        proxy: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BrowserSession:
        raise NotImplementedError

    async def stop(self, session: BrowserSession):
        raise NotImplementedError

    async def get_page(self, session: BrowserSession):
        if session.page is None:
            raise RuntimeError("browser session 未启动")
        return session.page

    async def health(self, account_id: str) -> Dict[str, Any]:
        raise NotImplementedError


class PatchrightBackend(BrowserBackend):
    """Patchright 生产后端（现有运行时兼容）。

    账号级隔离：每账号独立 user_data_dir（persistent context）。
    storage_state 仅作迁移/备份，不作为生产主机制。

    浏览器来源（只读用户本机浏览器，不随安装包分发任何浏览器）：
      - start() 未显式指定 executable_path 时，自动检测本机已安装的
        Chrome / Edge / Firefox / Brave / Opera / Vivaldi / Arc / Chromium；
      - 检测不到时抛清晰错误，绝不自动下载浏览器。
    """

    name = "patchright"
    capabilities = frozenset({"persistent_context", "chromium", "firefox", "proxy", "headful"})

    def __init__(self, profile_root: Optional[str] = None):
        self.profile_root = profile_root or "data/browser_profiles"
        from pathlib import Path
        Path(self.profile_root).mkdir(parents=True, exist_ok=True)

    def _user_data_dir(self, account_id: str) -> str:
        import os
        from pathlib import Path
        # 账号级独立目录：data/browser_profiles/<account_id>/
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in account_id)
        return str(Path(self.profile_root) / safe)

    def _resolve_local_browser(self) -> Optional[Any]:
        """
        检测本机已安装的主流浏览器（进程内缓存，成功检测后不再重复扫描）。
        返回 dict: {name, kind, path}；kind='chromium' 用 pw.chromium，'firefox' 用 pw.firefox。
        找不到返回 None（不抛异常，由调用方给出清晰报错）。
        """
        cached = getattr(self, "_detected_browser", None)
        if cached is not None:
            from pathlib import Path
            if Path(cached["path"]).is_file():
                return cached
            logger.warning(f"[PatchrightBackend] 缓存浏览器已失效，重新扫描: {cached['path']}")
            self._detected_browser = None

        try:
            from utils.chrome_detector import detect_browser

            info = detect_browser()
        except Exception as e:
            logger.warning(f"[PatchrightBackend] 浏览器检测失败: {e}")
            return None

        if info is None:
            return None
        result = {"name": info.name, "kind": info.kind, "path": info.path}
        self._detected_browser = result
        logger.info(f"[PatchrightBackend] 使用本机浏览器: {info.name} -> {info.path}")
        return result

    async def start(
        self,
        account_id: str,
        profile: Optional[Dict[str, Any]] = None,
        proxy: Optional[Dict[str, Any]] = None,
        headless: bool = True,
        **kwargs,
    ) -> BrowserSession:
        from utils.automation_provider import async_playwright

        user_data_dir = self._user_data_dir(account_id)
        profile = profile or {}

        launch_kwargs: Dict[str, Any] = {
            "user_data_dir": user_data_dir,
            "headless": headless,
        }
        if proxy:
            launch_kwargs["proxy"] = proxy
        if profile.get("locale"):
            launch_kwargs["locale"] = profile["locale"]
        if profile.get("timezone_id"):
            launch_kwargs["timezone_id"] = profile["timezone_id"]

        # 引擎选择：调用方显式传入 executable_path 时按其类型，否则检测本机浏览器
        engine = "chromium"
        if "executable_path" not in launch_kwargs:
            browser = self._resolve_local_browser()
            if browser is None:
                raise RuntimeError(
                    "未检测到本机浏览器（Google Chrome / Microsoft Edge / Firefox / "
                    "Brave / Opera / Vivaldi / Arc / Chromium）。\n"
                    "请安装任一主流浏览器后重试，或设置 LOCAL_CHROME_PATH / "
                    "LOCAL_FIREFOX_PATH 环境变量指向已安装的浏览器。"
                )
            launch_kwargs["executable_path"] = browser["path"]
            engine = browser["kind"]

        pw = await async_playwright().start()
        browser_api = getattr(pw, engine)  # pw.chromium / pw.firefox
        context = await browser_api.launch_persistent_context(**launch_kwargs)
        page = context.pages[0] if context.pages else await context.new_page()

        logger.info(
            f"[PatchrightBackend] 启动 {account_id} engine={engine} "
            f"user_data_dir={user_data_dir} "
            f"proxy={'已注入' if proxy else '直连'} locale={profile.get('locale')}"
        )
        session = BrowserSession(
            account_id=account_id,
            backend=self.name,
            context=context,
            page=page,
            browser=None,
            extra={"pw": pw, "user_data_dir": user_data_dir, "engine": engine},
        )
        return session

    async def stop(self, session: BrowserSession):
        await session.close()
        pw = session.extra.pop("pw", None)
        if pw is not None:
            try:
                await pw.stop()
            except Exception:
                pass

    async def health(self, account_id: str) -> Dict[str, Any]:
        return {
            "backend": self.name,
            "account_id": account_id,
            "profile_dir": self._user_data_dir(account_id),
            "status": "ready",
        }


class PersonaBackend(BrowserBackend):
    """Persona Studio 后端（Browser Identity / Fingerprint / Profile 层）。

    Prism 不自研指纹/Profile 持久化，全部交给 Persona Studio：
    - account_id ↔ persona_profile_id 一一映射（Prism 账号表维护）
    - Persona 负责指纹生成、Profile 存储、Cookie/LocalStorage 持久会话、
      引擎选择（cloak/camoufox/patchright/playwright）、代理注入
    - Prism 通过 Persona HTTP API attach CDP，再用 patchright connect_over_cdp
      驱动浏览器执行平台 Adapter（Platform Adapter 无感知）

    链路：Account → Persona Profile → Fingerprint → Sticky Proxy → Patchright → Platform Adapter
    """

    name = "persona"
    capabilities = frozenset({"persistent_profile", "cdp_attach", "identity", "proxy", "headful"})

    def __init__(self, api_base: Optional[str] = None):
        self.api_base = api_base  # http://127.0.0.1:8787

    def _client(self):
        from fastapi_app.services.persona_client import PersonaClient
        return PersonaClient(base_url=self.api_base)

    async def start(
        self,
        account_id: str,
        profile: Optional[Dict[str, Any]] = None,
        proxy: Optional[Dict[str, Any]] = None,
        headless: bool = True,
        **kwargs,
    ) -> BrowserSession:
        from fastapi_app.core.config import settings
        from utils.automation_provider import async_playwright

        profile = profile or {}
        client = self._client()

        # ── Account ↔ Persona Profile 持久映射 ──
        # 1) 账号表已存 persona_profile_id → 永久复用
        # 2) 未存 → 创建（name=platform_account_id）并写回账号表
        # 3) 已存但 Persona 侧丢失 → 明确 repair 流程，不静默新建身份
        account_binding = None
        try:
            from myUtils.cookie_manager import cookie_manager
            account_binding = cookie_manager.get_account_binding(account_id) or {}
        except Exception:
            pass

        stored_profile_id = (account_binding or {}).get("persona_profile_id")
        platform = (account_binding or {}).get("platform") or profile.get("platform") or "account"
        if not stored_profile_id:
            # 首次：创建 <platform>_<account_id> 便于人工定位
            persona_profile_id = f"{platform}_{account_id}" if platform != account_id else account_id
            await client.ensure_profile(
                persona_profile_id,
                proxy=proxy if settings.PERSONA_INJECT_PROXY else None,
                engine=kwargs.get("engine") or settings.PERSONA_DEFAULT_ENGINE,
                country=(proxy or {}).get("country"),
            )
            # 写回账号表（持久化）
            try:
                from myUtils.cookie_manager import cookie_manager
                cookie_manager.set_account_binding(account_id, persona_profile_id=persona_profile_id)
            except Exception as e:
                logger.warning(f"[PersonaBackend] 持久化 persona_profile_id 失败 {account_id}: {e}")
            logger.info(f"[PersonaBackend] 首次创建 Profile {persona_profile_id} 并绑定账号 {account_id}")
        else:
            persona_profile_id = stored_profile_id
            # 已存：检查 Persona 侧是否存在（丢失 → repair，不静默重建）
            existing = await client.get_profile(persona_profile_id)
            if existing is None:
                raise RuntimeError(
                    f"Persona Profile '{persona_profile_id}' 已从 Persona 侧丢失，"
                    "需要显式 repair/recreate（不静默生成新身份）。"
                    "请删除账号表 persona_profile_id 后重新 start，或人工在 Persona 重建。"
                )
            # 存在：如传入代理且与 Persona Profile 当前不一致，同步代理配置（rebind 场景）
            if proxy and settings.PERSONA_INJECT_PROXY:
                p_proxy = existing.get("proxy") or {}
                p_server = p_proxy.get("server") if isinstance(p_proxy, dict) else None
                if p_server != proxy.get("server"):
                    logger.info(
                        f"[PersonaBackend] 账号 {account_id} rebind 检测到代理变化，"
                        f"同步 Persona Profile {persona_profile_id}: {p_server} -> {proxy.get('server')}"
                    )
                    await client.update_profile(persona_profile_id, proxy=proxy)

        # 2. Attach CDP（headless 模式由调用方决定）
        attach = await client.attach(persona_profile_id, headless=headless)
        ws_url = attach.get("wsUrl") or attach.get("ws_url")
        if not ws_url:
            raise RuntimeError(
                f"Persona attach 未返回 wsUrl: {attach}（请确认 persona serve 已启动且引擎已安装）"
            )

        # 3. 用 Patchright 连接 CDP（Platform Adapter 无感知）
        pw = await async_playwright().start()
        browser = await pw.chromium.connect_over_cdp(ws_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()

        logger.info(
            f"[PersonaBackend] 启动 {account_id} persona_profile={persona_profile_id} "
            f"engine={kwargs.get('engine') or settings.PERSONA_DEFAULT_ENGINE} "
            f"proxy={'已注入' if proxy else '直连'} headless={headless}"
        )
        return BrowserSession(
            account_id=account_id,
            backend=self.name,
            context=context,
            page=page,
            browser=browser,
            extra={
                "pw": pw,
                "persona_profile_id": persona_profile_id,
                "client": client,
            },
        )

    async def stop(self, session: BrowserSession):
        persona_profile_id = session.extra.get("persona_profile_id")
        client = session.extra.get("client")
        await session.close()
        pw = session.extra.pop("pw", None)
        if pw is not None:
            try:
                await pw.stop()
            except Exception:
                pass
        # 停止 Persona 侧浏览器进程（Profile 数据保留）
        if client is not None and persona_profile_id:
            try:
                await client.stop(persona_profile_id)
            except Exception as e:
                logger.warning(f"[PersonaBackend] persona stop 失败: {e}")

    async def health(self, account_id: str) -> Dict[str, Any]:
        client = self._client()
        online = await client.health()
        return {
            "backend": self.name,
            "account_id": account_id,
            "persona_api": self.api_base,
            "status": "online" if online else "offline",
        }


class BrowserBackendManager:
    """统一入口：按 account.browser_backend 选择后端。"""

    _backends: Dict[str, BrowserBackend] = {}

    @classmethod
    def register(cls, backend: BrowserBackend):
        cls._backends[backend.name] = backend

    @classmethod
    def _ensure_registered(cls) -> None:
        if not cls._backends:
            cls.register(PatchrightBackend())
            cls.register(PersonaBackend())

    @classmethod
    def describe(cls) -> Dict[str, Dict[str, Any]]:
        cls._ensure_registered()
        return {
            name: {"name": name, "capabilities": sorted(backend.capabilities)}
            for name, backend in cls._backends.items()
        }

    @classmethod
    def require_capability(cls, name: str, capability: str) -> BrowserBackend:
        backend = cls.get(name)
        if capability not in backend.capabilities:
            raise RuntimeError(f"Browser backend '{backend.name}' does not support capability '{capability}'")
        return backend

    @classmethod
    def get(cls, name: Optional[str] = None) -> BrowserBackend:
        cls._ensure_registered()
        # 别名：persona-studio / persona_studio → persona
        if name is None:
            from fastapi_app.services.browser_runtime import get_default_browser_backend
            name = get_default_browser_backend()
        normalized = {
            "persona-studio": "persona",
            "persona_studio": "persona",
            "camofox": "persona",
        }.get(name, name)
        backend = cls._backends.get(normalized)
        if backend is None:
            logger.warning(f"BrowserBackend '{name}' 未注册，回退 patchright")
            return cls._backends["patchright"]
        return backend


def get_browser_backend(name: Optional[str] = None) -> BrowserBackend:
    return BrowserBackendManager.get(name)
