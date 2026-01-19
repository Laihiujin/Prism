
import requests
import json
import httpx
import asyncio
import os
import uuid
from datetime import datetime

# 用户提供的原始链接 (含广州地区)
URL_GUANGZHOU = "https://exclusive.proxy.qg.net/replace?key=880E8B24&num=1&area=440100&isp=0&format=json&distinct=false&keep_alive=1440"
# 全局随机链接 (去掉area参数)
URL_GLOBAL = "https://exclusive.proxy.qg.net/replace?key=880E8B24&num=1&isp=0&format=json&distinct=false&keep_alive=1440"

# 本地配置
API_URL = "http://127.0.0.1:8000/api/v1/ip-pool/add"
JSON_FILE_PATH = "d:/SynapseAutomation/syn_backend/data/ip_pool.json"

def fetch_ip():
    print(f"尝试提取 IP (优先广州)...")
    try:
        res = requests.get(URL_GUANGZHOU, timeout=10)
        data = res.json()
        
        if data.get("code") == "NO_RESOURCE_FOUND":
            print("⚠️ 广州地区资源不足，切换为全国随机提取...")
            res = requests.get(URL_GLOBAL, timeout=10)
            data = res.json()
            
        if data.get("code") == "SUCCESS" and data.get("data"):
            ips_list = data["data"].get("ips", [])
            if ips_list:
                item = ips_list[0]
                server = item.get("server")
                if ":" in server:
                    ip, port = server.split(":")
                    return {
                        "ip": ip,
                        "port": int(port),
                        "region": item.get("area", "Unknown"),
                        "isp": item.get("isp", ""),
                        "raw": item
                    }
    except Exception as e:
        print(f"提取失败: {e}")
    return None

async def add_via_api(payload):
    print("尝试通过 API 添加...")
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(API_URL, json=payload, timeout=5)
            if res.status_code == 200:
                print("✅ API 添加成功！")
                return True
            else:
                print(f"❌ API 返回错误: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"❌ API 连接失败: {e}")
    return False

def add_via_file(payload):
    print("尝试直接写入 ip_pool.json ...")
    if not os.path.exists(JSON_FILE_PATH):
        print("❌ 文件不存在")
        return False
        
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 查重
        for item in data:
            if item['ip'] == payload['ip'] and item['port'] == payload['port']:
                print("⚠️ IP 已存在于文件中")
                return True
                
        # 构造完整记录
        new_record = {
            "id": str(uuid.uuid4()),
            "ip": payload['ip'],
            "port": payload['port'],
            "protocol": payload['protocol'],
            "username": payload.get('username'),
            "password": payload.get('password'),
            "ip_type": payload['ip_type'],
            "status": "available",
            "bound_account_ids": [],
            "max_bindings": payload['max_bindings'],
            "country": payload['country'],
            "region": payload['region'],
            "city": payload['city'],
            "isp": payload['note'].split('_')[1] if '_' in payload['note'] else "",
            "success_count": 0,
            "fail_count": 0,
            "total_used": 0,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "note": payload['note'],
            "provider": payload['provider']
        }
        
        data.append(new_record)
        
        with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print("✅ 文件写入成功！(请确保后端服务重载以生效)")
        return True
    except Exception as e:
        print(f"❌ 文件写入失败: {e}")
        return False

async def main():
    ip_data = fetch_ip()
    if not ip_data:
        print("❌ 未能提取到任何 IP")
        return

    print(f"🎯 提取到的 IP: {ip_data['ip']}:{ip_data['port']} ({ip_data['region']} {ip_data['isp']})")
    
    payload = {
        "ip": ip_data['ip'],
        "port": ip_data['port'],
        "protocol": "http",
        "username": "",
        "password": "",
        "ip_type": "dynamic_residential",
        "country": "CN",
        "region": ip_data['region'],
        "city": ip_data['region'][:2], # 简单取前两个字
        "max_bindings": 50,
        "note": f"青果_{ip_data['isp']}_动态",
        "provider": "qg.net"
    }
    
    # 优先 API，失败则写文件
    if not await add_via_api(payload):
        add_via_file(payload)

if __name__ == "__main__":
    asyncio.run(main())
