"""测试 AI chat 接口"""
import requests
import json

# 测试用例 1: 使用 messages
print("测试用例 1: 使用 messages")
response1 = requests.post(
    "http://localhost:7000/api/v1/ai/chat",
    json={
        "messages": [{"role": "user", "content": "你好"}],
        "stream": False
    }
)
print(f"状态码: {response1.status_code}")
print(f"响应: {response1.text[:200]}\n")

# 测试用例 2: 使用 message + context
print("测试用例 2: 使用 message + context")
response2 = requests.post(
    "http://localhost:7000/api/v1/ai/chat",
    json={
        "message": "你好",
        "context": [],
        "stream": False
    }
)
print(f"状态码: {response2.status_code}")
print(f"响应: {response2.text[:200]}\n")

# 测试用例 3: 空 messages（会触发 400）
print("测试用例 3: 空 messages（应该触发 400）")
response3 = requests.post(
    "http://localhost:7000/api/v1/ai/chat",
    json={
        "messages": [],
        "stream": False
    }
)
print(f"状态码: {response3.status_code}")
print(f"响应: {response3.text[:200]}\n")

# 测试用例 4: 什么都不传（会触发 400）
print("测试用例 4: 什么都不传（应该触发 400）")
response4 = requests.post(
    "http://localhost:7000/api/v1/ai/chat",
    json={"stream": False}
)
print(f"状态码: {response4.status_code}")
print(f"响应: {response4.text[:200]}")
