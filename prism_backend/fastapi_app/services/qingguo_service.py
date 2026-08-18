
import httpx
from typing import Optional, Dict, Any, List
from fastapi_app.core.logger import logger
from urllib.parse import urlparse, parse_qs

class QingGuoService:
    """青果网络 API 服务"""
    
    BASE_URL = "https://exclusive.proxy.qg.net"
    
    def __init__(self):
        pass

    def parse_extraction_url(self, url: str) -> Dict[str, Any]:
        """解析用户提供的提取链接，提取关键参数"""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            
            return {
                "key": params.get("key", [""])[0],
                "area": params.get("area", [""])[0], # 可能为空
                "isp": params.get("isp", ["0"])[0],
                "num": params.get("num", ["1"])[0],
                "keep_alive": params.get("keep_alive", ["1440"])[0]
            }
        except Exception as e:
            logger.error(f"解析青果链接失败: {e}")
            return {}

    async def fetch_new_ip(self, key: str, area: str = "", isp: str = "0") -> Dict[str, Any]:
        """
        提取新 IP (replace)
        https://exclusive.proxy.qg.net/replace?key=...
        """
        # 如果指定地区失败，自动重试全国随机
        url = f"{self.BASE_URL}/replace"
        params = {
            "key": key,
            "num": 1,
            "area": area,
            "isp": isp,
            "format": "json",
            "distinct": "false",
            "keep_alive": 1440
        }
        
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                # 第一次尝试 (带地区)
                logger.info(f"青果提取IP: params={params}")
                resp = await client.get(url, params=params)
                data = resp.json()
                
                # 如果资源不足且指定了地区，尝试去除地区重试
                if data.get("code") == "NO_RESOURCE_FOUND" and area:
                    logger.warning("指定地区资源不足，尝试全国随机...")
                    params.pop("area")
                    resp = await client.get(url, params=params)
                    data = resp.json()

                if data.get("code") == "SUCCESS":
                    # 解析结果
                    # data结构: {"code":"SUCCESS", "data": {"ips": [{"proxy_ip":..., "server":...}]}}
                    ips = data.get("data", {}).get("ips", [])
                    if ips:
                        item = ips[0]
                        server = item.get("server") # 60.18.x.x:port
                        if server and ":" in server:
                            ip, port = server.split(":")
                            return {
                                "success": True,
                                "ip": ip,
                                "port": int(port),
                                "region": item.get("area", ""),
                                "isp": item.get("isp", ""),
                                "full_data": item
                            }
                
                return {
                    "success": False, 
                    "message": data.get("message", "Unknown Error"),
                    "code": data.get("code")
                }
                
            except Exception as e:
                logger.error(f"青果API请求失败: {e}")
                return {"success": False, "message": str(e)}

    async def query_active_ips(self, key: str) -> List[Dict[str, Any]]:
        """
        查询当前在用 IP (get)
        https://exclusive.proxy.qg.net/get?key=...
        """
        url = f"{self.BASE_URL}/get"
        params = {"key": key, "format": "json"}
        
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(url, params=params)
                data = resp.json()
                if data.get("code") == "SUCCESS":
                    return data.get("data", {}).get("ips", [])
                return []
            except Exception as e:
                logger.error(f"查询青果IP失败: {e}")
                return []

    async def release_ip(self, key: str, ip: str = "") -> bool:
        """
        释放 IP (delete)
        https://exclusive.proxy.qg.net/delete?key=...
        如果 ip 为空，可能释放所有？文档未明确，通常需要 release 全部或者指定。
        根据接口: /delete?key=xxx 应该是释放当前通道的 IP。
        """
        url = f"{self.BASE_URL}/delete"
        params = {"key": key}
        # 如果API支持指定IP释放: params["ip"] = ip
        
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(url, params=params)
                data = resp.json()
                logger.info(f"释放青果IP结果: {data}")
                return data.get("code") == "SUCCESS"
            except Exception as e:
                logger.error(f"释放青果IP失败: {e}")
                return False

# 单例
qingguo_service = QingGuoService()
