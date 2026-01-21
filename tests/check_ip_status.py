
import requests
import time

# 待检测的 IPs
ips = [
    {"location": "广西南宁 (新)", "url": "http://222.139.246.13:20100"}
]

def check_proxy(name, proxy_url):
    print(f"正在检测 {name} ...")
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }
    try:
        start = time.time()
        # 访问百度检测
        resp = requests.get("https://www.baidu.com", proxies=proxies, timeout=10)
        elapsed = (time.time() - start) * 1000
        
        if resp.status_code == 200:
            print(f"✅ {name}: 存活！延迟: {elapsed:.0f}ms")
        else:
            print(f"⚠️ {name}: 连接成功但状态码异常 ({resp.status_code})")
    except Exception as e:
        print(f"❌ {name}: 连接失败 - {e}")

def main():
    print("=== IP 最终复核 ===")
    for ip in ips:
        check_proxy(ip["location"], ip["url"])
    print("=== 检测结束 ===")

if __name__ == "__main__":
    main()
