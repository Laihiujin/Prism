import requests
import json
import sys

def test_chat_stream():
    url = "http://localhost:7000/api/v1/ai/chat"
    
    # Vercel AI SDK format
    payload = {
        "messages": [
            {"role": "user", "content": "Hello, are you working?"}
        ]
    }
    
    print(f"Testing {url} with payload: {payload}")
    
    try:
        with requests.post(url, json=payload, stream=True) as response:
            if response.status_code == 200:
                print("Connection successful. Receiving stream:")
                for chunk in response.iter_content(chunk_size=None):
                    if chunk:
                        print(chunk.decode('utf-8'), end='', flush=True)
                print("\nStream finished.")
            else:
                print(f"Error: {response.status_code}")
                print(response.text)
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_chat_stream()
