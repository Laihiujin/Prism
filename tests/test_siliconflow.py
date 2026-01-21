import os
import requests
import json

API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
BASE_URL = "https://api.siliconflow.cn/v1"

def test_list_models():
    print("Testing List Models...")
    url = f"{BASE_URL}/models"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Try with type and sub_type filters as used in the app
    params = {
        "type": "text",
        "sub_type": "chat"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            print(f"Success! Found {len(data.get('data', []))} models.")
            # Print first 5 models
            for model in data.get('data', [])[:5]:
                print(f" - {model['id']}")
            return True
        else:
            print(f"Failed to list models. Status: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Error listing models: {e}")
        return False

def test_chat_completion():
    print("\nTesting Chat Completion...")
    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Use a common model, e.g., Qwen/Qwen2.5-7B-Instruct
    # We'll pick one from the list if possible, otherwise default
    model = "Qwen/Qwen2.5-7B-Instruct" 
    
    data = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Hello, are you working?"}
        ],
        "stream": False
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            print("Success! Response:")
            print(result['choices'][0]['message']['content'])
            return True
        else:
            print(f"Failed to chat. Status: {response.status_code}")
            print(response.text)
            return False
    except Exception as e:
        print(f"Error chatting: {e}")
        return False

if __name__ == "__main__":
    if not API_KEY:
        print("Missing SILICONFLOW_API_KEY env var; skipping.")
        raise SystemExit(0)
    if test_list_models():
        test_chat_completion()
