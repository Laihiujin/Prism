"""
Persona Studio 客户端（Browser Identity / Fingerprint / Profile 层）。

对接开源 Persona Studio（TechQaiser/persona-studio）的 HTTP API：
    persona serve  →  http://127.0.0.1:8787

职责边界（Prism 不自研指纹/Profile 持久化）：
- Persona 负责：指纹生成、Profile 存储、Cookie/LocalStorage 持久会话、
  引擎选择（cloak/camoufox/patchright/playwright）、代理注入。
- Prism 负责：account_id ↔ persona_profile_id 映射、固定代理绑定、
  CDP attach 后用 Patchright 驱动浏览器执行平台 Adapter。

关键集成点：POST /api/profiles/{id}/attach 返回 wsUrl，
Prism 用 patchright connect_over_cdp 连接，Platform Adapter 无感知。
"""
import httpx
from typing import Any, Dict, Optional
from loguru import logger

from fastapi_app.core.config import settings


class PersonaClientError(Exception):
    """Persona Studio API 调用失败"""


class PersonaClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 15.0):
        self.base_url = (base_url or settings.PERSONA_API_BASE).rstrip("/")
        self.timeout = timeout

    # ─── 基础 ────────────────────────────────────────────────

    async def health(self) -> bool:
        """Persona serve 是否在线。"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/api/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_profiles(self) -> list:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/api/profiles")
            resp.raise_for_status()
            return resp.json()

    # ─── Profile CRUD ────────────────────────────────────────

    async def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """按 name 查找 Profile（Persona profile name = Prism persona_profile_id）。"""
        profiles = await self.list_profiles()
        for p in profiles:
            if p.get("name") == profile_id or p.get("id") == profile_id:
                return p
        return None

    async def create_profile(
        self,
        profile_id: str,
        *,
        proxy: Optional[Dict[str, Any]] = None,
        engine: Optional[str] = None,
        country: Optional[str] = None,
        locale: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建 Persona Profile（name = profile_id）。"""
        payload: Dict[str, Any] = {
            "name": profile_id,
            "engine": engine or settings.PERSONA_DEFAULT_ENGINE,
        }
        if proxy:
            # Proxy 模型: {"server": "http://user:pass@host:port", "country": "US"}
            payload["proxy"] = proxy
        if country:
            payload["country"] = country
        if locale:
            payload["locale"] = locale
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/profiles", json=payload)
            if resp.status_code >= 400:
                raise PersonaClientError(f"创建 Profile 失败: {resp.status_code} {resp.text[:200]}")
            return resp.json()

    async def ensure_profile(
        self,
        profile_id: str,
        *,
        proxy: Optional[Dict[str, Any]] = None,
        engine: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Dict[str, Any]:
        """确保 Profile 存在；存在则幂等（必要时更新代理）。"""
        existing = await self.get_profile(profile_id)
        if existing:
            return existing
        return await self.create_profile(
            profile_id, proxy=proxy, engine=engine, country=country
        )

    async def delete_profile(self, profile_id: str) -> bool:
        existing = await self.get_profile(profile_id)
        if not existing:
            return True
        pid = existing.get("id") or existing.get("name")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(f"{self.base_url}/api/profiles/{pid}")
            return resp.status_code < 400

    # ─── 启动 / 停止 / Attach ────────────────────────────────

    async def launch(self, profile_id: str, headless: bool = True) -> Dict[str, Any]:
        """启动 Profile（真实浏览器窗口）。"""
        existing = await self.get_profile(profile_id)
        if not existing:
            raise PersonaClientError(f"Profile {profile_id} 不存在")
        pid = existing.get("id") or existing.get("name")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/profiles/{pid}/launch",
                json={"headless": headless},
            )
            if resp.status_code >= 400:
                raise PersonaClientError(f"启动 Profile 失败: {resp.status_code} {resp.text[:200]}")
            return resp.json()

    async def attach(
        self, profile_id: str, headless: bool = True
    ) -> Dict[str, Any]:
        """Attach：以 CDP 方式打开，返回 wsUrl / port / snippets。

        Prism 用 patchright connect_over_cdp(wsUrl) 驱动该浏览器。
        """
        existing = await self.get_profile(profile_id)
        if not existing:
            raise PersonaClientError(f"Profile {profile_id} 不存在")
        pid = existing.get("id") or existing.get("name")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/profiles/{pid}/attach",
                json={"headless": headless},
            )
            if resp.status_code >= 400:
                raise PersonaClientError(f"Attach 失败: {resp.status_code} {resp.text[:200]}")
            return resp.json()

    async def stop(self, profile_id: str) -> bool:
        existing = await self.get_profile(profile_id)
        if not existing:
            return True
        pid = existing.get("id") or existing.get("name")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}/api/profiles/{pid}/stop")
            return resp.status_code < 400

    # ─── Cookies（旧 storage_state 迁移 / 登录态备份）─────────

    async def import_cookies(
        self, profile_id: str, storage_state: Dict[str, Any], clear: bool = False
    ) -> bool:
        """把 Prism 现有 storage_state（Playwright 格式）导入 Persona Profile。

        用于 Step 6 迁移：第一次启动 persistent profile 时加载旧登录态。
        """
        existing = await self.get_profile(profile_id)
        if not existing:
            return False
        pid = existing.get("id") or existing.get("name")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/profiles/{pid}/cookies",
                json={"storage_state": storage_state, "clear": clear},
            )
            return resp.status_code < 400

    async def export_cookies(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """导出 Persona Profile 的登录态（Playwright storage state 备份）。"""
        existing = await self.get_profile(profile_id)
        if not existing:
            return None
        pid = existing.get("id") or existing.get("name")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}/api/profiles/{pid}/cookies")
            if resp.status_code >= 400:
                return None
            return resp.json()

    # ─── 代理测试（复用 Persona 的探测能力）──────────────────

    async def proxy_test(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Persona 出口IP/国家/WebRTC 泄漏检测。"""
        existing = await self.get_profile(profile_id)
        if not existing:
            return None
        pid = existing.get("id") or existing.get("name")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/api/profiles/{pid}/proxy-test")
            if resp.status_code >= 400:
                return None
            return resp.json()


# 全局单例
_persona_client: Optional[PersonaClient] = None


def get_persona_client() -> PersonaClient:
    global _persona_client
    if _persona_client is None:
        _persona_client = PersonaClient()
    return _persona_client
