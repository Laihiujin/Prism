
import json
import os
from datetime import datetime
import uuid

FILE_PATH = "d:/SynapseAutomation/syn_backend/data/ip_pool.json"

proxy_data = {
    "id": str(uuid.uuid4()),
    "ip": "60.188.69.217",
    "port": 20199,
    "protocol": "http",
    "username": None,
    "password": None,
    "ip_type": "dynamic_residential",
    "status": "available",
    "bound_account_ids": [],
    "max_bindings": 50,
    "country": "CN",
    "region": "江苏省宿迁市",
    "city": "宿迁",
    "isp": "电信",
    "success_count": 0,
    "fail_count": 0,
    "total_used": 0,
    "last_used_at": None,
    "last_check_at": None,
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat(),
    "note": "青果_电信_动态",
    "provider": "qg.net"
}

def main():
    if not os.path.exists(FILE_PATH):
        print(f"File not found: {FILE_PATH}")
        data = []
    else:
        with open(FILE_PATH, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []

    # Check duplication
    for item in data:
        if item['ip'] == proxy_data['ip'] and item['port'] == proxy_data['port']:
            print("IP already exists.")
            return

    data.append(proxy_data)

    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("✅ Successfully added IP to JSON file directly.")

if __name__ == "__main__":
    main()
