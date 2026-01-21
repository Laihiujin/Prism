import requests
import json
import httpx
import asyncio

# 1. 代理提取链接 (去掉了地区限制)
PROXY_API_URL = "https://exclusive.proxy.qg.net/replace?key=880E8B24&num=1&isp=0&format=json&distinct=false&keep_alive=1440"

# 2. 本地后端添加IP接口
LOCAL_ADD_IP_URL = "http://127.0.0.1:8000/api/v1/ip-pool/add"

async def main():
    print(f"正在从青果网络提取IP: {PROXY_API_URL}")
    
    try:
        # 提取IP
        response = requests.get(PROXY_API_URL)
        print(f"提取结果: {response.text}")
        
        data = response.json()
        if data.get("code") == "SUCCESS" and data.get("data"):
            # 解析青果返回结构
            ips_list = data["data"].get("ips", [])
            if not ips_list:
                print("❌ 没有提取到IP列表")
                return

            proxy_item = ips_list[0]
            # server 字段格式为 IP:PORT
            server_str = proxy_item.get("server")
            if ":" in server_str:
                ip, port = server_str.split(":")
            else:
                ip = server_str
                port = 80 # fallback
                
            region = proxy_item.get("area", "")
            isp = proxy_item.get("isp", "")
            
            print(f"成功获取代理: {ip}:{port} (出口: {proxy_item.get('proxy_ip')})")
            
            # 构造添加请求
            payload = {
                "ip": ip,
                "port": int(port),
                "protocol": "http", # 青果默认通常是HTTP
                "username": "",     # 白名单模式通常无账号密码
                "password": "",
                "ip_type": "dynamic_residential",
                "country": "CN",
                "region": region,
                "city": region, # 简单处理
                "max_bindings": 50, # 动态IP建议绑定数
                "note": f"青果_{isp}_动态",
                "provider": "qg.net"
            }
            
            # 添加到本地系统
            print("正在添加到本地IP池...")
            async with httpx.AsyncClient() as client:
                res = await client.post(LOCAL_ADD_IP_URL, json=payload)
                if res.status_code == 200:
                    print("✅ 添加成功！")
                    print(res.json())
                else:
                    print(f"❌ 添加失败: {res.text}")
        else:
            print("❌ 提取IP失败，请检查白名单或额度")
            
    except Exception as e:
        print(f"❌ 发生错误: {e}")

if __name__ == "__main__":
    asyncio.run(main())
