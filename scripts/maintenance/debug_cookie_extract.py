"""
调试Cookie提取
"""
import sys
import io
import json
from pathlib import Path

# 设置UTF-8编码输出（Windows兼容）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 测试Cookie提取
cookie_file = Path("syn_backend/cookiesFile/ffe0d3a1-cba7-11f0-87f6-00a747280720.json")

with open(cookie_file, 'r', encoding='utf-8') as f:
    cookie_data = json.load(f)

print("Cookie数据类型:", type(cookie_data))
print("Cookie键:", cookie_data.keys() if isinstance(cookie_data, dict) else "不是字典")

if 'cookies' in cookie_data:
    cookies_list = cookie_data['cookies']
    print(f"\ncookies数组长度: {len(cookies_list)}")

    # 查找userId
    for cookie in cookies_list:
        if cookie.get('name') == 'userId':
            print(f"\n找到userId!")
            print(f"  name: {cookie.get('name')}")
            print(f"  value: {cookie.get('value')}")
            print(f"  domain: {cookie.get('domain')}")
