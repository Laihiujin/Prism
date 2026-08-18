"""
测试脚本 - 验证平台适配器独立模块

使用方法:
    python test_platform_adapters.py bilibili
    python test_platform_adapters.py douyin
    python test_platform_adapters.py kuaishou
    python test_platform_adapters.py xiaohongshu
    python test_platform_adapters.py tencent
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app_new.platforms import (
    BilibiliAdapter,
    DouyinAdapter,
    KuaishouAdapter,
    XiaohongshuAdapter,
    TencentAdapter
)
from app_new.platforms.base import LoginStatus


async def test_bilibili():
    """测试B站登录流程"""
    print("="*70)
    print("测试 B站 登录流程")
    print("="*70)

    adapter = BilibiliAdapter()

    # Step 1: 生成二维码
    print("\n[Step 1] 生成二维码...")
    try:
        qr_data = await adapter.get_qrcode()
        print(f"✅ 二维码生成成功!")
        print(f"   Session ID: {qr_data.session_id[:12]}...")
        print(f"   QR URL: {qr_data.qr_url}")
        print(f"   QR Image: {qr_data.qr_image[:60]}...")
        print(f"   过期时间: {qr_data.expires_in}秒")
    except Exception as e:
        print(f"❌ 二维码生成失败: {e}")
        return False

    # Step 2: 轮询登录状态
    print("\n[Step 2] 请使用B站APP扫描二维码...")
    print("开始轮询登录状态 (每2秒一次，最多60次)...")

    session_id = qr_data.session_id
    for i in range(60):
        await asyncio.sleep(2)
        result = await adapter.poll_status(session_id)

        if result.status == LoginStatus.WAITING:
            print(f"[{i+1}/60] ⏳ 等待扫码...")
        elif result.status == LoginStatus.SCANNED:
            print(f"[{i+1}/60] 👀 已扫码，请在手机上确认...")
        elif result.status == LoginStatus.CONFIRMED:
            print(f"[{i+1}/60] ✅ 登录成功!")
            print(f"\n用户信息:")
            print(f"   UserID: {result.user_info.user_id}")
            print(f"   用户名: {result.user_info.name}")
            print(f"   头像: {result.user_info.avatar}")
            print(f"\nCookie数量: {len(result.cookies)}")
            return True
        elif result.status == LoginStatus.EXPIRED:
            print(f"[{i+1}/60] ⏰ 二维码已过期")
            return False
        elif result.status == LoginStatus.FAILED:
            print(f"[{i+1}/60] ❌ 登录失败: {result.message}")
            return False

    print("\n❌ 超时: 60次轮询后仍未登录")
    return False


async def test_playwright_platform(platform_name: str):
    """测试需要Playwright的平台"""
    print("="*70)
    print(f"测试 {platform_name} 登录流程")
    print("="*70)

    # 选择适配器
    adapters = {
        "douyin": DouyinAdapter,
        "kuaishou": KuaishouAdapter,
        "xiaohongshu": XiaohongshuAdapter,
        "tencent": TencentAdapter
    }

    adapter_class = adapters.get(platform_name)
    if not adapter_class:
        print(f"❌ 未知平台: {platform_name}")
        return False

    adapter = adapter_class({"headless": False})  # 非无头模式方便调试

    # Step 1: 生成二维码
    print("\n[Step 1] 启动浏览器并生成二维码...")
    try:
        qr_data = await adapter.get_qrcode()
        print(f"✅ 二维码生成成功!")
        print(f"   Session ID: {qr_data.session_id[:12]}...")
        print(f"   QR URL: {qr_data.qr_url}")
        print(f"   QR Image: {qr_data.qr_image[:60]}...")
    except Exception as e:
        print(f"❌ 二维码生成失败: {e}")
        return False

    # Step 2: 轮询登录状态
    print(f"\n[Step 2] 请使用{platform_name}APP扫描二维码...")
    print("开始轮询登录状态 (每2秒一次，最多60次)...")

    session_id = qr_data.session_id
    for i in range(60):
        await asyncio.sleep(2)
        result = await adapter.poll_status(session_id)

        if result.status == LoginStatus.WAITING:
            print(f"[{i+1}/60] ⏳ 等待扫码...")
        elif result.status == LoginStatus.SCANNED:
            print(f"[{i+1}/60] 👀 已扫码，请在手机上确认...")
        elif result.status == LoginStatus.CONFIRMED:
            print(f"[{i+1}/60] ✅ 登录成功!")
            print(f"\n用户信息:")
            print(f"   UserID: {result.user_info.user_id}")
            print(f"   用户名: {result.user_info.name}")
            print(f"   头像: {result.user_info.avatar}")
            print(f"\nCookie数量: {len(result.cookies) if result.cookies else 0}")
            return True
        elif result.status == LoginStatus.EXPIRED:
            print(f"[{i+1}/60] ⏰ 二维码已过期")
            await adapter.cleanup_session(session_id)
            return False
        elif result.status == LoginStatus.FAILED:
            print(f"[{i+1}/60] ❌ 登录失败: {result.message}")
            await adapter.cleanup_session(session_id)
            return False

    print("\n❌ 超时: 60次轮询后仍未登录")
    await adapter.cleanup_session(session_id)
    return False


async def main():
    if len(sys.argv) < 2:
        print("使用方法: python test_platform_adapters.py <platform>")
        print("支持的平台: bilibili, douyin, kuaishou, xiaohongshu, tencent")
        sys.exit(1)

    platform = sys.argv[1].lower()

    if platform == "bilibili":
        success = await test_bilibili()
    elif platform in ["douyin", "kuaishou", "xiaohongshu", "tencent"]:
        success = await test_playwright_platform(platform)
    else:
        print(f"❌ 不支持的平台: {platform}")
        print("支持的平台: bilibili, douyin, kuaishou, xiaohongshu, tencent")
        sys.exit(1)

    if success:
        print("\n" + "="*70)
        print("✅ 测试通过!")
        print("="*70)
        sys.exit(0)
    else:
        print("\n" + "="*70)
        print("❌ 测试失败!")
        print("="*70)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
