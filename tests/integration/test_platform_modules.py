"""
测试平台模块化架构
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent / "syn_backend"))

async def test_verification_manager():
    """测试验证码管理器"""
    print("=" * 50)
    print("测试验证码管理器")
    print("=" * 50)
    
    from platforms.verification import verification_manager
    
    # 测试请求验证码
    event = verification_manager.request_verification(
        account_id="test_account",
        platform=3,
        message="测试验证码"
    )
    print(f"✅ 验证码请求已创建: {event}")
    
    # 测试获取事件
    events = verification_manager.get_pending_events()
    print(f"✅ 获取到 {len(events)} 个待处理事件")
    
    # 测试提交验证码
    success = verification_manager.submit_code("test_account", "123456")
    print(f"✅ 验证码提交: {'成功' if success else '失败'}")
    
    # 测试等待验证码（应该立即返回）
    code = await verification_manager.wait_for_code("test_account", timeout=2)
    print(f"✅ 收到验证码: {code}")
    
    print()


async def test_douyin_login():
    """测试抖音登录模块"""
    print("=" * 50)
    print("测试抖音登录模块")
    print("=" * 50)
    
    from platforms.douyin.login import douyin_login
    
    print(f"✅ 平台代码: {douyin_login.platform_code}")
    print(f"✅ 平台名称: {douyin_login.platform_name}")
    print(f"✅ 登录URL: {douyin_login.login_url}")
    print(f"✅ 上传URL: {douyin_login.upload_url}")
    
    print()


async def test_douyin_upload():
    """测试抖音上传模块"""
    print("=" * 50)
    print("测试抖音上传模块")
    print("=" * 50)
    
    from platforms.douyin.upload import douyin_upload
    
    print(f"✅ 平台代码: {douyin_upload.platform_code}")
    print(f"✅ 平台名称: {douyin_upload.platform_name}")
    print(f"✅ 上传URL: {douyin_upload.upload_url}")
    
    print()


async def test_base_platform():
    """测试平台基类"""
    print("=" * 50)
    print("测试平台基类")
    print("=" * 50)
    
    from platforms.base import BasePlatform
    
    class TestPlatform(BasePlatform):
        def __init__(self):
            super().__init__(platform_code=99, platform_name="测试平台")
        
        async def login(self, account_id: str, **kwargs):
            return {"success": True, "message": "测试登录"}
        
        async def upload(self, account_file: str, title: str, file_path: str, tags: list, **kwargs):
            return {"success": True, "message": "测试上传"}
    
    test_platform = TestPlatform()
    print(f"✅ 平台代码: {test_platform.platform_code}")
    print(f"✅ 平台名称: {test_platform.platform_name}")
    
    # 测试登录
    result = await test_platform.login("test_account")
    print(f"✅ 登录测试: {result}")
    
    # 测试上传
    result = await test_platform.upload("test.json", "测试标题", "test.mp4", ["标签1"])
    print(f"✅ 上传测试: {result}")
    
    print()


async def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("平台模块化架构测试")
    print("=" * 50 + "\n")
    
    try:
        await test_verification_manager()
        await test_douyin_login()
        await test_douyin_upload()
        await test_base_platform()
        
        print("=" * 50)
        print("✅ 所有测试通过！")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
