"""
Persona 代理网关管理 API。

提供订阅 URL 导入、配置生成、热重载、状态查询、取消导入能力。
前端对应页面: /persona-proxy
"""
import asyncio
from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from fastapi_app.core.logger import logger
from fastapi_app.services import persona_proxy_gateway as gw

router = APIRouter(prefix="/persona-proxy", tags=["代理网关"])


class SubscriptionIn(BaseModel):
    url: str


@router.get("")
async def status():
    """获取网关当前状态（订阅 URL、节点端口映射、端口监听、控制器健康）。"""
    try:
        return {"status": "success", "result": gw.current_status()}
    except Exception as e:
        logger.error(f"查询代理网关状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询代理网关状态失败: {e}")


@router.get("/meta")
async def meta():
    """返回网关基础信息（端口起点、控制器地址）。"""
    return {
        "status": "success",
        "result": {
            "base_port": gw.BASE_PORT,
            "controller_url": gw.CONTROLLER_URL,
            "config_path": str(gw.CONFIG_PATH),
        },
    }


@router.put("/subscription")
async def set_subscription(data: SubscriptionIn = Body(...)):
    """导入订阅 URL：抓取 -> 解析全部节点 -> 分配端口 -> 生成配置 -> 热重载。"""
    url = (data.url or "").strip()
    if not url or not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="请输入合法的订阅 URL（http/https）")
    try:
        result = await asyncio.to_thread(gw.generate_and_reload, url)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"导入订阅失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入订阅失败: {e}")


@router.delete("/subscription")
async def clear_subscription():
    """取消导入：清空节点与端口分配，释放所有监听端口，保留网关进程。"""
    try:
        result = await asyncio.to_thread(gw.clear_subscription)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"取消导入失败: {e}")
        raise HTTPException(status_code=500, detail=f"取消导入失败: {e}")


@router.post("/reload")
async def reload():
    """不重新抓取，仅用现有 config.yaml 热重载。"""
    try:
        result = await asyncio.to_thread(gw.reload_existing)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"重载代理网关失败: {e}")
        raise HTTPException(status_code=500, detail=f"重载代理网关失败: {e}")
