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
    """

    name = "patchright"

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

        pw = await async_playwright().start()
        context = await pw.chromium.launch_persistent_context(**launch_kwargs)
        page = context.pages[0] if context.pages else await context.new_page()

        logger.info(
            f"[PatchrightBackend] 启动 {account_id} user_data_dir={user_data_dir} "
            f"proxy={'已注入' if proxy else '直连'} locale={profile.get('locale')}"
        )
        session = BrowserSession(
            account_id=account_id,
            backend=self.name,
            context=context,
            page=page,
            browser=None,
            extra={"pw": pw, "user_data_dir": user_data_dir},
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
    """Persona Studio 后端（预留）。

    Persona Studio 负责指纹/Profile 持久化；Prism 只做 account_id ↔ persona_profile_id
    映射 + 注入固定 Proxy。接入时实现 start()：调用 Persona API 启动 profile 并取 CDP/上下文。
    """

    name = "persona"

    def __init__(self, api_base: Optional[str] = None):
        self.api_base = api_base  # 例如 http://127.0.0.1:PORT

    async def start(
        self,
        account_id: str,
        profile: Optional[Dict[str, Any]] = None,
        proxy: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> BrowserSession:
        raise NotImplementedError(
            "Persona Studio 尚未接入。接入后：persona_profile_id 启动 Profile，注入 proxy，返回 CDP 上下文。"
        )


class BrowserBackendManager:
    """统一入口：按 account.browser_backend 选择后端。"""

    _backends: Dict[str, BrowserBackend] = {}

    @classmethod
    def register(cls, backend: BrowserBackend):
        cls._backends[backend.name] = backend

    @classmethod
    def get(cls, name: str = "patchright") -> BrowserBackend:
        if not cls._backends:
            cls.register(PatchrightBackend())
            cls.register(PersonaBackend())
        backend = cls._backends.get(name)
        if backend is None:
            logger.warning(f"BrowserBackend '{name}' 未注册，回退 patchright")
            return cls._backends["patchright"]
        return backend


def get_browser_backend(name: str = "patchright") -> BrowserBackend:
    return BrowserBackendManager.get(name)
