"""
IP池管理服务
"""
import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime
import random
import asyncio
import httpx

from fastapi_app.models.ip_pool import (
    ProxyIP, IPStatus, IPSourceType, AddIPRequest, IPStatsResponse
)
from fastapi_app.core.logger import logger


class IPPoolService:
    """IP池管理服务"""
    
    def __init__(self):
        self.ip_pool_file = Path("data/ip_pool.json")
        self.ips: Dict[str, ProxyIP] = {}
        self._load_ips()
    
    def _load_ips(self):
        """从文件加载IP池"""
        if self.ip_pool_file.exists():
            try:
                with open(self.ip_pool_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        ip = ProxyIP(**item)
                        self.ips[ip.id] = ip
                logger.info(f"已加载 {len(self.ips)} 个代理IP")
            except Exception as e:
                logger.error(f"加载IP池失败: {e}")
        logger.info("IP池重载完成")  # 触发重载监测
    
    def _save_ips(self):
        """保存IP池到文件"""
        self.ip_pool_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = [ip.model_dump(mode="json") for ip in self.ips.values()]
            with open(self.ip_pool_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存IP池失败: {e}")
    
    def add_ip(self, request: AddIPRequest) -> ProxyIP:
        """添加IP到池中"""
        ip = ProxyIP(
            ip=request.ip,
            port=request.port,
            protocol=request.protocol,
            username=request.username,
            password=request.password,
            ip_type=request.ip_type,
            country=request.country,
            region=request.region,
            city=request.city,
            isp=request.isp,
            max_bindings=request.max_bindings,
            note=request.note,
            provider=request.provider
        )
        
        self.ips[ip.id] = ip
        self._save_ips()
        logger.info(f"添加IP: {ip.ip}:{ip.port}")
        return ip
    
    def get_ip(self, ip_id: str) -> Optional[ProxyIP]:
        """获取单个IP"""
        return self.ips.get(ip_id)
    
    def list_ips(
        self,
        status: Optional[IPStatus] = None,
        ip_type: Optional[IPSourceType] = None,
        region: Optional[str] = None
    ) -> List[ProxyIP]:
        """获取IP列表"""
        ips = list(self.ips.values())
        
        if status:
            ips = [ip for ip in ips if ip.status == status]
        if ip_type:
            ips = [ip for ip in ips if ip.ip_type == ip_type]
        if region:
            ips = [ip for ip in ips if ip.region == region]
        
        return ips
    
    def delete_ip(self, ip_id: str) -> bool:
        """删除IP"""
        if ip_id in self.ips:
            ip = self.ips[ip_id]
            del self.ips[ip_id]
            self._save_ips()
            logger.info(f"删除IP: {ip.ip}:{ip.port}")
            return True
        return False
    
    def update_ip_status(self, ip_id: str, status: IPStatus):
        """更新IP状态"""
        if ip_id in self.ips:
            self.ips[ip_id].status = status
            self.ips[ip_id].updated_at = datetime.now()
            self._save_ips()
    
    def bind_account_to_ip(self, ip_id: str, account_id: str) -> bool:
        """绑定账号到IP"""
        ip = self.ips.get(ip_id)
        if not ip:
            raise ValueError(f"IP {ip_id} 不存在")
        
        # 检查是否已达到绑定上限
        if len(ip.bound_account_ids) >= ip.max_bindings:
            raise ValueError(f"IP已达到绑定上限 ({ip.max_bindings})")
        
        # 先解绑该账号在其他IP的绑定
        self.unbind_account(account_id)
        
        # 添加绑定
        if account_id not in ip.bound_account_ids:
            ip.bound_account_ids.append(account_id)
            ip.updated_at = datetime.now()
            self._save_ips()
            logger.info(f"绑定账号 {account_id} 到IP {ip.ip}:{ip.port}")
        
        return True
    
    def unbind_account(self, account_id: str) -> bool:
        """解绑账号"""
        for ip in self.ips.values():
            if account_id in ip.bound_account_ids:
                ip.bound_account_ids.remove(account_id)
                ip.updated_at = datetime.now()
                self._save_ips()
                logger.info(f"解绑账号 {account_id}")
                return True
        return False
    
    def get_ip_for_account(self, account_id: str) -> Optional[ProxyIP]:
        """获取账号绑定的IP"""
        for ip in self.ips.values():
            if account_id in ip.bound_account_ids:
                return ip
        return None
    
    def auto_bind_account(
        self,
        account_id: str,
        prefer_region: Optional[str] = None
    ) -> Optional[ProxyIP]:
        """自动为账号分配IP"""
        # 1. 优先选择同地区的可用IP
        candidates = []
        
        if prefer_region:
            candidates = [
                ip for ip in self.ips.values()
                if ip.region == prefer_region
                and len(ip.bound_account_ids) < ip.max_bindings
                and ip.status == IPStatus.AVAILABLE
            ]
        
        # 2. 如果没有同地区的，选择任意可用IP
        if not candidates:
            candidates = [
                ip for ip in self.ips.values()
                if len(ip.bound_account_ids) < ip.max_bindings
                and ip.status == IPStatus.AVAILABLE
            ]
        
        if not candidates:
            logger.warning(f"没有可用IP为账号 {account_id} 分配")
            return None
        
        # 选择绑定数最少的IP
        best_ip = min(candidates, key=lambda x: len(x.bound_account_ids))
        self.bind_account_to_ip(best_ip.id, account_id)
        return best_ip
    
    async def check_ip_health(self, ip: ProxyIP) -> bool:
        """检测IP健康状态"""
        try:
            proxy_url = ip.to_proxy_url()
            client_kwargs = {"timeout": 10.0}
            
            # 只有当proxy_url存在时才设置代理
            if proxy_url:
                client_kwargs["proxy"] = proxy_url
            
            async with httpx.AsyncClient(**client_kwargs) as client:
                # 测试请求到百度 (国内更稳定)
                try:
                    response = await client.get("https://www.baidu.com")
                    ip.last_check_at = datetime.now()
                    
                    if 200 <= response.status_code < 400:
                        logger.info(f"IP {ip.ip}:{ip.port} 健康检测通过")
                        return True
                    else:
                        logger.warning(f"IP {ip.ip}:{ip.port} 返回状态码 {response.status_code}")
                        return False
                except Exception as e:
                    # 如果百度失败，尝试备用地址 (myip)
                    try:
                        response = await client.get("https://myip.ipip.net")
                        if response.status_code == 200:
                            return True
                    except:
                        pass
                    raise e
                    
        except Exception as e:
            logger.error(f"IP {ip.ip}:{ip.port} 健康检测失败: {e}")
            return False
    
    async def batch_check_health(self) -> Dict[str, bool]:
        """批量检测IP健康状态"""
        results = {}
        tasks = []
        
        for ip_id, ip in self.ips.items():
            task = self.check_ip_health(ip)
            tasks.append((ip_id, task))
        
        for ip_id, task in tasks:
            healthy = await task
            results[ip_id] = healthy
            
            # 更新状态
            if healthy:
                self.update_ip_status(ip_id, IPStatus.AVAILABLE)
            else:
                self.update_ip_status(ip_id, IPStatus.FAILED)
        
        return results
    
    def record_usage(self, ip_id: str, success: bool):
        """记录IP使用结果"""
        if ip_id in self.ips:
            ip = self.ips[ip_id]
            ip.total_used += 1
            
            if success:
                ip.success_count += 1
            else:
                ip.fail_count += 1
            
            ip.last_used_at = datetime.now()
            self._save_ips()
    
    def get_statistics(self) -> IPStatsResponse:
        """获取IP池统计"""
        total = len(self.ips)
        available = sum(1 for ip in self.ips.values() if ip.status == IPStatus.AVAILABLE)
        in_use = sum(1 for ip in self.ips.values() if ip.status == IPStatus.IN_USE)
        failed = sum(1 for ip in self.ips.values() if ip.status == IPStatus.FAILED)
        banned = sum(1 for ip in self.ips.values() if ip.status == IPStatus.BANNED)
        
        total_bindings = sum(len(ip.bound_account_ids) for ip in self.ips.values())
        
        # 计算平均成功率
        success_rates = [ip.success_rate for ip in self.ips.values() if ip.total_used > 0]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0
        
        return IPStatsResponse(
            total=total,
            available=available,
            in_use=in_use,
            failed=failed,
            banned=banned,
            total_bindings=total_bindings,
            avg_success_rate=round(avg_success_rate, 2)
        )


# 全局单例
_ip_pool_service: Optional[IPPoolService] = None


def get_ip_pool_service() -> IPPoolService:
    """获取IP池服务单例"""
    global _ip_pool_service
    if _ip_pool_service is None:
        _ip_pool_service = IPPoolService()
    return _ip_pool_service
