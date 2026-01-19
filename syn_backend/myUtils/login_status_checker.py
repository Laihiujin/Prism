"""
简单的账号登录状态监控模块
- 通过调用 Playwright Worker 访问创作者中心判断登录状态
- 等待3-5秒，检测URL是否包含"login"
- 仅更新 login_status 字段，不影响其他功能
"""
import asyncio
import random
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger

import httpx
from myUtils.cookie_manager import cookie_manager


# 平台创作者中心URL
PLATFORM_CREATOR_URLS = {
    "douyin": "https://creator.douyin.com/creator-micro/home",
    "xiaohongshu": "https://creator.xiaohongshu.com/new/home",  # 更新后的URL
    "kuaishou": "https://cp.kuaishou.com/profile",
    "channels": "https://channels.weixin.qq.com/platform/home",
    "bilibili": "https://member.bilibili.com/platform/home",
}


class LoginStatusChecker:
    """账号登录状态检查器"""

    def __init__(self):
        self.db_path = cookie_manager.db_path
        self.cookies_dir = cookie_manager.cookies_dir
        self._ensure_login_status_column()

        # 轮询跟踪器：记录已检查的账号索引
        self.rotation_index = 0

        # Playwright Worker URL
        self.worker_url = "http://127.0.0.1:7001"

    def _ensure_login_status_column(self):
        """确保 login_status 字段存在"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("PRAGMA table_info(cookie_accounts)")
                columns = [row[1] for row in cursor.fetchall()]
                if "login_status" not in columns:
                    conn.execute("ALTER TABLE cookie_accounts ADD COLUMN login_status TEXT DEFAULT 'unknown'")
                    logger.info("[LoginStatusChecker] 已添加 login_status 字段到数据库")
        except Exception as e:
            logger.error(f"[LoginStatusChecker] 添加 login_status 字段失败: {e}")

    def update_login_status(self, account_id: str, platform: str, login_status: str):
        """更新账号登录状态（仅更新 login_status 字段）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE cookie_accounts
                    SET login_status = ?
                    WHERE account_id = ? AND platform = ?
                    """,
                    (login_status, account_id, platform),
                )
                logger.info(f"[LoginStatusChecker] 更新账号 {account_id} ({platform}) 登录状态: {login_status}")
        except Exception as e:
            logger.error(f"[LoginStatusChecker] 更新登录状态失败 {account_id}: {e}")

    async def check_single_account_login_status(
        self, account_id: str, platform: str, cookie_file: str
    ) -> Dict[str, Any]:
        """
        检查单个账号的登录状态

        Returns:
            {
                "account_id": str,
                "platform": str,
                "login_status": "logged_in" | "session_expired" | "error" | "skipped",
                "final_url": str,
                "error": str (if any)
            }
        """
        result = {
            "account_id": account_id,
            "platform": platform,
            "login_status": "unknown",
            "final_url": None,
            "error": None,
        }

        # B站账号默认在线(使用不同登录机制)
        if platform == "bilibili":
            result["login_status"] = "logged_in"
            result["error"] = "B站账号使用不同登录机制,默认标记为在线"
            logger.info(f"[LoginStatusChecker] {account_id} (bilibili) 默认标记为在线")

            # 更新数据库状态为在线
            self.update_login_status(account_id, platform, "logged_in")
            return result

        # 获取创作者中心URL
        creator_url = PLATFORM_CREATOR_URLS.get(platform)
        if not creator_url:
            result["login_status"] = "error"
            result["error"] = f"不支持的平台: {platform}"
            logger.warning(f"[LoginStatusChecker] {result['error']}")
            return result

        # 读取 cookie 文件
        cookie_file_path = self.cookies_dir / cookie_file
        if not cookie_file_path.exists():
            result["login_status"] = "error"
            result["error"] = "Cookie文件不存在"
            logger.warning(f"[LoginStatusChecker] {account_id} Cookie文件不存在: {cookie_file_path}")
            return result

        try:
            with open(cookie_file_path, 'r', encoding='utf-8') as f:
                cookie_data = json.load(f)
        except Exception as e:
            result["login_status"] = "error"
            result["error"] = f"读取Cookie文件失败: {str(e)}"
            logger.error(f"[LoginStatusChecker] {account_id} 读取Cookie文件失败: {e}")
            return result

        # 调用 Playwright Worker 的 /creator/open 接口
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {
                    "platform": platform,
                    "account_id": account_id,
                    "storage_state": cookie_data,
                    "headless": True,  # 无头模式
                    "keep_alive": False,  # 检查完立即关闭
                }

                logger.info(f"[LoginStatusChecker] 调用 Playwright Worker 检查 {platform} 账号: {account_id}")

                response = await client.post(
                    f"{self.worker_url}/creator/open",
                    json=payload,
                    timeout=60.0
                )

                # 缩短等待时间到1-2秒 (足够让页面重定向)
                wait_time = random.uniform(1, 2)
                logger.info(f"[LoginStatusChecker] 等待 {wait_time:.2f} 秒...")
                await asyncio.sleep(wait_time)

                if response.status_code == 200:
                    # 成功访问，说明已登录
                    result["login_status"] = "logged_in"
                    result["final_url"] = creator_url
                    logger.info(f"[LoginStatusChecker] 账号 {account_id} ({platform}) 在线")

                    # 关闭会话
                    try:
                        resp_data = response.json()
                        session_id = resp_data.get("session_id")
                        if session_id:
                            await client.post(f"{self.worker_url}/creator/close", json={"session_id": session_id})
                    except Exception:
                        pass

                elif response.status_code == 401:
                    # 需要登录，说明cookies过期
                    result["login_status"] = "session_expired"
                    try:
                        error_data = response.json()
                        result["final_url"] = error_data.get("detail", "")
                        result["error"] = error_data.get("error", "Login required")
                    except Exception:
                        result["error"] = "Login required"
                    logger.warning(
                        f"[LoginStatusChecker] 账号 {account_id} ({platform}) 已掉线"
                    )
                else:
                    # 其他错误
                    result["login_status"] = "error"
                    try:
                        error_data = response.json()
                        result["error"] = error_data.get("error", f"HTTP {response.status_code}")
                    except Exception:
                        result["error"] = f"HTTP {response.status_code}"
                    logger.error(f"[LoginStatusChecker] {account_id} 检查失败: {result['error']}")

        except httpx.TimeoutException as e:
            result["login_status"] = "error"
            result["error"] = f"请求超时: {str(e)}"
            logger.error(f"[LoginStatusChecker] {account_id} 请求超时: {e}")
        except httpx.ConnectError as e:
            result["login_status"] = "error"
            result["error"] = f"无法连接到 Playwright Worker: {str(e)}"
            logger.error(f"[LoginStatusChecker] 无法连接到 Playwright Worker: {e}")
        except Exception as e:
            result["login_status"] = "error"
            result["error"] = f"请求异常: {str(e)}"
            logger.error(f"[LoginStatusChecker] {account_id} 请求异常: {e}")

        # 更新数据库中的登录状态
        self.update_login_status(account_id, platform, result["login_status"])

        return result

    def get_next_batch_accounts(self, batch_size: int = 5) -> list:
        """
        轮询策略：获取下一批要检查的账号

        Args:
            batch_size: 每批检查的账号数量

        Returns:
            账号列表
        """
        all_accounts = cookie_manager.list_flat_accounts()

        # 只检查状态为 'valid' 的账号,且排除B站账号
        valid_accounts = [
            acc for acc in all_accounts
            if acc.get("status") == "valid" and acc.get("platform") != "bilibili"
        ]

        if not valid_accounts:
            logger.info("[LoginStatusChecker] 没有有效账号需要检查")
            return []

        total_accounts = len(valid_accounts)

        # 如果索引超出范围，重置为0
        if self.rotation_index >= total_accounts:
            self.rotation_index = 0
            logger.info("[LoginStatusChecker] 轮询周期完成，重新开始")

        # 获取下一批账号
        end_index = min(self.rotation_index + batch_size, total_accounts)
        batch = valid_accounts[self.rotation_index:end_index]

        # 更新索引
        self.rotation_index = end_index

        logger.info(
            f"[LoginStatusChecker] 获取第 {self.rotation_index}/{total_accounts} 批账号 (本批 {len(batch)} 个, 已排除B站账号)"
        )

        return batch

    async def check_batch_accounts_async(self, batch_size: int = 5) -> Dict[str, Any]:
        """
        批量检查账号登录状态 (直接调用 Playwright Worker 的 /creator/check-login-status 端点)

        Args:
            batch_size: 每批检查的账号数量

        Returns:
            检查结果统计
        """
        logger.info(f"[LoginStatusChecker] 调用 Playwright Worker 批量检查登录状态 (batch_size={batch_size})")

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # 调用 Worker 的 /creator/check-login-status 端点（不指定account_ids，使用轮询策略）
                response = await client.post(
                    f"{self.worker_url}/creator/check-login-status",
                    json={"batch_size": batch_size},
                    timeout=120.0
                )

                if response.status_code != 200:
                    error_msg = f"Worker API error: HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", error_msg)
                    except Exception:
                        pass

                    logger.error(f"[LoginStatusChecker] Worker API调用失败: {error_msg}")
                    return {
                        "checked": 0,
                        "logged_in": 0,
                        "session_expired": 0,
                        "errors": 1,
                        "skipped": 0,
                        "details": [],
                        "error": error_msg,
                    }

                result = response.json()
                logger.info(
                    f"[LoginStatusChecker] 在线={result.get('logged_in', 0)}, "
                    f"掉线={result.get('session_expired', 0)}, 错误={result.get('errors', 0)}"
                )
                return result

        except httpx.ConnectError as e:
            logger.error(f"[LoginStatusChecker] 无法连接到 Playwright Worker: {e}")
            return {
                "checked": 0,
                "logged_in": 0,
                "session_expired": 0,
                "errors": 1,
                "skipped": 0,
                "details": [],
                "error": f"无法连接到 Worker: {str(e)}",
            }
        except Exception as e:
            logger.error(f"[LoginStatusChecker] 调用Worker失败: {e}")
            return {
                "checked": 0,
                "logged_in": 0,
                "session_expired": 0,
                "errors": 1,
                "skipped": 0,
                "details": [],
                "error": str(e),
            }

    def check_batch_accounts(self, batch_size: int = 5) -> Dict[str, Any]:
        """同步版本的批量检查（供调度器调用）"""
        try:
            return asyncio.run(self.check_batch_accounts_async(batch_size))
        except Exception as e:
            logger.error(f"[LoginStatusChecker] 批量检查失败: {e}")
            return {
                "checked": 0,
                "logged_in": 0,
                "session_expired": 0,
                "errors": 1,
                "skipped": 0,
                "details": [],
                "error": str(e),
            }


# 全局单例
login_status_checker = LoginStatusChecker()


if __name__ == "__main__":
    # 测试脚本
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        logger.info("开始测试登录状态检查器...")
        stats = login_status_checker.check_batch_accounts(batch_size=3)
        logger.info(f"测试完成: {stats}")
    else:
        print("用法: python login_status_checker.py test")
