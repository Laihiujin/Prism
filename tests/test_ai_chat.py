import requests
import json

# 测试 AI Chat 接口
url = "http://localhost:7000/api/v1/ai/chat"

# 测试非流式响应
payload = {
    "messages": [{"role": "user", "content": "生成一个5字以内的标题"}],
    "stream": False
}

print("发送请求...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")

try:
    response = requests.post(url, json=payload, timeout=30)
    print(f"\n状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    print(f"\n响应内容:")
    
    # 尝试解析 JSON
    try:
        data = response.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except:
        print("无法解析为 JSON，原始内容:")
        print(response.text)
        
except Exception as e:
    print(f"请求失败: {e}")
