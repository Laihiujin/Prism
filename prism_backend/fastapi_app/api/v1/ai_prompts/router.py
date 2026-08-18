"""
AI Prompts Configuration Management API
支持可视化编辑和管理所有AI提示词
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import yaml
from pathlib import Path
from datetime import datetime
from fastapi_app.core.config import settings
from fastapi_app.core.logger import logger

router = APIRouter(prefix="/ai-prompts", tags=["ai-prompts"])

# 配置文件路径
PROMPTS_CONFIG_PATH = settings.BASE_DIR / "config" / "ai_prompts_unified.yaml"

# 缓存配置，避免频繁读取文件
_PROMPTS_CACHE: Dict[str, Any] = {"mtime": None, "data": None}


def _load_prompts_config() -> Dict[str, Any]:
    """加载AI配置文件（带缓存）"""
    if not PROMPTS_CONFIG_PATH.exists():
        raise FileNotFoundError(f"配置文件不存在: {PROMPTS_CONFIG_PATH}")

    try:
        mtime = PROMPTS_CONFIG_PATH.stat().st_mtime

        # 检查缓存
        if _PROMPTS_CACHE.get("data") and _PROMPTS_CACHE.get("mtime") == mtime:
            return _PROMPTS_CACHE["data"]

        # 读取配置
        with open(PROMPTS_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # 更新缓存
        _PROMPTS_CACHE["data"] = data
        _PROMPTS_CACHE["mtime"] = mtime

        logger.info(f"AI配置已加载: {PROMPTS_CONFIG_PATH}")
        return data

    except Exception as e:
        logger.error(f"加载AI配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"加载配置失败: {str(e)}")


def _save_prompts_config(data: Dict[str, Any]) -> bool:
    """保存AI配置文件"""
    try:
        # 备份原配置
        backup_path = PROMPTS_CONFIG_PATH.with_suffix(".yaml.bak")
        if PROMPTS_CONFIG_PATH.exists():
            import shutil
            shutil.copy2(PROMPTS_CONFIG_PATH, backup_path)

        # 更新metadata
        if "metadata" not in data:
            data["metadata"] = {}
        data["metadata"]["last_updated"] = datetime.now().isoformat()

        # 保存配置
        with open(PROMPTS_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

        # 清除缓存
        _PROMPTS_CACHE["data"] = None
        _PROMPTS_CACHE["mtime"] = None

        logger.info(f"AI配置已保存: {PROMPTS_CONFIG_PATH}")
        return True

    except Exception as e:
        logger.error(f"保存AI配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存配置失败: {str(e)}")


class PromptConfigItem(BaseModel):
    """单个Prompt配置项"""
    category: str = Field(..., description="分类名称")
    label: str = Field(..., description="显示标签")
    description: Optional[str] = Field(None, description="描述")
    version: Optional[str] = Field(None, description="版本号")
    editable: bool = Field(True, description="是否可编辑")
    system_prompt: str = Field(..., description="系统提示词")
    extra_config: Optional[Dict[str, Any]] = Field(None, description="额外配置")


class PromptCategoryResponse(BaseModel):
    """Prompt分类响应"""
    category: str
    label: str
    items: List[Dict[str, Any]]


class UpdatePromptRequest(BaseModel):
    """更新Prompt请求"""
    system_prompt: str = Field(..., description="新的系统提示词")
    extra_config: Optional[Dict[str, Any]] = Field(None, description="额外配置")


@router.get("/structure", summary="获取AI配置结构（用于前端渲染导航）")
async def get_prompts_structure():
    """
    返回配置的层级结构，用于前端面包屑导航和分类展示

    返回格式：
    [
        {
            "category": "content_generation",
            "label": "内容生成",
            "items": [
                {"key": "title_generation", "label": "标题生成", "editable": true},
                {"key": "description_generation", "label": "文案生成", "editable": true},
                ...
            ]
        },
        ...
    ]
    """
    try:
        config = _load_prompts_config()

        structure = []

        # 处理 content_generation 模块
        if "content_generation" in config:
            items = []
            for key, value in config["content_generation"].items():
                if isinstance(value, dict) and "label" in value:
                    items.append({
                        "key": key,
                        "label": value.get("label", key),
                        "description": value.get("description", ""),
                        "editable": value.get("editable", True),
                        "version": value.get("version", "1.0"),
                    })

            if items:
                structure.append({
                    "category": "content_generation",
                    "label": "内容生成",
                    "items": items
                })

        # 处理 chat_assistant
        if "chat_assistant" in config:
            chat = config["chat_assistant"]
            structure.append({
                "category": "chat_assistant",
                "label": "聊天助手",
                "items": [{
                    "key": "chat_assistant",
                    "label": chat.get("label", "智能助手"),
                    "description": chat.get("description", ""),
                    "editable": chat.get("editable", True),
                    "version": chat.get("version", "1.0"),
                }]
            })

        # 处理 automation 模块
        if "automation" in config:
            items = []
            for key, value in config["automation"].items():
                if isinstance(value, dict) and "label" in value:
                    items.append({
                        "key": key,
                        "label": value.get("label", key),
                        "description": value.get("description", ""),
                        "editable": value.get("editable", True),
                        "version": value.get("version", "1.0"),
                    })

            if items:
                structure.append({
                    "category": "automation",
                    "label": "自动化",
                    "items": items
                })

        # 处理 routing 和 general
        system_items = []
        if "routing" in config:
            routing = config["routing"]
            system_items.append({
                "key": "routing",
                "label": routing.get("label", "意图路由"),
                "description": routing.get("description", ""),
                "editable": routing.get("editable", False),
                "version": routing.get("version", "1.0"),
            })

        if "general" in config:
            general = config["general"]
            system_items.append({
                "key": "general",
                "label": general.get("label", "全局配置"),
                "description": general.get("description", ""),
                "editable": general.get("editable", False),
                "version": general.get("version", "1.0"),
            })

        if system_items:
            structure.append({
                "category": "system",
                "label": "系统配置",
                "items": system_items
            })

        return {
            "status": "success",
            "data": structure
        }

    except Exception as e:
        logger.error(f"获取配置结构失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置结构失败: {str(e)}")


@router.get("/config/{config_key}", summary="获取指定配置项的详细信息")
async def get_prompt_config(config_key: str):
    """
    获取指定配置项的完整配置

    参数：
    - config_key: 配置键，支持点号路径，例如：
      - "title_generation" (content_generation下的)
      - "chat_assistant"
      - "manus_agent" (automation下的)
    """
    try:
        config = _load_prompts_config()

        # 查找配置项
        target_config = None
        category_path = []

        # 在 content_generation 中查找
        if "content_generation" in config and config_key in config["content_generation"]:
            target_config = config["content_generation"][config_key]
            category_path = ["content_generation", config_key]

        # 在 automation 中查找
        elif "automation" in config and config_key in config["automation"]:
            target_config = config["automation"][config_key]
            category_path = ["automation", config_key]

        # 直接在根级别查找
        elif config_key in config:
            target_config = config[config_key]
            category_path = [config_key]

        if not target_config:
            raise HTTPException(status_code=404, detail=f"配置项不存在: {config_key}")

        return {
            "status": "success",
            "data": {
                "key": config_key,
                "category_path": category_path,
                "config": target_config
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.put("/config/{config_key}", summary="更新指定配置项")
async def update_prompt_config(config_key: str, request: UpdatePromptRequest):
    """
    更新指定配置项的 system_prompt 和 extra_config

    参数：
    - config_key: 配置键
    - request: 更新请求体
    """
    try:
        config = _load_prompts_config()

        # 查找配置项
        target_config = None
        category_path = []

        # 在 content_generation 中查找
        if "content_generation" in config and config_key in config["content_generation"]:
            target_config = config["content_generation"][config_key]
            category_path = ["content_generation", config_key]

        # 在 automation 中查找
        elif "automation" in config and config_key in config["automation"]:
            target_config = config["automation"][config_key]
            category_path = ["automation", config_key]

        # 直接在根级别查找
        elif config_key in config:
            target_config = config[config_key]
            category_path = [config_key]

        if not target_config:
            raise HTTPException(status_code=404, detail=f"配置项不存在: {config_key}")

        # 检查是否可编辑
        if not target_config.get("editable", True):
            raise HTTPException(status_code=403, detail=f"配置项不可编辑: {config_key}")

        # 更新配置
        target_config["system_prompt"] = request.system_prompt

        if request.extra_config:
            for key, value in request.extra_config.items():
                target_config[key] = value

        # 保存配置
        _save_prompts_config(config)

        logger.info(f"配置已更新: {config_key}")

        return {
            "status": "success",
            "message": f"配置项 {config_key} 已更新",
            "data": {
                "key": config_key,
                "category_path": category_path,
                "config": target_config
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新配置失败: {str(e)}")


@router.post("/config/{config_key}/reset", summary="重置配置项到默认值")
async def reset_prompt_config(config_key: str):
    """
    重置指定配置项到默认值（从备份文件恢复）
    """
    try:
        backup_path = PROMPTS_CONFIG_PATH.with_suffix(".yaml.bak")

        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="备份文件不存在，无法重置")

        # 从备份加载配置
        with open(backup_path, "r", encoding="utf-8") as f:
            backup_config = yaml.safe_load(f)

        # 查找目标配置
        target_config = None

        if "content_generation" in backup_config and config_key in backup_config["content_generation"]:
            target_config = backup_config["content_generation"][config_key]
        elif "automation" in backup_config and config_key in backup_config["automation"]:
            target_config = backup_config["automation"][config_key]
        elif config_key in backup_config:
            target_config = backup_config[config_key]

        if not target_config:
            raise HTTPException(status_code=404, detail=f"备份中未找到配置项: {config_key}")

        # 加载当前配置
        current_config = _load_prompts_config()

        # 替换配置
        if "content_generation" in current_config and config_key in current_config["content_generation"]:
            current_config["content_generation"][config_key] = target_config
        elif "automation" in current_config and config_key in current_config["automation"]:
            current_config["automation"][config_key] = target_config
        elif config_key in current_config:
            current_config[config_key] = target_config

        # 保存配置
        _save_prompts_config(current_config)

        logger.info(f"配置已重置: {config_key}")

        return {
            "status": "success",
            "message": f"配置项 {config_key} 已重置到默认值"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"重置配置失败: {str(e)}")


@router.get("/metadata", summary="获取配置文件元数据")
async def get_prompts_metadata():
    """获取配置文件的元数据信息"""
    try:
        config = _load_prompts_config()
        metadata = config.get("metadata", {})

        return {
            "status": "success",
            "data": {
                "version": metadata.get("version", "unknown"),
                "last_updated": metadata.get("last_updated", "unknown"),
                "description": metadata.get("description", ""),
                "file_path": str(PROMPTS_CONFIG_PATH),
                "file_size": PROMPTS_CONFIG_PATH.stat().st_size,
            }
        }

    except Exception as e:
        logger.error(f"获取元数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取元数据失败: {str(e)}")
