from fastapi import APIRouter

router = APIRouter(prefix="/recovery", tags=["recovery"])


@router.get("/health")
async def health_check():
    """Recovery module health check"""
    return {"status": "ok", "module": "recovery"}
