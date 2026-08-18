from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from ai_service.script_runner import list_available_scripts, run_script

router = APIRouter(prefix="/scripts", tags=["scripts"])


class RunScriptRequest(BaseModel):
    name: str
    args: Optional[List[str]] = []


@router.get("/list")
async def list_scripts():
    """List runnable backend scripts."""
    scripts = list_available_scripts()
    return {"status": "success", "scripts": scripts}


@router.post("/run")
async def run_scripts(request: RunScriptRequest):
    """Execute a whitelisted script with optional args."""
    if not request.name:
        raise HTTPException(status_code=400, detail="name is required")

    try:
        result = run_script(request.name, request.args if isinstance(request.args, list) else [])
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
