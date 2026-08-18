import sys
import os
import asyncio
import logging

# 必须在任何其他导入之前设置 Windows 策略
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from myUtils.cookie_manager import cookie_manager
from myUtils.auth import check_cookie
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_sync():
    print("🚀 开始手动同步账号状态...")
    
    accounts = cookie_manager.list_flat_accounts()
    print(f"📋 找到 {len(accounts)} 个账号")
    
    for account in accounts:
        account_id = account['account_id']
        name = account['name']
        platform = account['platform']
        platform_code = account['platform_code']
        file_path = account['cookie_file']
        
        print(f"\n🔍 正在检测账号: {name} ({platform})...")
        
        if not file_path:
            print("   ⚠️ 跳过: 无 Cookie 文件")
            continue
            
        try:
            # 调用验证逻辑
            result = await check_cookie(platform_code, file_path)
            
            # 确定状态
            status = "expired"
            updates = {"last_checked": datetime.now().isoformat()}
            
            if isinstance(result, dict):
                status = result.get("status", "expired")
                updates["status"] = status
                if status == "valid":
                    print("   ✅ 状态有效")
                else:
                    print(f"   ❌ 状态失效 (原因: {result})")
            else:
                status = "valid" if result else "expired"
                updates["status"] = status
                if status == "valid":
                    print("   ✅ 状态有效")
                else:
                    print("   ❌ 状态失效")

            # 更新数据库
            success = cookie_manager.update_account(account_id, **updates)
            
            if success:
                print(f"   💾 数据库更新成功: status={status}")
            else:
                print(f"   ⚠️ 数据库更新失败! (可能ID不存在)")
                
        except Exception as e:
            print(f"   💥 检测出错: {e}")

    print("\n✨ 同步完成！请刷新前端页面查看结果。")

if __name__ == "__main__":
    try:
        asyncio.run(test_sync())
    except Exception as e:
        print(f"脚本执行出错: {e}")
