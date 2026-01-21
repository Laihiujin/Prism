"""
账号管理Service层
复用现有的 myUtils/cookie_manager.py
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import asyncio
import random

# 添加路径以导入现有模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from myUtils.cookie_manager import cookie_manager
from myUtils.cookie_manager import cookie_manager
from fastapi_app.core.logger import logger
from fastapi_app.core.exceptions import NotFoundException, BadRequestException


class AccountService:
    """账号管理服务"""

    def __init__(self):
        self.manager = cookie_manager

    async def list_accounts(
        self,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        获取账号列表

        Args:
            platform: 平台过滤
            status: 状态过滤
            skip: 跳过数量
            limit: 限制数量

        Returns:
            {total: int, items: List[Dict]}
        """
        try:
            accounts = self.manager.list_flat_accounts()

            # 过滤
            if platform:
                accounts = [a for a in accounts if a['platform'] == platform]
            if status:
                accounts = [a for a in accounts if a['status'] == status]

            total = len(accounts)
            items = accounts[skip:skip + limit]

            logger.info(f"查询账号列表: total={total}, platform={platform}, status={status}")
            return {"total": total, "items": items}
        except Exception as e:
            logger.error(f"查询账号列表失败: {e}")
            raise

    async def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """获取单个账号详情"""
        try:
            account = self.manager.get_account_by_id(account_id)
            if not account:
                raise NotFoundException(f"账号不存在: {account_id}")

            logger.info(f"查询账号详情: {account_id}")
            return account
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"查询账号详情失败: {e}")
            raise

    async def create_account(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建/添加账号"""
        try:
            platform = account_data.get("platform")
            self.manager.add_account(platform, account_data)

            logger.info(f"创建账号成功: {account_data.get('account_id')}")
            return {"success": True, "message": "账号创建成功"}
        except Exception as e:
            logger.error(f"创建账号失败: {e}")
            raise BadRequestException(f"创建账号失败: {str(e)}")

    async def update_account(
        self,
        account_id: str,
        update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新账号信息"""
        try:
            # 检查账号是否存在
            account = self.manager.get_account_by_id(account_id)
            if not account:
                raise NotFoundException(f"账号不存在: {account_id}")

            # 更新
            success = self.manager.update_account(account_id, **update_data)
            if not success:
                raise BadRequestException("更新失败")

            logger.info(f"更新账号成功: {account_id}")
            return {"success": True, "message": "账号更新成功"}
        except (NotFoundException, BadRequestException):
            raise
        except Exception as e:
            logger.error(f"更新账号失败: {e}")
            raise

    async def delete_account(self, account_id: str) -> Dict[str, Any]:
        """删除账号"""
        try:
            success = self.manager.delete_account(account_id)
            if not success:
                raise NotFoundException(f"账号不存在: {account_id}")

            logger.info(f"删除账号成功: {account_id}")
            return {"success": True, "message": "账号删除成功"}
        except NotFoundException:
            raise
        except Exception as e:
            logger.error(f"删除账号失败: {e}")
            raise



    async def deep_sync(self) -> Dict[str, Any]:
        """深度同步账号"""
        try:
            logger.info("开始深度同步账号")
            stats = self.manager.deep_sync_accounts()

            return {
                "success": True,
                "added": stats.get('added', 0),
                "marked_missing": stats.get('marked_missing', 0),
                "total_files": stats.get('total_files', 0),
                "backed_up": stats.get('backed_up', 0),
                "cleaned_up": stats.get('cleaned_up', 0),
                "message": f"同步完成: 新增 {stats['added']} 个, 标记丢失 {stats['marked_missing']} 个"
            }
        except Exception as e:
            logger.error(f"深度同步失败: {e}")
            raise

    async def delete_invalid_accounts(self) -> Dict[str, Any]:
        """删除所有失效账号"""
        try:
            count = self.manager.delete_invalid_accounts()
            logger.info(f"删除失效账号: {count} 个")
            return {
                "success": True,
                "count": count,
                "message": f"已删除 {count} 个失效账号"
            }
        except Exception as e:
            logger.error(f"删除失效账号失败: {e}")
            raise

    async def get_stats(self) -> Dict[str, int]:
        """获取账号统计"""
        try:
            accounts = self.manager.list_flat_accounts()

            stats = {
                "total": len(accounts),
                "valid": 0,
                "expired": 0,
                "error": 0,
                "file_missing": 0,
                "by_platform": {}
            }

            for acc in accounts:
                status = acc.get('status', 'unknown')
                platform = acc.get('platform', 'unknown')

                # 状态统计
                stats[status] = stats.get(status, 0) + 1

                # 平台统计
                stats['by_platform'][platform] = stats['by_platform'].get(platform, 0) + 1

            return stats
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
            raise




    async def check_account_status(
        self,
        platform: Optional[str] = None,
        account_ids: Optional[List[str]] = None,
        sample_size: Optional[int] = None,
        fallback: bool = False,
    ) -> Dict[str, Any]:
        """Fast status check: only update status/last_checked (no info changes)."""
        try:
            from myUtils.fast_cookie_validator import FastCookieValidator

            accounts = self.manager.list_flat_accounts()
            if platform:
                accounts = [a for a in accounts if a.get("platform") == platform]
            if account_ids:
                account_set = set(account_ids)
                accounts = [a for a in accounts if a.get("account_id") in account_set]

            total = len(accounts)
            if total == 0:
                return {"success": True, "checked": 0, "valid": 0, "expired": 0, "details": []}

            if sample_size is None:
                sample_size = min(5, total)
            else:
                sample_size = max(1, min(sample_size, total))

            random.shuffle(accounts)
            sample_accounts = accounts[:sample_size]

            validator = FastCookieValidator()
            tasks = [
                validator.validate_cookie_fast(
                    acc.get("platform"),
                    account_file=acc.get("cookie_file"),
                    fallback=fallback,
                )
                for acc in sample_accounts
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            checked = 0
            valid = 0
            expired = 0
            details = []
            for acc, result in zip(sample_accounts, results):
                checked += 1
                new_status = "expired"
                error = None
                elapsed_ms = None
                source = None
                if isinstance(result, Exception):
                    error = str(result)
                else:
                    new_status = "valid" if result.get("status") == "valid" else "expired"
                    error = result.get("error")
                    elapsed_ms = result.get("elapsed_ms")
                    source = result.get("source")

                self.manager.update_account_status(acc.get("platform"), acc.get("account_id"), new_status)
                if new_status == "valid":
                    valid += 1
                else:
                    expired += 1

                details.append(
                    {
                        "account_id": acc.get("account_id"),
                        "platform": acc.get("platform"),
                        "status": new_status,
                        "elapsed_ms": elapsed_ms,
                        "source": source,
                        "error": error,
                    }
                )

            return {
                "success": True,
                "checked": checked,
                "valid": valid,
                "expired": expired,
                "details": details,
            }
        except Exception as e:
            logger.error(f"Status check failed: {e}")
            raise


    async def sync_user_info(self) -> Dict[str, Any]:
        """同步所有账号的用户信息"""
        try:
            logger.info('开始同步用户信息')
            from myUtils.fetch_user_info_service import fetch_all_user_info
            stats = await fetch_all_user_info()

            return {
                'success': True,
                'total': stats.get('total', 0),
                'updated': stats.get('updated', 0),
                'failed': stats.get('failed', 0),
                'skipped': stats.get('skipped', 0),
                'message': f"同步完成: 更新 {stats['updated']} 个, 失败 {stats['failed']} 个, 跳过 {stats['skipped']} 个"
            }
        except Exception as e:
            logger.error(f'同步用户信息失败: {e}')
            raise

# 全局服务实例
account_service = AccountService()
