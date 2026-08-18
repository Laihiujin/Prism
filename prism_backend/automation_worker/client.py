"""
Playwright Worker 客户端
FastAPI 使用此客户端与 Playwright Worker 通信
"""
import httpx
from typing import Dict, Any, Optional
from loguru import logger


class PlaywrightWorkerClient:
    """Playwright Worker HTTP 客户端"""

    def __init__(self, worker_url: str = "http://127.0.0.1:7001"):
        self.worker_url = worker_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def generate_qrcode(
        self,
        platform: str,
        account_id: str,
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        请求 Worker 生成二维码

        Args:
            platform: 平台名称
            account_id: 账号ID
            headless: 是否无头模式

        Returns:
            包含 session_id, qr_image 等的字典
        """
        try:
            url = f"{self.worker_url}/qrcode/generate"
            params = {
                "platform": platform,
                "account_id": account_id,
                "headless": headless
            }

            logger.info(f"[WorkerClient] Requesting QR: {platform} {account_id}")

            response = await self.client.post(url, params=params)
            try:
                data = response.json()
            except Exception:
                data = {}

            if response.status_code >= 400:
                worker_error = (data.get("error") if isinstance(data, dict) else None) or response.text
                raise RuntimeError(f"Playwright Worker error ({response.status_code}): {worker_error}".strip())

            if not isinstance(data, dict) or not data.get("success"):
                raise RuntimeError((data.get("error") if isinstance(data, dict) else None) or "Unknown error")

            return data.get("data") or {}

        except httpx.HTTPError as e:
            logger.error(f"[WorkerClient] HTTP error: {e}")
            raise Exception(f"Failed to communicate with Playwright Worker: {e}")
        except Exception as e:
            logger.error(f"[WorkerClient] Error: {e}")
            raise

    async def poll_status(self, session_id: str) -> Dict[str, Any]:
        """
        轮询登录状态

        Args:
            session_id: 会话ID

        Returns:
            登录状态信息
        """
        try:
            url = f"{self.worker_url}/qrcode/status/{session_id}"

            response = await self.client.get(url)
            try:
                data = response.json()
            except Exception:
                data = {}

            if response.status_code >= 400:
                worker_error = (data.get("error") if isinstance(data, dict) else None) or response.text
                raise RuntimeError(f"Playwright Worker error ({response.status_code}): {worker_error}".strip())

            if not isinstance(data, dict) or not data.get("success"):
                raise RuntimeError((data.get("error") if isinstance(data, dict) else None) or "Unknown error")

            return data.get("data") or {}

        except httpx.HTTPError as e:
            logger.error(f"[WorkerClient] HTTP error: {e}")
            raise Exception(f"Failed to poll status: {e}")
        except Exception as e:
            logger.error(f"[WorkerClient] Error: {e}")
            raise

    async def cancel_session(self, session_id: str) -> bool:
        """
        取消登录会话

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        try:
            url = f"{self.worker_url}/qrcode/cancel/{session_id}"

            response = await self.client.delete(url)
            response.raise_for_status()

            data = response.json()
            return data.get("success", False)

        except Exception as e:
            logger.error(f"[WorkerClient] Cancel failed: {e}")
            return False

    async def close_creator_center(self, session_id: str) -> bool:
        """
        关闭创作者中心浏览器会话
        """
        try:
            url = f"{self.worker_url}/creator/close/{session_id}"
            response = await self.client.delete(url)
            response.raise_for_status()
            data = response.json()
            return data.get("success", False)
        except Exception as e:
            logger.error(f"[WorkerClient] Close creator center failed: {e}")
            return False

    async def open_creator_center(
        self,
        platform: str,
        storage_state: Dict[str, Any],
        account_id: str | None = None,
        apply_fingerprint: bool = True,
        headless: bool = False,
        timeout_ms: int = 60000,
        expires_in: int = 3600,
        url: str | None = None,
    ) -> Dict[str, Any]:
        """
        Ask Worker to open a creator center page using the given storage_state.
        Returns {session_id, url}.
        """
        endpoint_url = f"{self.worker_url}/creator/open"
        payload = {
            "platform": platform,
            "storage_state": storage_state,
            "account_id": account_id,
            "apply_fingerprint": apply_fingerprint,
            "headless": headless,
            "timeout_ms": timeout_ms,
            "expires_in": expires_in,
            "url": url,
        }
        response = await self.client.post(endpoint_url, json=payload, timeout=30.0)
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.status_code >= 400:
            worker_error = (data.get("error") if isinstance(data, dict) else None) or response.text
            raise RuntimeError(f"Playwright Worker error ({response.status_code}): {worker_error}".strip())
        if not isinstance(data, dict) or not data.get("success"):
            raise RuntimeError((data.get("error") if isinstance(data, dict) else None) or "Unknown error")
        return data.get("data") or {}

    async def fetch_creator_sec_uid(
        self,
        platform: str,
        storage_state: Dict[str, Any],
        account_id: str | None = None,
        headless: bool = True,
        timeout_ms: int = 3000,
        input_selector: str | None = None,
    ) -> Dict[str, Any]:
        """Fetch sec_uid from creator center using storage_state."""
        url = f"{self.worker_url}/creator/sec-uid"
        payload = {
            "platform": platform,
            "storage_state": storage_state,
            "account_id": account_id,
            "headless": headless,
            "timeout_ms": timeout_ms,
            "input_selector": input_selector,
        }
        response = await self.client.post(url, json=payload, timeout=30.0)
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.status_code >= 400:
            worker_error = (data.get("error") if isinstance(data, dict) else None) or response.text
            raise RuntimeError(f"Playwright Worker error ({response.status_code}): {worker_error}".strip())
        if not isinstance(data, dict) or not data.get("success"):
            raise RuntimeError((data.get("error") if isinstance(data, dict) else None) or "Unknown error")
        return data.get("data") or {}

    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            Worker 是否正常运行
        """
        try:
            url = f"{self.worker_url}/health"
            response = await self.client.get(url, timeout=5.0)
            response.raise_for_status()
            return response.json().get("status") == "ok"
        except Exception:
            return False

    async def health_info(self) -> Dict[str, Any]:
        """获取 Worker 详细健康信息（用于故障诊断）。"""
        url = f"{self.worker_url}/health"
        response = await self.client.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return {"raw": data}
        return data

    async def enrich_account(
        self,
        platform: str,
        storage_state: Dict[str, Any],
        headless: bool = True,
        account_id: str | None = None,
    ) -> Dict[str, Any]:
        """
        使用 storage_state 在 Worker 内补全 user_id/name/avatar（DOM + cookie）。
        """
        url = f"{self.worker_url}/account/enrich"
        payload = {
            "platform": platform,
            "storage_state": storage_state,
            "headless": headless,
            "account_id": account_id,
        }
        response = await self.client.post(url, json=payload, timeout=30.0)
        try:
            data = response.json()
        except Exception:
            data = {}
        if response.status_code >= 400:
            worker_error = (data.get("error") if isinstance(data, dict) else None) or response.text
            raise RuntimeError(f"Playwright Worker error ({response.status_code}): {worker_error}".strip())
        if not isinstance(data, dict) or not data.get("success"):
            raise RuntimeError((data.get("error") if isinstance(data, dict) else None) or "Unknown error")
        return data.get("data") or {}

    async def close(self):
        """关闭客户端连接"""
        await self.client.aclose()


# 全局单例
_worker_client: Optional[PlaywrightWorkerClient] = None


def get_worker_client() -> PlaywrightWorkerClient:
    """获取 Worker 客户端单例"""
    global _worker_client
    if _worker_client is None:
        _worker_client = PlaywrightWorkerClient()
    return _worker_client
