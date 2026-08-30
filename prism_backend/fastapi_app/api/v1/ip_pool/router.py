"""
IP池管理API路由
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from fastapi_app.models.ip_pool import (
    ProxyIP, IPStatus, IPSourceType, AddIPRequest, 
    ImportProxyRequest, BindAccountRequest, IPStatsResponse, IPProtocol
)
from fastapi_app.services.ip_pool_service import get_ip_pool_service, IPPoolService
from fastapi_app.services.qingguo_service import qingguo_service
from fastapi_app.core.logger import logger


router = APIRouter(prefix="/ip-pool", tags=["IP池管理"])

# --- 请求模型 ---
class QGFetchRequest(BaseModel):
    link: Optional[str] = None  # 完整的提取链接
    key: Optional[str] = None   # 或者单独的 key
    area: Optional[str] = None  # 可选地区代码
    isp: Optional[str] = "0"
    note_prefix: Optional[str] = "青果"

class QGReleaseRequest(BaseModel):
    key: str
    ip: Optional[str] = None

class BindBatchRequest(BaseModel):
    ip_id: str
    account_ids: List[str]

# --- 现有接口 ---

@router.get("/stats", response_model=IPStatsResponse)
async def get_statistics(
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """获取IP池统计信息"""
    return service.get_statistics()


@router.get("/list")
async def list_ips(
    status: Optional[IPStatus] = None,
    ip_type: Optional[IPSourceType] = None,
    region: Optional[str] = None,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """获取IP列表"""
    ips = service.list_ips(status=status, ip_type=ip_type, region=region)
    return {
        "status": "success",
        "result": {
            "success": True,
            "items": [ip.model_dump(mode="json") for ip in ips],
            "total": len(ips)
        }
    }


@router.get("/export")
async def export_ips(
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """导出所有代理信息"""
    data = service.export_ips()
    return {
        "status": "success",
        "result": {
            "success": True,
            "items": data,
            "total": len(data)
        }
    }


@router.get("/{ip_id}")
async def get_ip_detail(
    ip_id: str,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """获取IP详情"""
    ip = service.get_ip(ip_id)
    if not ip:
        raise HTTPException(status_code=404, detail="IP不存在")
    
    return {
        "status": "success",
        "result": {
            "success": True,
            "ip": ip.model_dump(mode="json")
        }
    }


@router.post("/add")
async def add_ip(
    request: AddIPRequest,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """添加IP到池中"""
    try:
        ip = service.add_ip(request)
        return {
            "status": "success",
            "result": {
                "success": True,
                "ip_id": ip.id,
                "message": f"成功添加IP {ip.ip}:{ip.port}"
            }
        }
    except Exception as e:
        logger.error(f"添加IP失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{ip_id}")
async def delete_ip(
    ip_id: str,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """删除IP"""
    success = service.delete_ip(ip_id)
    if not success:
        raise HTTPException(status_code=404, detail="IP不存在")
    
    return {
        "status": "success",
        "result": {
            "success": True,
            "message": "IP已删除"
        }
    }


@router.post("/bind")
async def bind_account(
    request: BindAccountRequest,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """绑定账号到IP"""
    try:
        service.bind_account_to_ip(request.ip_id, request.account_id)
        return {
            "status": "success",
            "result": {
                "success": True,
                "message": f"成功绑定账号到IP"
            }
        }
    except Exception as e:
        logger.error(f"绑定账号失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bind-batch")
async def bind_batch_accounts(
    request: BindBatchRequest,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """批量绑定账号到IP"""
    try:
        ip_id = request.ip_id
        account_ids = request.account_ids

        success_count = 0
        failed = []
        
        for account_id in account_ids:
            try:
                service.bind_account_to_ip(ip_id, account_id)
                success_count += 1
            except Exception as e:
                failed.append({"account_id": account_id, "error": str(e)})
        
        return {
            "status": "success",
            "result": {
                "success": True,
                "success_count": success_count,
                "failed_count": len(failed),
                "failed": failed,
                "message": f"成功绑定 {success_count}/{len(account_ids)} 个账号"
            }
        }
    except Exception as e:
        logger.error(f"批量绑定失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/unbind/{account_id}")
async def unbind_account(
    account_id: str,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """解绑账号"""
    success = service.unbind_account(account_id)
    return {
        "status": "success",
        "result": {
            "success": success,
            "message": "账号已解绑" if success else "账号未绑定任何IP"
        }
    }


@router.post("/auto-bind/{account_id}")
async def auto_bind_account(
    account_id: str,
    prefer_region: Optional[str] = None,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """自动为账号分配IP（已有绑定则返回原代理，不换绑）"""
    existing = service.get_ip_for_account(account_id)
    ip = service.auto_bind_account(account_id, prefer_region)
    
    if not ip:
        raise HTTPException(status_code=404, detail="没有可用IP")
    
    message = f"账号已绑定代理 {ip.ip}:{ip.port}（持久绑定，不换绑）" if existing else f"首次分配代理 {ip.ip}:{ip.port}"
    
    return {
        "status": "success",
        "result": {
            "success": True,
            "ip_id": ip.id,
            "ip": f"{ip.ip}:{ip.port}",
            "message": message,
            "existing_binding": bool(existing)
        }
    }


@router.post("/{ip_id}/toggle")
async def toggle_ip_enabled(
    ip_id: str,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """启用/禁用代理节点"""
    ip = service.get_ip(ip_id)
    if not ip:
        raise HTTPException(status_code=404, detail="代理不存在")
    ip.is_enabled = not ip.is_enabled
    ip.updated_at = datetime.now()
    service._save_ips()
    return {
        "status": "success",
        "result": {
            "success": True,
            "is_enabled": ip.is_enabled,
            "message": "代理已启用" if ip.is_enabled else "代理已禁用"
        }
    }


@router.post("/check-health/{ip_id}")
async def check_ip_health(
    ip_id: str,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """检测单个IP健康状态"""
    ip = service.get_ip(ip_id)
    if not ip:
        raise HTTPException(status_code=404, detail="IP不存在")
    
    healthy = await service.check_ip_health(ip)
    
    # 更新状态
    if healthy:
        service.update_ip_status(ip_id, IPStatus.AVAILABLE)
    else:
        service.update_ip_status(ip_id, IPStatus.FAILED)
    
    return {
        "status": "success",
        "result": {
            "success": True,
            "healthy": healthy,
            "ip_status": IPStatus.AVAILABLE if healthy else IPStatus.FAILED,
            "exit_ip": ip.exit_ip,
            "asn": ip.asn,
            "latency_ms": ip.latency_ms,
            "message": "IP可用 (连接成功)" if healthy else "IP不可用 (连接失败)"
        }
    }


@router.post("/import")
async def import_ips(
    request: ImportProxyRequest,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """批量导入代理"""
    added = service.import_ips(request.items)
    return {
        "status": "success",
        "result": {
            "success": True,
            "count": len(added),
            "message": f"成功导入 {len(added)} 个代理"
        }
    }


@router.post("/batch-check")
async def batch_check_health(
    ids: List[str],
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """批量检测指定代理"""
    results = {}
    for ip_id in ids:
        ip = service.get_ip(ip_id)
        if ip:
            healthy = await service.check_ip_health(ip)
            results[ip_id] = {"healthy": healthy, "exit_ip": ip.exit_ip, "asn": ip.asn, "latency_ms": ip.latency_ms}
    return {
        "status": "success",
        "result": results
    }


@router.post("/check-all")
async def check_all_health(
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """批量检测所有IP健康状态"""
    results = await service.batch_check_health()
    
    healthy_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    return {
        "status": "success",
        "result": {
            "success": True,
            "total": total_count,
            "healthy": healthy_count,
            "failed": total_count - healthy_count,
            "details": results,
            "message": f"检测完成: {healthy_count}/{total_count} 个IP可用"
        }
    }

from fastapi_app.services.proxy_fetcher_service import proxy_fetcher
from fastapi_app.services.qingguo_service import qingguo_service # 保留青果服务用于特定操作如释放

# ... (Previous code)

class APIFetchRequest(BaseModel):
    url: str
    note_prefix: Optional[str] = "API提取"

# ... (Other endpoints)

# --- 通用 API 提取接口 ---

@router.post("/fetch-from-url")
async def fetch_ip_from_url(
    request: APIFetchRequest,
    service: IPPoolService = Depends(get_ip_pool_service)
):
    """
    通用接口：从任意 URL 提取 IP
    会自动尝试解析返回内容中的 IP:Port
    """
    if not request.url:
        raise HTTPException(status_code=400, detail="Missing API URL")
        
    # 1. 调用通用提取服务
    result = await proxy_fetcher.fetch_and_parse(request.url)
    
    if not result["success"]:
        return {
            "status": "error", 
            "message": f"提取失败: {result.get('message')}"
        }
        
    ip_str = result["ip"]
    port = result["port"]
    provider = result.get("provider_guess", "unknown")
    
    # 2. 构造添加请求
    # 注意：通用提取拿不到地区和运营商信息，除非特定适配
    # 这里我们简化处理，或者将来做更深入的适配
    
    # 尝试利用原始响应里的一些常见字段猜测地区 (简单适配青果/通用JSON)
    raw = result.get("original_response", {})
    region_guess = ""
    isp_guess = ""
    if isinstance(raw, dict):
        region_guess = raw.get("area") or raw.get("region") or raw.get("city") or ""
        isp_guess = raw.get("isp") or ""
    
    note = f"{request.note_prefix}"
    if isp_guess: note += f"_{isp_guess}"
    if region_guess: note += f"_{region_guess}"
    
    add_req = AddIPRequest(
        ip=ip_str,
        port=port,
        protocol=IPProtocol.HTTP,
        ip_type=IPSourceType.DYNAMIC_RESIDENTIAL,
        country="CN",
        region=region_guess if region_guess else None,
        max_bindings=50,
        note=note,
        provider=provider # 记录 provider 方便后续可能的特定操作
    )
    
    # 3. 添加到池
    try:
        new_ip = service.add_ip(add_req)
        return {
            "status": "success",
            "result": {
                "success": True,
                "ip": new_ip.model_dump(mode="json"),
                "message": f"成功提取: {ip_str}:{port}"
            }
        }
    except Exception as e:
         return {
            "status": "error", 
            "message": f"提取成功但入库失败: {str(e)}"
        }

# --- 青果特定操作 (Release/Query) ---
# 用户给出了特定接口用于查询和释放，我们保留这些能力，供前端在识别到是 QingGuo IP 时调用

@router.post("/qg/release")
async def release_qingguo_ip(
    request: QGReleaseRequest
):
    """释放/销毁青果IP"""
    # 这里我们依然用 qingguo_service，因为它已经封装好了 delete 请求
    success = await qingguo_service.release_ip(request.key, request.ip)
    return {
        "status": "success",
        "result": {
            "success": success,
            "message": "释放成功" if success else "释放失败"
        }
    }


# ── Persona Studio 状态（Browser Identity 层健康）──

@router.get("/persona/status")
async def persona_status():
    """Persona Studio 服务状态（Browser Identity / Fingerprint / Profile 层）。"""
    try:
        from fastapi_app.services.persona_client import get_persona_client
        from fastapi_app.core.config import settings
        client = get_persona_client()
        online = await client.health()
        profiles = []
        engine = settings.PERSONA_DEFAULT_ENGINE
        if online:
            try:
                profiles = await client.list_profiles()
            except Exception:
                profiles = []
        return {
            "status": "success",
            "result": {
                "online": online,
                "api_base": client.base_url,
                "default_engine": engine,
                "inject_proxy": settings.PERSONA_INJECT_PROXY,
                "profile_count": len(profiles) if isinstance(profiles, list) else 0,
                "message": "Persona Studio 在线" if online else "Persona Studio 离线，浏览器回退 Patchright 直连模式",
            }
        }
    except Exception as e:
        logger.error(f"查询 Persona 状态失败: {e}")
        return {
            "status": "success",
            "result": {
                "online": False,
                "message": "Persona Studio 不可用",
            }
        }
