"""
运行平台探索器
遍历所有有效账号，执行深度探索，提取表头和新功能。
"""
import asyncio
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from myUtils.cookie_manager import cookie_manager
from myUtils.platform_explorer import explorer

async def main():
    print("="*60)
    print("🕵️‍♀️ 开始平台深度探索任务")
    print("="*60)
    
    # 获取所有账号
    accounts = cookie_manager.list_flat_accounts()
    valid_accounts = [acc for acc in accounts if acc['status'] == 'valid']
    
    if not valid_accounts:
        print("❌ 没有找到有效的账号，请先登录账号。")
        return

    print(f"📋 找到 {len(valid_accounts)} 个有效账号，准备开始探索...")
    
    for account in valid_accounts:
        print(f"\n>> 正在探索账号: {account['name']} ({account['platform']})")
        await explorer.start_exploration(account)
        
    print("\n" + "="*60)
    print("✅ 所有探索任务完成！")
    print("请查看 syn_backend/config/ 目录下的 platform_features_*.json 文件")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
