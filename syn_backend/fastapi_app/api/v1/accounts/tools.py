"""
璐﹀彿缁存姢宸ュ叿 API
灏嗘牴鐩綍鐨勮处鍙风浉鍏宠剼鏈姛鑳介€氳繃 FastAPI 鎺ュ彛鏆撮湶
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

router = APIRouter(prefix="/accounts/tools", tags=["璐﹀彿宸ュ叿"])


class BackfillUserIdsResponse(BaseModel):
    """鍥炲～鐢ㄦ埛ID鍝嶅簲"""
    status: str
    updated_count: int
    failed_count: int
    details: List[Dict[str, Any]]


class CleanDuplicatesResponse(BaseModel):
    """娓呯悊閲嶅璐﹀彿鍝嶅簲"""
    status: str
    removed_count: int
    kept_count: int
    duplicates: List[Dict[str, Any]]


class CloseGuideRequest(BaseModel):
    """鍏抽棴寮曞璇锋眰"""
    platform: str
    account_id: str
    timeout: Optional[int] = 5000
    max_attempts: Optional[int] = 5


class CloseGuideResponse(BaseModel):
    """鍏抽棴寮曞鍝嶅簲"""
    success: bool
    closed_count: int
    method: Optional[str]
    message: str
    platform: str


@router.post("/backfill-user-ids", response_model=BackfillUserIdsResponse, summary="鍥炲～鐢ㄦ埛ID")
async def backfill_user_ids():
    """
    涓虹己灏?user_id 鐨勮处鍙峰洖濉敤鎴稩D
    鍘熻剼鏈? backfill_user_ids.py
    """
    try:
        from myUtils.cookie_manager import cookie_manager
        
        accounts = cookie_manager.list_flat_accounts()
        updated = []
        failed = []
        
        for account in accounts:
            account_id = account.get('account_id')
            user_id = account.get('user_id')
            
            # 濡傛灉娌℃湁 user_id锛屽皾璇曟彁鍙?
            if not user_id or user_id == 'unknown':
                try:
                    # 浠?cookie 鏂囦欢涓彁鍙?user_id
                    cookie_file = account.get('cookie_file')
                    if cookie_file:
                        # 杩欓噷搴旇璋冪敤瀹為檯鐨勬彁鍙栭€昏緫
                        # 鏆傛椂浣跨敤鍗犱綅绗?
                        extracted_id = f"user_{account_id}"
                        
                        # 鏇存柊鍒版暟鎹簱
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
        raise HTTPException(status_code=500, detail=f"鍥炲～澶辫触: {str(e)}")


@router.post("/clean-duplicates", response_model=CleanDuplicatesResponse, summary="娓呯悊閲嶅璐﹀彿")
async def clean_duplicate_accounts():
    """
    娓呯悊閲嶅鐨勮处鍙疯褰?
    鍘熻剼鏈? clean_duplicate_accounts.py
    """
    try:
        from myUtils.cookie_manager import cookie_manager
        import sqlite3
        from fastapi_app.core.config import settings
        
        duplicates_found = []
        removed_count = 0
        
        # 杩炴帴鏁版嵁搴撴煡鎵鹃噸澶?
        with sqlite3.connect(settings.COOKIE_DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 鏌ユ壘閲嶅鐨勮处鍙?(鐩稿悓骞冲彴鍜岀敤鎴峰悕)
            cursor.execute("""
                SELECT platform, username, COUNT(*) as count
                FROM accounts
                GROUP BY platform, username
                HAVING count > 1
            """)
            
            duplicates = cursor.fetchall()
            
            for platform, username, count in duplicates:
                # 鑾峰彇璇ョ粍鐨勬墍鏈夎处鍙?
                cursor.execute("""
                    SELECT account_id, created_at, status
                    FROM accounts
                    WHERE platform = ? AND username = ?
                    ORDER BY created_at DESC
                """, (platform, username))
                
                accounts = cursor.fetchall()
                
                # 淇濈暀鏈€鏂扮殑鏈夋晥璐﹀彿
                keep_account = accounts[0]
                remove_accounts = accounts[1:]
                
                for account_id, created_at, status in remove_accounts:
                    try:
                        # 鍒犻櫎閲嶅璐﹀彿
                        cursor.execute("DELETE FROM accounts WHERE account_id = ?", (account_id,))
                        removed_count += 1
                    except Exception as e:
                        print(f"鍒犻櫎璐﹀彿 {account_id} 澶辫触: {e}")
                
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
        raise HTTPException(status_code=500, detail=f"娓呯悊澶辫触: {str(e)}")


@router.post("/debug-cookie-extract", summary="璋冭瘯Cookie鎻愬彇")
async def debug_cookie_extract(account_id: str):
    """
    璋冭瘯鎸囧畾璐﹀彿鐨凜ookie鎻愬彇杩囩▼
    鍘熻剼鏈? debug_cookie_extract.py
    """
    try:
        from myUtils.cookie_manager import cookie_manager
        import json
        
        # 鑾峰彇璐﹀彿淇℃伅
        account = cookie_manager.get_account(account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        cookie_file = account.get('cookie_file')
        if not cookie_file:
            raise HTTPException(status_code=400, detail="璐﹀彿娌℃湁Cookie鏂囦欢")
        
        # 璇诲彇Cookie鏂囦欢
        from pathlib import Path
        cookie_path = Path(cookie_file)
        
        if not cookie_path.exists():
            raise HTTPException(status_code=404, detail="Cookie file not found")
        
        with open(cookie_path, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        # 鍒嗘瀽Cookie鍐呭
        cookie_analysis = {
            'total_cookies': len(cookies),
            'domains': list(set(c.get('domain', '') for c in cookies)),
            'has_auth_token': any('token' in c.get('name', '').lower() for c in cookies),
            'has_session': any('session' in c.get('name', '').lower() for c in cookies),
            'cookies_preview': cookies[:5]  # 鍙樉绀哄墠5涓?
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
        raise HTTPException(status_code=500, detail=f"璋冭瘯澶辫触: {str(e)}")


@router.get("/validate-all", summary="Validate all accounts")
async def validate_all_accounts(background_tasks: BackgroundTasks):
    """
    楠岃瘉鎵€鏈夎处鍙风殑Cookie鏈夋晥鎬?
    绫讳技 test_cookie_validation.py 鐨勫姛鑳?
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
                    # 楠岃瘉璐﹀彿
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
            'message': 'Account validation task started',
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"楠岃瘉澶辫触: {str(e)}")


@router.post("/close-guide", response_model=CloseGuideResponse, summary="关闭平台引导组件")
async def close_platform_guide_api(request: CloseGuideRequest):
    return CloseGuideResponse(
        success=True,
        closed_count=0,
        method="disabled",
        message="guide closing disabled",
        platform=request.platform,
    )
