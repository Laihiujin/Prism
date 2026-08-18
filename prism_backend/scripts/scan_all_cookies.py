"""
全量Cookie扫描与诊断脚本
功能：
1. 扫描 cookiesFile 目录下所有文件
2. 自动识别平台
3. 调用 auth.py 进行深度检测
4. 输出最终状态报告
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# 添加父目录到 Python 路径
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from myUtils.auth import check_cookie
from myUtils.cookie_manager import cookie_manager

COOKIES_DIR = cookie_manager.cookies_dir

PLATFORM_MAP = {
    "douyin": 3,
    "kuaishou": 4,
    "xiaohongshu": 1,
    "tencent": 2,
    "bilibili": 5
}

def identify_platform(cookie_data):
    """根据cookie内容识别平台"""
    # Normalize data
    if isinstance(cookie_data, dict) and 'cookies' in cookie_data:
        cookie_data = cookie_data['cookies']
    
    if not isinstance(cookie_data, list):
        return None
    
    domains = set()
    for cookie in cookie_data:
        if 'domain' in cookie:
            domains.add(cookie['domain'])
            
    # Simple heuristics
    for domain in domains:
        if "douyin" in domain: return "douyin"
        if "kuaishou" in domain: return "kuaishou"
        if "xiaohongshu" in domain: return "xiaohongshu"
        if "bilibili" in domain: return "bilibili"
        if "channels.weixin.qq.com" in domain: return "tencent"
        # Tencent fallback
        if "qq.com" in domain and not "bilibili" in domain: return "tencent"
        
    return "unknown"

async def scan_all():
    # 1. Get all accounts from DB
    from myUtils.cookie_manager import cookie_manager
    accounts = cookie_manager.list_flat_accounts()
    
    print(f"📋 数据库中共有 {len(accounts)} 个账号")
    
    results = []
    
    # 2. Check each account
    for account in accounts:
        account_id = account['account_id']
        name = account['name']
        platform = account['platform']
        platform_code = account['platform_code']
        filename = account['cookie_file']
        
        print(f"\n🔍 检查账号: {name} ({platform})")
        
        if not filename:
            print(f"  ❌ 错误: 数据库中未记录文件名")
            results.append({"name": name, "platform": platform, "status": "missing_config"})
            continue
            
        file_path = COOKIES_DIR / filename
        if not file_path.exists():
            print(f"  ❌ 错误: Cookie文件丢失 ({filename})")
            results.append({"name": name, "platform": platform, "status": "missing_file"})
            continue
            
        # File exists, check validity
        print(f"  ✅ 文件存在，开始检测有效性...")
        try:
            # check_cookie expects just the filename
            res = await check_cookie(platform_code, filename)
            status = res.get("status", "error")
            real_name = res.get("name", "N/A")
            
            print(f"  📊 状态: {status}")
            if status == "valid":
                print(f"  👤 验证用户名: {real_name}")
            
            results.append({
                "name": name, 
                "platform": platform, 
                "status": status,
                "real_name": real_name
            })
            
        except Exception as e:
            print(f"  ❌ 检测出错: {e}")
            results.append({"name": name, "platform": platform, "status": "error", "error": str(e)})

    # 3. Check for orphan files (files not in DB)
    db_files = set(a['cookie_file'] for a in accounts if a['cookie_file'])
    disk_files = set(f.name for f in COOKIES_DIR.glob("*.json"))
    orphans = disk_files - db_files
    
    print("\n" + "="*60)
    print("📊 最终全量报告 (8个账号)")
    print("="*60)
    
    # Group by platform
    by_platform = {}
    for r in results:
        p = r['platform']
        if p not in by_platform: by_platform[p] = []
        by_platform[p].append(r)
        
    for p, items in by_platform.items():
        print(f"\n[{p}]")
        for r in items:
            status = r['status']
            icon = "✅" if status == "valid" else "❌"
            if status == "missing_file": icon = "📁❌"
            
            note = ""
            if status == "missing_file": note = " (文件丢失, 需重新登录)"
            elif status == "expired": note = " (Cookie过期, 需重新登录)"
            elif status == "valid": note = f" (用户: {r.get('real_name', 'N/A')})"
            
            print(f"  {icon} {r['name']}: {status.upper()}{note}")

    if orphans:
        print(f"\n🗑️  发现 {len(orphans)} 个无主文件 (建议清理):")
        for f in orphans:
            print(f"  - {f}")

if __name__ == "__main__":
    asyncio.run(scan_all())
