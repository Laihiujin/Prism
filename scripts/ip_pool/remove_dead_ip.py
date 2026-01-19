
import json
import os

FILE_PATH = "d:/SynapseAutomation/syn_backend/data/ip_pool.json"

def main():
    if not os.path.exists(FILE_PATH):
        print("File not found.")
        return

    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter out the dead IP
    new_data = [item for item in data if item['ip'] != "60.188.69.217"]

    if len(new_data) < len(data):
        with open(FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)
        print("✅ 已删除失效的宿迁IP")
    else:
        print("未找到该IP")

if __name__ == "__main__":
    main()
