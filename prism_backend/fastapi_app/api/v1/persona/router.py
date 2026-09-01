"""
Persona Studio Dashboard 托管 API（内嵌进 Prism 前端）。

提供 Dashboard 前端进程的启动 / 停止 / 状态查询能力。
前端对应页面: /persona
"""
from fastapi import APIRouter, HTTPException

from fastapi_app.core.logger import logger
from fastapi_app.services import persona_dashboard

router = APIRouter(prefix="/persona", tags=["Persona"])


@router.get("/dashboard/status")
async def dashboard_status():
    """Dashboard 前端进程状态（running / url / persona API 在线与否）。"""
    try:
        return {"status": "success", "result": await persona_dashboard.get_persona_dashboard_status()}
    except Exception as e:
        logger.error(f"查询 Persona Dashboard 状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询 Persona Dashboard 状态失败: {e}")


@router.post("/dashboard/start")
async def dashboard_start():
    """拉起 Persona Dashboard 前端进程（幂等：已在运行则直接返回状态）。"""
    try:
        result = await persona_dashboard.start_persona_dashboard()
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"启动 Persona Dashboard 失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动 Persona Dashboard 失败: {e}")


@router.post("/dashboard/stop")
async def dashboard_stop():
    """停止由本服务拉起的 Persona Dashboard 前端进程。"""
    try:
        result = await persona_dashboard.stop_persona_dashboard()
        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"停止 Persona Dashboard 失败: {e}")
        raise HTTPException(status_code=500, detail=f"停止 Persona Dashboard 失败: {e}")
