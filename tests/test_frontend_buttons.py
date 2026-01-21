"""
快速测试前端按钮连接的后端路由
"""
import requests

BASE_URL = "http://localhost:7000"

tests = [
    ("AI 模型配置列表", "GET", f"{BASE_URL}/api/v1/ai/model-configs"),
    ("AI 模型配置详情", "GET", f"{BASE_URL}/api/v1/ai/model-configs/chat"),
    ("AI 聊天（非流式）", "POST", f"{BASE_URL}/api/v1/ai/chat", {
        "messages": [{"role": "user", "content": "测试"}],
        "stream": False
    }),
    ("AI 封面生成", "POST", f"{BASE_URL}/api/v1/ai/generate-cover", {
        "prompt": "测试封面",
        "aspect_ratio": "3:4"
    }),
]

print("=" * 70)
print("前端按钮路由测试")
print("=" * 70)

for name, method, url, *data in tests:
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        else:
            response = requests.post(url, json=data[0] if data else None, timeout=10)
        
        status = "✅" if response.status_code in [200, 201] else "❌"
        print(f"\n{status} {name}")
        print(f"   URL: {url}")
        print(f"   状态码: {response.status_code}")
        
        if response.status_code not in [200, 201]:
            print(f"   错误: {response.text[:200]}")
        else:
            # 检查是否是 JSON
            try:
                data = response.json()
                print(f"   响应: {str(data)[:100]}...")
            except:
                print(f"   响应: {response.text[:100]}...")
                
    except Exception as e:
        print(f"\n❌ {name}")
        print(f"   错误: {e}")

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
print("\n如果看到 ❌，说明该路由不可用，需要：")
print("1. 确认后端已重启")
print("2. 检查路由是否正确注册")
print("3. 检查数据库配置是否存在")
