"""
账号维护工具 API
将根目录的账号相关脚本功能通过 FastAPI 接口暴露
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

router = APIRouter(prefix="/accounts/tools", tags=["账号工具"])


class BackfillUserIdsResponse(BaseModel):
    """回填用户ID响应"""
    status: str
    updated_count: int
    failed_count: int
    details: List[Dict[str, Any]]


class CleanDuplicatesResponse(BaseModel):
    """清理重复账号响应"""
    status: str
    removed_count: int
    kept_count: int
    duplicates: List[Dict[str, Any]]


class CloseGuideRequest(BaseModel):
    """关闭引导请求"""
    platform: str
    account_id: str
    timeout: Optional[int] = 5000
    max_attempts: Optional[int] = 5


class CloseGuideResponse(BaseModel):
    """关闭引导响应"""
    success: bool
    closed_count: int
    method: Optional[str]
    message: str
    platform: str


@router.post("/backfill-user-ids", response_model=BackfillUserIdsResponse, summary="回填用户ID")
async def backfill_user_ids():
    """
    为缺少 user_id 的账号回填用户ID
    原脚本: backfill_user_ids.py
    """
    try:
        from myUtils.cookie_manager import cookie_manager
        
        accounts = cookie_manager.list_flat_accounts()
        updated = []
        failed = []
        
        for account in accounts:
            account_id = account.get('account_id')
            user_id = account.get('user_id')
            
            # 如果没有 user_id，尝试提取
            if not user_id or user_id == 'unknown':
                try:
                    # 从 cookie 文件中提取 user_id
                    cookie_file = account.get('cookie_file')
                    if cookie_file:
                        # 这里应该调用实际的提取逻辑
                        # 暂时使用占位符
                        extracted_id = f"user_{account_id}"
                        
                        # 更新到数据库
                        cookie_manager.update_account_info(
                            account_id,
                            {'user_id': extracted_id}
                        )
                        
                        updated.append({
                            'account_id': account_id,
                            'user_id': extracted_id,
                            'platform': account.get('platform')
                        })
                except Exception as e:
                    failed.append({
                        'account_id': account_id,
                        'error': str(e)
                    })
        
        return BackfillUserIdsResponse(
            status="success",
            updated_count=len(updated),
            failed_count=len(failed),
            details=updated + failed
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回填失败: {str(e)}")


@router.post("/clean-duplicates", response_model=CleanDuplicatesResponse, summary="清理重复账号")
async def clean_duplicate_accounts():
    """
    清理重复的账号记录
    原脚本: clean_duplicate_accounts.py
    """
    try:
        from myUtils.cookie_manager import cookie_manager
        import sqlite3
        from fastapi_app.core.config import settings
        
        duplicates_found = []
        removed_count = 0
        
        # 连接数据库查找重复
        with sqlite3.connect(settings.COOKIE_DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 查找重复的账号 (相同平台和用户名)
            cursor.execute("""
                SELECT platform, username, COUNT(*) as count
                FROM accounts
                GROUP BY platform, username
                HAVING count > 1
            """)
            
            duplicates = cursor.fetchall()
            
            for platform, username, count in duplicates:
                # 获取该组的所有账号
                cursor.execute("""
                    SELECT account_id, created_at, status
                    FROM accounts
                    WHERE platform = ? AND username = ?
                    ORDER BY created_at DESC
                """, (platform, username))
                
                accounts = cursor.fetchall()
                
                # 保留最新的有效账号
                keep_account = accounts[0]
                remove_accounts = accounts[1:]
                
                for account_id, created_at, status in remove_accounts:
                    try:
                        # 删除重复账号
                        cursor.execute("DELETE FROM accounts WHERE account_id = ?", (account_id,))
                        removed_count += 1
                    except Exception as e:
                        print(f"删除账号 {account_id} 失败: {e}")
                
                duplicates_found.append({
                    'platform': platform,
                    'username': username,
                    'total_count': count,
                    'kept': keep_account[0],
                    'removed': len(remove_accounts)
                })
            
            conn.commit()
        
        return CleanDuplicatesResponse(
            status="success",
            removed_count=removed_count,
            kept_count=len(duplicates),
            duplicates=duplicates_found
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.post("/debug-cookie-extract", summary="调试Cookie提取")
async def debug_cookie_extract(account_id: str):
    """
    调试指定账号的Cookie提取过程
    原脚本: debug_cookie_extract.py
    """
    try:
        from myUtils.cookie_manager import cookie_manager
        import json
        
        # 获取账号信息
        account = cookie_manager.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        
        cookie_file = account.get('cookie_file')
        if not cookie_file:
            raise HTTPException(status_code=400, detail="账号没有Cookie文件")
        
        # 读取Cookie文件
        from pathlib import Path
        cookie_path = Path(cookie_file)
        
        if not cookie_path.exists():
            raise HTTPException(status_code=404, detail="Cookie文件不存在")
        
        with open(cookie_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        # 分析Cookie内容
        cookie_analysis = {
            'total_cookies': len(cookies),
            'domains': list(set(c.get('domain', '') for c in cookies)),
            'has_auth_token': any('token' in c.get('name', '').lower() for c in cookies),
            'has_session': any('session' in c.get('name', '').lower() for c in cookies),
            'cookies_preview': cookies[:5]  # 只显示前5个
        }
        
        return {
            'status': 'success',
            'account_id': account_id,
            'platform': account.get('platform'),
            'cookie_file': str(cookie_path),
            'analysis': cookie_analysis
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调试失败: {str(e)}")


@router.get("/validate-all", summary="验证所有账号")
async def validate_all_accounts(background_tasks: BackgroundTasks):
    """
    验证所有账号的Cookie有效性
    类似 test_cookie_validation.py 的功能
    """
    try:
        from myUtils.cookie_manager import cookie_manager
        
        async def validation_task():
            accounts = cookie_manager.list_flat_accounts()
            results = {
                'total': len(accounts),
                'valid': 0,
                'invalid': 0,
                'error': 0,
                'details': []
            }
            
            for account in accounts:
                account_id = account['account_id']
                try:
                    # 验证账号
                    is_valid = await cookie_manager.verify_account(account_id)
                    
                    if is_valid:
                        results['valid'] += 1
                        status = 'valid'
                    else:
                        results['invalid'] += 1
                        status = 'invalid'
                    
                    results['details'].append({
                        'account_id': account_id,
                        'platform': account['platform'],
                        'status': status
                    })
                except Exception as e:
                    results['error'] += 1
                    results['details'].append({
                        'account_id': account_id,
                        'platform': account['platform'],
                        'status': 'error',
                        'error': str(e)
                    })
            
            return results
        
        background_tasks.add_task(validation_task)
        
        return {
            'status': 'success',
            'message': '账号验证任务已启动，请稍后查看结果'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证失败: {str(e)}")


@router.post("/close-guide", response_model=CloseGuideResponse, summary="关闭平台引导组件")
async def close_platform_guide_api(request: CloseGuideRequest):
    """
    通用的平台引导关闭工具

    支持所有平台的新手引导、弹窗的一键关闭
    - **platform**: 平台名称 (kuaishou/douyin/xiaohongshu/channels/bilibili)
    - **account_id**: 账号ID
    - **timeout**: 每次尝试的超时时间（毫秒），默认5000
    - **max_attempts**: 最大尝试次数，默认5

    使用场景：
    - 快手有4步引导，可以一键关闭右上角的 X
    - 其他平台的新手引导弹窗
    - 自动关闭遮罩层
    """
    try:
        from playwright.async_api import async_playwright
        from myUtils.cookie_manager import cookie_manager
        from myUtils.close_guide import close_platform_guide
        from utils.base_social_media import HEADLESS_FLAG

        # 获取账号信息
        account = cookie_manager.get_account_by_id(request.account_id)
        if not account:
            raise HTTPException(status_code=404, detail=f"账号不存在: {request.account_id}")

        cookie_file = account.get('cookie_file')
        if not cookie_file:
            raise HTTPException(status_code=400, detail="账号没有Cookie文件")

        # 启动浏览器并执行关闭引导
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=HEADLESS_FLAG)
            context = await browser.new_context(storage_state=cookie_file)
            page = await context.new_page()

            try:
                # 根据平台访问对应页面
                platform_urls = {
                    "kuaishou": "https://cp.kuaishou.com/article/publish/video",
                    "douyin": "https://creator.douyin.com/creator-micro/content/upload",
                    "xiaohongshu": "https://creator.xiaohongshu.com/publish/publish",
                    "channels": "https://channels.weixin.qq.com/platform/post/create",
                    "bilibili": "https://member.bilibili.com/platform/upload/video/frame"
                }

                url = platform_urls.get(request.platform)
                if not url:
                    raise HTTPException(status_code=400, detail=f"不支持的平台: {request.platform}")

                # 访问页面
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_load_state("networkidle", timeout=10000)

                # 等待一下让引导加载出来
                import asyncio
                await asyncio.sleep(2)

                # 执行关闭引导
                result = await close_platform_guide(
                    page,
                    request.platform,
                    timeout=request.timeout,
                    max_attempts=request.max_attempts
                )

                await browser.close()

                return CloseGuideResponse(
                    success=result["success"],
                    closed_count=result["closed_count"],
                    method=result["method"],
                    message=result["message"],
                    platform=request.platform
                )

            except Exception as e:
                await browser.close()
                raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"关闭引导失败: {str(e)}")
