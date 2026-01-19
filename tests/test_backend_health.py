"""
简单的矩阵API连通性测试
"""
import requests
import sys

def test_backend_health():
    """测试后端健康状态"""
    try:
        response = requests.get("http://localhost:8860/health", timeout=5)
        if response.status_code == 200:
            print("✓ 后端服务正常运行")
            print(f"  版本: {response.json().get('version')}")
            return True
        else:
            print(f"✗ 后端返回异常状态: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到后端服务 (http://localhost:8860)")
        print("  请确保后端已启动: python -m uvicorn fastapi_app.main:app --reload --port 8860")
        return False
    except Exception as e:
        print(f"✗ 检查后端失败: {e}")
        return False


def test_matrix_routes():
    """测试矩阵路由是否可用"""
    try:
        response = requests.get("http://localhost:8860/api/v1/matrix/stats", timeout=5)
        if response.status_code == 200:
            print("✓ 矩阵路由已加载")
            stats = response.json().get('data', {})
            print(f"  当前任务统计: {stats}")
            return True
        else:
            print(f"✗ 矩阵路由返回错误: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ 矩阵路由不可用（后端可能未重启）")
        return False
    except Exception as e:
        print(f"✗ 测试矩阵路由失败: {e}")
        return False


def test_publish_preset_fix():
    """测试发布预设修复"""
    try:
        # 测试保存预设（之前返回422错误）
        test_data = {
            "name": "测试预设",
            "platforms": ["xiaohongshu"],
            "accounts": ["test_account"],
            "materials": ["101"],
            "title": "测试标题",
            "description": "测试描述"
        }
        
        response = requests.post(
            "http://localhost:8860/api/publish-presets",
            json=test_data,
            timeout=5
        )
        
        if response.status_code == 200:
            print("✓ 发布预设保存修复成功（之前422错误）")
            return True
        else:
            print(f"✗ 发布预设保存失败: {response.status_code}")
            print(f"  响应: {response.text}")
            return False
    except Exception as e:
        print(f"✗ 测试发布预设失败: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("SynapseAutomation 后端连通性测试")
    print("=" * 60)
    print()
    
    # 1. 测试后端健康
    print("【1/3】测试后端服务...")
    backend_ok = test_backend_health()
    print()
    
    if not backend_ok:
        print("⚠ 后端服务未运行，跳过其他测试")
        sys.exit(1)
    
    # 2. 测试矩阵路由
    print("【2/3】测试矩阵路由...")
    matrix_ok = test_matrix_routes()
    print()
    
    # 3. 测试发布预设修复
    print("【3/3】测试发布预设修复...")
    preset_ok = test_publish_preset_fix()
    print()
    
    # 总结
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"后端服务:   {'✓' if backend_ok else '✗'}")
    print(f"矩阵路由:   {'✓' if matrix_ok else '✗ (需要重启后端)'}")
    print(f"预设修复:   {'✓' if preset_ok else '✗'}")
    
    if backend_ok and matrix_ok and preset_ok:
        print("\n✅ 所有测试通过！系统就绪。")
        sys.exit(0)
    else:
        print("\n⚠ 部分测试失败，请检查上述输出。")
        sys.exit(1)
