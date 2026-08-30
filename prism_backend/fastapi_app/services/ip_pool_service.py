"""
IP池管理服务 → Network Manager (代理管理 + 持久绑定)
"""
import json
import time
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


def _get_cookie_manager():
    """延迟导入 CookieManager，避免循环依赖/启动时序问题。"""
    try:
        from myUtils.cookie_manager import cookie_manager
        return cookie_manager
    except Exception as e:
        logger.warning(f"CookieManager 不可用，绑定仅落 JSON: {e}")
        return None


class IPPoolService:
    """
    Network Manager — 代理管理与账号-代理持久绑定。
    
    核心原则：
    - 绑定是持久的：账号一旦绑定代理，除非显式解绑，否则不自动换。
    - 出口 IP 检测：健康检测时通过代理请求外部 API 获取真实出口 IP/ASN。
    - 国内外统一抽象：HTTP/SOCKS5 是基础层，3Proxy/gluetun/sing-box 作为 provider 以后插。
    """
    
    def __init__(self):
        self.ip_pool_file = Path("data/ip_pool.json")
        self.ips: Dict[str, ProxyIP] = {}
        self._load_ips()
    
    def _load_ips(self):
        """从文件加载代理列表"""
        if self.ip_pool_file.exists():
            try:
                with open(self.ip_pool_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        # 兼容旧数据（未含 name/exit_ip/asn/latency_ms 字段）
                        if "name" not in item:
                            item["name"] = f"proxy-{item.get('id', '?')[:8]}"
                        if "exit_ip" not in item:
                            item["exit_ip"] = None
                        if "asn" not in item:
                            item["asn"] = None
                        if "latency_ms" not in item:
                            item["latency_ms"] = None
                        if "max_bindings" not in item:
                            item["max_bindings"] = 1
                        ip = ProxyIP(**item)
                        self.ips[ip.id] = ip
                logger.info(f"已加载 {len(self.ips)} 个代理")
            except Exception as e:
                logger.error(f"加载代理列表失败: {e}")
    
    def _save_ips(self):
        """保存代理列表到文件"""
        self.ip_pool_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = [ip.model_dump(mode="json") for ip in self.ips.values()]
            with open(self.ip_pool_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存代理列表失败: {e}")
    
    # ─── CRUD ────────────────────────────────────────────────
    
    def add_ip(self, request: AddIPRequest) -> ProxyIP:
        """添加代理到池中"""
        ip = ProxyIP(
            name=request.name or f"proxy-{len(self.ips) + 1:04d}",
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
            asn=request.asn,
            max_bindings=request.max_bindings,
            note=request.note,
            provider=request.provider
        )
        
        self.ips[ip.id] = ip
        self._save_ips()
        logger.info(f"添加代理: {ip.name} ({ip.ip}:{ip.port})")
        return ip
    
    def get_ip(self, ip_id: str) -> Optional[ProxyIP]:
        """获取单个代理"""
        return self.ips.get(ip_id)
    
    def list_ips(
        self,
        status: Optional[IPStatus] = None,
        ip_type: Optional[IPSourceType] = None,
        region: Optional[str] = None
    ) -> List[ProxyIP]:
        """获取代理列表"""
        ips = list(self.ips.values())
        
        if status:
            ips = [ip for ip in ips if ip.status == status]
        if ip_type:
            ips = [ip for ip in ips if ip.ip_type == ip_type]
        if region:
            ips = [ip for ip in ips if ip.region == region]
        
        return ips
    
    def delete_ip(self, ip_id: str) -> bool:
        """删除代理"""
        if ip_id in self.ips:
            ip = self.ips[ip_id]
            del self.ips[ip_id]
            self._save_ips()
            logger.info(f"删除代理: {ip.name} ({ip.ip}:{ip.port})")
            return True
        return False
    
    def update_ip_status(self, ip_id: str, status: IPStatus):
        """更新代理状态"""
        if ip_id in self.ips:
            self.ips[ip_id].status = status
            self.ips[ip_id].updated_at = datetime.now()
            self._save_ips()
    
    def update_ip(self, ip_id: str, **kwargs) -> Optional[ProxyIP]:
        """更新代理字段"""
        ip = self.ips.get(ip_id)
        if not ip:
            return None
        for k, v in kwargs.items():
            if hasattr(ip, k) and v is not None:
                setattr(ip, k, v)
        ip.updated_at = datetime.now()
        self._save_ips()
        return ip
    
    # ─── 持久绑定 ────────────────────────────────────────────
    
    def bind_account_to_ip(self, ip_id: str, account_id: str) -> bool:
        """持久绑定账号到代理（账号→固定代理，1:1 绑定）"""
        ip = self.ips.get(ip_id)
        if not ip:
            raise ValueError(f"代理 {ip_id} 不存在")
        
        # 检查是否启用
        if not ip.is_enabled:
            raise ValueError(f"代理 {ip.name or ip_id} 已被禁用")
        
        # 检查状态（offline 不允许新绑定，degraded 允许）
        if ip.status in (IPStatus.FAILED, IPStatus.BANNED, IPStatus.AUTH_FAILED):
            raise ValueError(f"代理 {ip.name or ip_id} 当前状态 {ip.status}，不可绑定")
        
        # 检查绑定上限
        if len(ip.bound_account_ids) >= ip.max_bindings:
            raise ValueError(f"代理已达到绑定上限 ({ip.max_bindings})")
        
        # 先解绑该账号在其他代理的绑定（确保 1:1 持久）
        self.unbind_account(account_id)
        
        # 添加绑定
        if account_id not in ip.bound_account_ids:
            ip.bound_account_ids.append(account_id)
            ip.updated_at = datetime.now()
            ip.status = IPStatus.IN_USE
            self._save_ips()
            logger.info(f"绑定账号 {account_id} → 代理 {ip.name} ({ip.ip}:{ip.port})")

        # ── 权威绑定落账号表（sticky）──
        cm = _get_cookie_manager()
        if cm:
            try:
                cm.set_account_binding(account_id, proxy_id=ip_id)
            except Exception as e:
                logger.warning(f"同步账号表 proxy_id 失败 {account_id}: {e}")

        return True
    
    def unbind_account(self, account_id: str) -> bool:
        """解绑账号（持久绑定解除）"""
        for ip in self.ips.values():
            if account_id in ip.bound_account_ids:
                ip.bound_account_ids.remove(account_id)
                ip.updated_at = datetime.now()
                # 如果没有绑定账号了，恢复可用状态
                if not ip.bound_account_ids:
                    ip.status = IPStatus.AVAILABLE
                self._save_ips()
                logger.info(f"解绑账号 {account_id} ← 代理 {ip.name}")
                # ── 权威解绑落账号表 ──
                cm = _get_cookie_manager()
                if cm:
                    try:
                        cm.set_account_binding(account_id, clear_proxy=True)
                    except Exception as e:
                        logger.warning(f"同步账号表清除 proxy_id 失败 {account_id}: {e}")
                return True
        return False
    
    def get_ip_for_account(self, account_id: str) -> Optional[ProxyIP]:
        """获取账号绑定的代理（持久绑定查询）。
        
        权威来源 = 账号表 proxy_id（sticky）；JSON bound_account_ids 为反向索引/兜底。
        """
        # 1. 优先读账号表权威绑定
        cm = _get_cookie_manager()
        if cm:
            try:
                binding = cm.get_account_binding(account_id)
                if binding and binding.get("proxy_id"):
                    ip = self.ips.get(binding["proxy_id"])
                    if ip:
                        return ip
            except Exception as e:
                logger.debug(f"读账号表绑定失败 {account_id}: {e}")

        # 2. 兜底：JSON 反向索引（兼容未迁移旧数据）
        for ip in self.ips.values():
            if account_id in ip.bound_account_ids:
                return ip
        return None
    
    def auto_bind_account(
        self,
        account_id: str,
        prefer_region: Optional[str] = None
    ) -> Optional[ProxyIP]:
        """
        为账号自动分配代理（首次绑定用）。
        
        【核心改进】持久绑定语义：如果账号已有绑定，直接返回现有代理，不换绑。
        """
        # 1. 已有绑定 → 返回现有（不换绑）
        existing = self.get_ip_for_account(account_id)
        if existing:
            logger.info(f"账号 {account_id} 已有绑定 → 代理 {existing.name}，不换绑")
            return existing
        
        # 2. 无绑定 → 分配可用代理
        candidates = []
        if prefer_region:
            candidates = [
                ip for ip in self.ips.values()
                if ip.region == prefer_region
                and len(ip.bound_account_ids) < ip.max_bindings
                and ip.status in (IPStatus.AVAILABLE, IPStatus.IN_USE)
            ]
        
        if not candidates:
            candidates = [
                ip for ip in self.ips.values()
                if len(ip.bound_account_ids) < ip.max_bindings
                and ip.status in (IPStatus.AVAILABLE, IPStatus.IN_USE)
            ]
        
        if not candidates:
            logger.warning(f"没有可用代理为账号 {account_id} 分配")
            return None
        
        # 选择绑定数最少的代理
        best_ip = min(candidates, key=lambda x: len(x.bound_account_ids))
        self.bind_account_to_ip(best_ip.id, account_id)
        logger.info(f"首次分配账号 {account_id} → 代理 {best_ip.name}")
        return best_ip
    
    # ─── 健康检测 (v2: 出口IP + ASN + 延迟) ─────────────────
    
    async def check_ip_health(self, ip: ProxyIP) -> bool:
        """
        检测代理健康状态（v2 + 状态机）。
        
        通过代理访问外部 API 检测：
        - 连通性 / 认证
        - 出口 IP（真实出口）+ 漂移检测
        - ASN + 地区
        - 延迟 (ms)
        
        状态机（不因单次失败换绑）：
        连续 1 次失败 → degraded
        连续 >=3 次失败 → offline (failed)
        成功 → 重置计数，回 available/in_use
        """
        try:
            proxy_url = ip.to_proxy_url()
            client_kwargs = {"timeout": 15.0}
            
            if proxy_url:
                client_kwargs["proxy"] = proxy_url
            
            start = time.monotonic()
            
            async with httpx.AsyncClient(**client_kwargs) as client:
                # 用 ip-api.com 检测出口 IP + ASN + 地区
                try:
                    resp = await client.get("http://ip-api.com/json/?fields=query,as,org,country,regionName,city,isp")
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    ip.latency_ms = elapsed_ms
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        new_exit_ip = data.get("query")
                        
                        # ── 出口IP漂移检测 ──
                        if ip.exit_ip and new_exit_ip and ip.exit_ip != new_exit_ip:
                            ip.previous_exit_ip = ip.exit_ip
                            ip.exit_ip_changed_at = datetime.now()
                            logger.warning(
                                f"代理 {ip.name} 出口IP漂移: {ip.exit_ip} → {new_exit_ip} "
                                f"(sticky 绑定不自动换，需管理员确认)"
                            )
                        elif ip.previous_exit_ip == new_exit_ip:
                            ip.previous_exit_ip = None  # 回到稳定
                        
                        ip.exit_ip = new_exit_ip
                        asn_raw = data.get("as", "")
                        # ASN 格式通常是 "AS12345 Provider Name"
                        if asn_raw:
                            parts = asn_raw.split(" ", 1)
                            ip.asn = parts[0] if parts[0].startswith("AS") else asn_raw
                            if len(parts) > 1:
                                ip.isp = parts[1]
                        if data.get("country"):
                            ip.country = data.get("country", ip.country)
                        if data.get("regionName"):
                            ip.region = data.get("regionName", ip.region)
                        if data.get("city"):
                            ip.city = data.get("city", ip.city)
                        
                        ip.last_check_at = datetime.now()
                        ip.last_success_at = datetime.now()
                        ip.consecutive_failures = 0  # 成功重置
                        # 恢复状态（保留 in_use）
                        ip.status = ip.status if ip.status == IPStatus.IN_USE else IPStatus.AVAILABLE
                        ip.updated_at = datetime.now()
                        self._save_ips()
                        logger.info(f"代理 {ip.name} 健康: {ip.exit_ip} ({ip.asn}) {elapsed_ms}ms")
                        return True
                    else:
                        logger.warning(f"ip-api 返回 {resp.status_code}")
                except Exception as e:
                    logger.warning(f"ip-api 失败: {e}")
                
                # 回退：只检测连通性（出口IP沿用入口）
                fallback_resp = await client.get("https://www.baidu.com", timeout=10.0)
                elapsed_ms = int((time.monotonic() - start) * 1000)
                ip.latency_ms = elapsed_ms
                ip.last_check_at = datetime.now()
                ip.last_success_at = datetime.now()
                ip.consecutive_failures = 0
                ip.status = ip.status if ip.status == IPStatus.IN_USE else IPStatus.AVAILABLE
                ip.updated_at = datetime.now()
                self._save_ips()
                return 200 <= fallback_resp.status_code < 400
                    
        except Exception as e:
            # ── 失败状态机 ──
            ip.consecutive_failures += 1
            ip.fail_count += 1
            ip.last_failure_at = datetime.now()
            ip.last_check_at = datetime.now()
            
            # 认证失败（407/401 等）
            err_msg = str(e).lower()
            if "407" in err_msg or "proxy authentication" in err_msg or "401" in err_msg:
                ip.status = IPStatus.AUTH_FAILED
            elif ip.consecutive_failures >= 3:
                ip.status = IPStatus.FAILED  # offline
            else:
                ip.status = IPStatus.DEGRADED  # 连续1次失败 → degraded，不换绑
            
            ip.updated_at = datetime.now()
            self._save_ips()
            logger.error(
                f"代理 {ip.name} 健康检测失败 ({ip.consecutive_failures} 连败) → {ip.status}: {e}"
            )
            return False
    
    async def batch_check_health(self) -> Dict[str, bool]:
        """批量检测所有代理健康状态（尊重状态机，不强制覆盖状态）"""
        results = {}
        tasks = []
        
        for ip_id, ip in self.ips.items():
            task = self.check_ip_health(ip)
            tasks.append((ip_id, task))
        
        for ip_id, task in tasks:
            try:
                healthy = await task
                results[ip_id] = healthy
                # 状态已由 check_ip_health 状态机维护，这里不再强制覆盖
                if healthy:
                    ip = self.ips.get(ip_id)
                    if ip and ip.status not in (IPStatus.IN_USE, IPStatus.AVAILABLE):
                        ip.status = IPStatus.AVAILABLE
                        self._save_ips()
            except Exception as e:
                logger.error(f"批量检测: {ip_id} 失败 {e}")
                results[ip_id] = False
        
        return results
    
    # ─── 批量导入导出 ────────────────────────────────────────
    
    def import_ips(self, items: List[AddIPRequest]) -> List[ProxyIP]:
        """批量导入代理"""
        added = []
        for req in items:
            ip = self.add_ip(req)
            added.append(ip)
        logger.info(f"批量导入 {len(added)} 个代理")
        return added
    
    def export_ips(self) -> List[Dict]:
        """导出所有代理"""
        return [ip.model_dump(mode="json") for ip in self.ips.values()]
    
    # ─── 使用统计 ────────────────────────────────────────────
    
    def record_usage(self, ip_id: str, success: bool):
        """记录代理使用结果"""
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
        """获取代理统计"""
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
    """获取代理管理服务单例"""
    global _ip_pool_service
    if _ip_pool_service is None:
        _ip_pool_service = IPPoolService()
    return _ip_pool_service