"""
快速验证B站适配器 - 仅测试二维码生成
不需要真正扫码登录,只验证代码逻辑正确
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app_new.platforms import BilibiliAdapter, LoginStatus


async def quick_test_bilibili():
    """快速测试B站适配器"""
    print("="*70)
    print("B站适配器快速验证测试")
    print("="*70)

    adapter = BilibiliAdapter()

    # 测试1: 实例化
    print("\n[Test 1] 实例化适配器...")
    print(f"  Platform: {adapter.platform_name}")
    print(f"  Supports API Login: {await adapter.supports_api_login()}")
    assert adapter.platform_name == "bilibili", "Platform name incorrect"
    assert await adapter.supports_api_login() == True, "Should support API login"
    print("  PASS")

    # 测试2: 生成二维码
    print("\n[Test 2] 生成二维码...")
    try:
        qr_data = await adapter.get_qrcode()
        print(f"  Session ID: {qr_data.session_id[:16]}...")
        print(f"  QR URL: {qr_data.qr_url}")
        print(f"  QR Image Type: {qr_data.qr_image[:30]}...")
        print(f"  Expires In: {qr_data.expires_in}s")

        assert qr_data.session_id, "Session ID should not be empty"
        assert "bilibili.com" in qr_data.qr_url, "QR URL should contain bilibili.com"
        assert qr_data.qr_image.startswith("data:image/png;base64,") or qr_data.qr_image.startswith("http"), "QR image format incorrect"
        assert qr_data.expires_in == 180, "Expires time should be 180s"
        print("  PASS")

        session_id = qr_data.session_id

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试3: 轮询状态 (应该是waiting,因为没人扫码)
    print("\n[Test 3] 轮询登录状态 (应该返回waiting)...")
    try:
        result = await adapter.poll_status(session_id)
        print(f"  Status: {result.status}")
        print(f"  Message: {result.message}")

        assert result.status == LoginStatus.WAITING, f"Should be WAITING, got {result.status}"
        print("  PASS")

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 测试4: 清理会话 (B站无需清理,应该不报错)
    print("\n[Test 4] 清理会话...")
    try:
        await adapter.cleanup_session(session_id)
        print("  PASS")
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

    print("\n" + "="*70)
    print("ALL TESTS PASSED!")
    print("="*70)
    return True


if __name__ == "__main__":
    success = asyncio.run(quick_test_bilibili())
    sys.exit(0 if success else 1)
