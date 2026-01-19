"""
简单测试 - 直接调用 API 测试工具
"""
import requests
import json

print("=" * 70)
print("测试 OpenManus Agent API")
print("=" * 70)

# 测试 1: 简单的目标
print("\n[测试 1] 简单目标: 你好")
print("-" * 70)
try:
    response = requests.post(
        "http://localhost:7000/api/v1/agent/manus-run",
        json={"goal": "列出所有账号", "context": {}},
        timeout=120
    )
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"成功: {result.get('success')}")
        print(f"结果: {result.get('data', {}).get('result', 'N/A')[:200]}")
    else:
        print(f"错误: {response.text[:500]}")
except Exception as e:
    print(f"异常: {e}")

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
