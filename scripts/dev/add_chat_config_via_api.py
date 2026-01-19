"""通过 API 添加 Chat 配置"""
import requests
import json

# ⚠️ 请替换为你的实际 API Key
API_KEY = "sk-your-siliconflow-api-key-here"
BASE_URL = "https://api.siliconflow.cn/v1"
MODEL_NAME = "deepseek-ai/DeepSeek-V3"

# 1. 测试连接
print("📡 正在测试 API 连接...")
test_response = requests.post(
    "http://localhost:7000/api/v1/ai/test-connection",
    json={
        "service_type": "chat",
        "provider": "openai_compatible",
        "api_key": API_KEY,
        "base_url": BASE_URL,
        "model_name": MODEL_NAME
    }
)

print(f"测试结果: {test_response.status_code}")
if test_response.status_code == 200:
    result = test_response.json()
    print(f"✅ {result.get('message', '连接成功')}")
else:
    print(f"❌ 测试失败: {test_response.text}")
    print("\n⚠️ 请检查 API Key 是否正确，然后重试")
    exit(1)

# 2. 保存配置
print("\n💾 正在保存配置...")
save_response = requests.post(
    "http://localhost:7000/api/v1/ai/model-configs",
    json={
        "service_type": "chat",
        "provider": "openai_compatible",
        "api_key": API_KEY,
        "base_url": BASE_URL,
        "model_name": MODEL_NAME,
        "extra_config": {},
        "is_active": True
    }
)

print(f"保存结果: {save_response.status_code}")
if save_response.status_code == 200:
    result = save_response.json()
    print(f"✅ {result.get('message', '配置保存成功')}")
else:
    print(f"❌ 保存失败: {save_response.text}")
    exit(1)

# 3. 验证配置
print("\n🔍 验证配置...")
verify_response = requests.get("http://localhost:7000/api/v1/ai/model-configs/chat")
if verify_response.status_code == 200:
    config = verify_response.json()
    if config.get('data'):
        data = config['data']
        print(f"✅ 配置已保存:")
        print(f"   - Service Type: {data.get('service_type')}")
        print(f"   - Provider: {data.get('provider')}")
        print(f"   - Model: {data.get('model_name')}")
        print(f"   - Active: {bool(data.get('is_active'))}")
    else:
        print("⚠️ 未找到配置")
else:
    print(f"❌ 验证失败: {verify_response.text}")

# 4. 测试 Chat 接口
print("\n🧪 测试 Chat 接口...")
chat_response = requests.post(
    "http://localhost:7000/api/v1/ai/chat",
    json={
        "messages": [{"role": "user", "content": "你好，请回复'测试成功'"}],
        "stream": False
    }
)

print(f"Chat 测试结果: {chat_response.status_code}")
if chat_response.status_code == 200:
    result = chat_response.json()
    print(f"✅ AI 回复: {result.get('content', '')[:100]}")
    print("\n🎉 所有配置完成！Chat 服务已可用！")
else:
    print(f"❌ Chat 测试失败: {chat_response.text}")
    print("\n💡 提示: 如果是 400 错误，可能需要重启后端服务")
