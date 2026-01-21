
import httpx
import asyncio

URL = "http://127.0.0.1:8000/api/v1/ip-pool/add"

PAYLOAD = {
    "ip": "60.188.69.217",
    "port": 20199,
    "protocol": "http",
    "username": "",
    "password": "",
    "ip_type": "dynamic_residential",
    "country": "CN",
    "region": "江苏省宿迁市",
    "city": "宿迁",
    "max_bindings": 50,
    "note": "青果_电信_动态",
    "provider": "qg.net"
}

async def main():
    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(URL, json=PAYLOAD)
            print(res.status_code)
            print(res.text)
        except Exception as e:
            print(e)

if __name__ == "__main__":
    asyncio.run(main())
