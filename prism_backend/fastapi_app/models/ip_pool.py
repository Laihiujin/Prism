"""
IP池数据模型
"""
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import uuid4


class IPSourceType(str, Enum):
    """IP来源类型"""
    RESIDENTIAL = "residential"           # 住宅IP
    DATACENTER = "datacenter"            # 数据中心IP
    MOBILE = "mobile"                    # 移动IP
    DYNAMIC_RESIDENTIAL = "dynamic_residential"  # 动态住宅IP


class IPProtocol(str, Enum):
    """代理协议"""
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"
    DIRECT = "direct"  # 新增：本机直连


class IPStatus(str, Enum):
    """IP状态"""
    AVAILABLE = "available"    # 可用
    IN_USE = "in_use"         # 使用中
    FAILED = "failed"         # 失效
    BANNED = "banned"         # 被封禁
    CHECKING = "checking"     # 检测中
    DEGRADED = "degraded"     # 降级（连续1次失败，暂不换绑）
    AUTH_FAILED = "auth_failed"  # 认证失败（密码错误等）


class ProxyIP(BaseModel):
    """代理IP模型"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    
    # 基础信息
    name: Optional[str] = Field(None, description="节点名称，如 proxy-001")
    ip: str = Field(..., description="IP地址/主机")
    port: int = Field(..., description="端口号")
    protocol: IPProtocol = Field(default=IPProtocol.HTTP, description="协议类型")
    
    # 认证信息
    username: Optional[str] = Field(None, description="代理用户名")
    password: Optional[str] = Field(None, description="代理密码")
    
    # IP类型
    ip_type: IPSourceType = Field(default=IPSourceType.RESIDENTIAL, description="IP类型")
    
    # 状态
    status: IPStatus = Field(default=IPStatus.AVAILABLE, description="IP状态")
    
    # 绑定信息（支持多账号绑定）
    bound_account_ids: List[str] = Field(default_factory=list, description="绑定的账号ID列表")
    max_bindings: int = Field(default=1, description="最大绑定账号数，默认1（账号级固定绑定）")
    
    # 地理位置
    country: str = Field(default="CN", description="国家代码")
    region: Optional[str] = Field(None, description="省/州")
    city: Optional[str] = Field(None, description="城市")
    isp: Optional[str] = Field(None, description="运营商")
    asn: Optional[str] = Field(None, description="ASN编号")
    
    # 出口IP（健康检测时经代理探测到的真实出口IP）
    exit_ip: Optional[str] = Field(None, description="出口IP（经代理实际出口）")
    latency_ms: Optional[int] = Field(None, description="最近延迟(ms)")
    
    # ── 健康状态机（连续失败计数 + 出口IP漂移检测）──
    consecutive_failures: int = Field(default=0, description="连续失败次数")
    is_enabled: bool = Field(default=True, description="是否启用（禁用后不可绑定/使用）")
    previous_exit_ip: Optional[str] = Field(None, description="上一次检测到的出口IP（用于漂移检测）")
    exit_ip_changed_at: Optional[datetime] = Field(None, description="出口IP最近一次变化时间")
    last_success_at: Optional[datetime] = Field(None, description="最近成功检测时间")
    last_failure_at: Optional[datetime] = Field(None, description="最近失败检测时间")
    
    # 使用统计
    success_count: int = Field(default=0, description="成功次数")
    fail_count: int = Field(default=0, description="失败次数")
    total_used: int = Field(default=0, description="总使用次数")
    
    # 时间戳
    last_used_at: Optional[datetime] = Field(None, description="最后使用时间")
    last_check_at: Optional[datetime] = Field(None, description="最后检测时间")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    
    # 备注
    note: Optional[str] = Field(None, description="备注")
    provider: Optional[str] = Field(None, description="代理商名称")
    
    class Config:
        use_enum_values = True
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_used == 0:
            return 0.0
        return round(self.success_count / self.total_used * 100, 2)
    
    @property
    def is_healthy(self) -> bool:
        """是否健康"""
        return self.status in (IPStatus.AVAILABLE, IPStatus.IN_USE)
    
    @property
    def exit_ip_changed(self) -> bool:
        """出口IP是否发生过漂移"""
        return bool(
            self.exit_ip
            and self.previous_exit_ip
            and self.exit_ip != self.previous_exit_ip
        )
    
    def to_proxy_url(self) -> Optional[str]:
        """转换为代理URL"""
        if self.protocol == IPProtocol.DIRECT:
            return None  # 直连不返回代理URL

        if self.username and self.password:
            return f"{self.protocol}://{self.username}:{self.password}@{self.ip}:{self.port}"
        return f"{self.protocol}://{self.ip}:{self.port}"


class AddIPRequest(BaseModel):
    """添加IP请求"""
    name: Optional[str] = None
    ip: str
    port: int
    protocol: IPProtocol = IPProtocol.HTTP
    username: Optional[str] = None
    password: Optional[str] = None
    ip_type: IPSourceType = IPSourceType.RESIDENTIAL
    country: str = "CN"
    region: Optional[str] = None
    city: Optional[str] = None
    isp: Optional[str] = None
    asn: Optional[str] = None
    max_bindings: int = 1
    note: Optional[str] = None
    provider: Optional[str] = None


class ImportProxyRequest(BaseModel):
    """批量导入代理请求"""
    items: List[AddIPRequest]


class BindAccountRequest(BaseModel):
    """绑定账号请求"""
    ip_id: str
    account_id: str


class IPStatsResponse(BaseModel):
    """IP统计响应"""
    total: int
    available: int
    in_use: int
    failed: int
    banned: int
    total_bindings: int
    avg_success_rate: float
