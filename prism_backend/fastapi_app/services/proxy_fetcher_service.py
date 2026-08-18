
import httpx
import re
import json
from typing import Optional, Dict, Any, List, Tuple
from fastapi_app.core.logger import logger

class ProxyFetcherService:
    """通用代理API提取服务"""
    
    # 匹配 IP:Port 的正则 (IPv4)
    # 粗略匹配: 数字.数字.数字.数字:数字
    IP_PORT_PATTERN = re.compile(r'((?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?):(\d{2,5})')

    def __init__(self):
        pass

    async def fetch_and_parse(self, api_url: str) -> Dict[str, Any]:
        """
        从任意 API URL 提取 IP
        """
        logger.info(f"正在从API提取IP: {api_url}")
        
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            try:
                resp = await client.get(api_url)
                content_text = resp.text
                
                # 1. 尝试解析 IP:Port
                # 扫描所有匹配项
                matches = self.IP_PORT_PATTERN.findall(content_text)
                
                if not matches:
                    # 如果没找到直接的 IP:Port，可能是 json 分开的 ip 和 port 字段
                    # 尝试解析 JSON
                    try:
                        data = resp.json()
                        ip, port = self._deep_find_ip_port(data)
                        if ip and port:
                            return {
                                "success": True,
                                "ip": ip,
                                "port": int(port),
                                "original_response": data,
                                "provider_guess": self._guess_provider(api_url)
                            }
                    except:
                        pass
                    
                    return {
                        "success": False, 
                        "message": f"未在响应中找到有效的 IP:Port 格式。响应内容前100字: {content_text[:100]}"
                    }

                # 2. 如果找到了匹配项，取第一个
                # findall 返回的是 tuple list? pattern 有分组。
                # 现在的 pattern: (ip_part)... : (port)
                # 这种复杂正则 findall 返回会比较乱，建议用 search 或者优化正则
                
                # 简化正则查找
                full_matches = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)', content_text)
                if full_matches:
                     ip, port = full_matches[0]
                     return {
                        "success": True,
                        "ip": ip,
                        "port": int(port),
                        "original_response": content_text[:200],
                        "provider_guess": self._guess_provider(api_url)
                    }
                
                return {"success": False, "message": "解析失败"}

            except Exception as e:
                logger.error(f"代理API请求失败: {e}")
                return {"success": False, "message": str(e)}

    def _deep_find_ip_port(self, data: Any) -> Tuple[Optional[str], Optional[int]]:
        """
        在 JSON 结构中递归查找看起来像 IP 和 Port 的字段
        """
        # 简单策略：查找 key 为 'ip'/'proxy'/'server' 和 'port' 的值
        # 这是一个启发式搜索
        if isinstance(data, dict):
            # 1. 直接检查当前层级
            ip = None
            port = None
            
            # 找 IP
            for k in ['ip', 'proxy_ip', 'server_ip', 'op']:
                if k in data and isinstance(data[k], str) and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', data[k]):
                    ip = data[k]
                    break
            
            # 找 Port
            for k in ['port', 'server_port']:
                if k in data:
                    try:
                        port = int(data[k])
                        break
                    except:
                        pass
            
            if ip and port:
                return ip, port

            # 2. 也是可能是 "server": "1.2.3.4:8888"
            for k, v in data.items():
                if isinstance(v, str):
                    m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)', v)
                    if m:
                        return m.group(1), int(m.group(2))

            # 3. 递归查找 list 或 dict
            for v in data.values():
                res_ip, res_port = self._deep_find_ip_port(v)
                if res_ip and res_port:
                    return res_ip, res_port

        elif isinstance(data, list):
            for item in data:
                res_ip, res_port = self._deep_find_ip_port(item)
                if res_ip and res_port:
                    return res_ip, res_port
                    
        return None, None

    def _guess_provider(self, url: str) -> str:
        if "qg.net" in url: return "qg.net"
        if "zhima" in url: return "zhima"
        if "kdlapi" in url: return "kuaidaili"
        return "custom_api"

# 单例
proxy_fetcher = ProxyFetcherService()
