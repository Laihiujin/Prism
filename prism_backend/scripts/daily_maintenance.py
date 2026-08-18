"""
每日账号健康维护脚本
功能：
1. 遍历所有有效账号
2. 登录创作者平台
3. 停留60秒
4. 自动点击引导弹窗
5. 更新账号状态

建议配置为每日定时任务 (Crontab)
"""
import asyncio
import os
import sys
from pathlib import Path

# 添加父目录到 Python 路径
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from myUtils.cookie_manager import cookie_manager

async def main():
    print("="*50)
    print("🛡️  开始每日账号健康维护任务")
    print("="*50)
    
    try:
        results = await cookie_manager.run_maintenance()
        
        print("\n" + "="*50)
        print("📊 维护报告")
        print("="*50)
        print(f"✅ 成功: {results['success']}")
        print(f"❌ 过期: {results['expired']}")
        print(f"⚠️ 出错: {results['error']}")
        
        for detail in results['details']:
            icon = "✅" if detail['status'] == "success" else "❌"
            print(f"{icon} {detail['name']} ({detail['platform']}): {detail['status']}")
            
    except Exception as e:
        print(f"❌ 任务执行失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
