"""
混合爬虫 API 路由
Hybrid Crawler API Router

支持平台：抖音、TikTok、Bilibili
Supported platforms: Douyin, TikTok, Bilibili
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal
import sys
import os

# 添加 douyin_tiktok_api 到路径
douyin_api_path = os.path.join(os.path.dirname(__file__), '../../../../douyin_tiktok_api')
sys.path.insert(0, douyin_api_path)

from crawlers.hybrid.hybrid_crawler import HybridCrawler
from crawlers.douyin.web.web_crawler import DouyinWebCrawler
from crawlers.bilibili.web.web_crawler import BilibiliWebCrawler

router = APIRouter()

# 初始化爬虫实例
hybrid_crawler = HybridCrawler()
douyin_crawler = DouyinWebCrawler()
bilibili_crawler = BilibiliWebCrawler()


class VideoURLRequest(BaseModel):
    """视频链接请求模型"""
    url: str = Field(..., description="视频分享链接 (支持抖音/TikTok/Bilibili)", example="https://v.douyin.com/xxx/")
    minimal: bool = Field(default=False, description="是否返回最小数据集")


class VideoDataResponse(BaseModel):
    """视频数据响应模型"""
    success: bool = Field(..., description="请求是否成功")
    platform: Optional[str] = Field(None, description="平台名称")
    data: Optional[dict] = Field(None, description="视频数据")
    error: Optional[str] = Field(None, description="错误信息")


class AccountVideosRequest(BaseModel):
    """账号视频列表请求模型"""
    platform: Literal["douyin", "bilibili"] = Field(..., description="平台名称")
    user_id: str = Field(..., description="用户ID (抖音: sec_user_id, B站: mid)")
    max_cursor: int = Field(default=0, description="分页游标")
    count: int = Field(default=20, description="每页数量", ge=1, le=100)


@router.post("/fetch_video", response_model=VideoDataResponse, summary="抓取单个视频数据（混合接口）")
async def fetch_video(request: VideoURLRequest):
    """
    ## 功能说明

    通过分享链接抓取单个视频数据，自动识别平台。

    ### 支持的平台：
    - **抖音 (Douyin)**: `https://v.douyin.com/xxx/`
    - **TikTok**: `https://www.tiktok.com/@user/video/xxx`
    - **Bilibili**: `https://www.bilibili.com/video/BVxxx` 或 `https://b23.tv/xxx`

    ### 参数说明：
    - `url`: 视频分享链接（必填）
    - `minimal`: 是否返回最小数据集（默认 False，返回完整数据）

    ### 返回数据：
    - `success`: 请求是否成功
    - `platform`: 自动识别的平台名称
    - `data`: 视频完整数据（包含标题、作者、统计数据、视频链接等）
    - `error`: 错误信息（如果失败）

    ### 使用场景：
    - 外部视频数据分析
    - 竞品视频监控
    - 内容素材收集

    ### 示例：
    ```python
    # 抖音视频
    response = await fetch_video({
        "url": "https://v.douyin.com/xxx/",
        "minimal": False
    })

    # TikTok视频
    response = await fetch_video({
        "url": "https://www.tiktok.com/@user/video/xxx",
        "minimal": False
    })

    # Bilibili视频
    response = await fetch_video({
        "url": "https://b23.tv/xxx",
        "minimal": False
    })
    ```
    """
    try:
        # 调用混合爬虫
        data = await hybrid_crawler.hybrid_parsing_single_video(
            url=request.url,
            minimal=request.minimal
        )

        # 判断平台
        platform = None
        if "douyin" in request.url:
            platform = "douyin"
        elif "tiktok" in request.url:
            platform = "tiktok"
        elif "bilibili" in request.url or "b23.tv" in request.url:
            platform = "bilibili"

        return VideoDataResponse(
            success=True,
            platform=platform,
            data=data,
            error=None
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"抓取失败: {str(e)}")


@router.post("/fetch_account_videos", response_model=VideoDataResponse, summary="抓取账号视频列表（项目内账号）")
async def fetch_account_videos(request: AccountVideosRequest):
    """
    ## 功能说明

    抓取项目内已登录账号的视频列表数据。

    ### 支持的平台：
    - **抖音 (Douyin)**: 需要提供 sec_user_id
    - **Bilibili**: 需要提供 mid (用户ID)

    ### 参数说明：
    - `platform`: 平台名称 ("douyin" 或 "bilibili")
    - `user_id`: 用户ID
      - 抖音: sec_user_id (如 MS4wLjABAAAA...)
      - B站: mid (数字ID)
    - `max_cursor`: 分页游标（默认 0）
    - `count`: 每页数量（默认 20，最大 100）

    ### 返回数据：
    - `success`: 请求是否成功
    - `platform`: 平台名称
    - `data`: 视频列表数据
    - `error`: 错误信息（如果失败）

    ### 使用场景：
    - 项目内账号数据分析
    - 内容管理
    - 数据统计

    ### 示例：
    ```python
    # 抖音账号视频
    response = await fetch_account_videos({
        "platform": "douyin",
        "user_id": "MS4wLjABAAAA...",
        "max_cursor": 0,
        "count": 20
    })

    # B站账号视频
    response = await fetch_account_videos({
        "platform": "bilibili",
        "user_id": "123456",
        "max_cursor": 0,
        "count": 20
    })
    ```
    """
    try:
        if request.platform == "douyin":
            # 抖音账号视频列表
            data = await douyin_crawler.fetch_user_post_videos(
                sec_user_id=request.user_id,
                max_cursor=request.max_cursor,
                count=request.count
            )
        elif request.platform == "bilibili":
            # B站账号视频列表
            data = await bilibili_crawler.fetch_user_post_videos(
                mid=request.user_id,
                pn=request.max_cursor + 1,  # B站使用页码，从1开始
                ps=request.count
            )
        else:
            raise ValueError(f"不支持的平台: {request.platform}")

        return VideoDataResponse(
            success=True,
            platform=request.platform,
            data=data,
            error=None
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"抓取失败: {str(e)}")


@router.get("/supported_platforms", summary="获取支持的平台列表")
async def get_supported_platforms():
    """
    ## 功能说明

    获取混合爬虫支持的所有平台列表。

    ### 返回数据：
    ```json
    {
        "platforms": [
            {
                "name": "douyin",
                "display_name": "抖音",
                "url_keywords": ["douyin"],
                "example_url": "https://v.douyin.com/xxx/"
            },
            {
                "name": "tiktok",
                "display_name": "TikTok",
                "url_keywords": ["tiktok"],
                "example_url": "https://www.tiktok.com/@user/video/xxx"
            },
            {
                "name": "bilibili",
                "display_name": "Bilibili",
                "url_keywords": ["bilibili", "b23.tv"],
                "example_url": "https://www.bilibili.com/video/BVxxx"
            }
        ]
    }
    ```
    """
    return {
        "platforms": [
            {
                "name": "douyin",
                "display_name": "抖音",
                "url_keywords": ["douyin"],
                "example_url": "https://v.douyin.com/xxx/",
                "supports_external": True,
                "supports_account": True
            },
            {
                "name": "tiktok",
                "display_name": "TikTok",
                "url_keywords": ["tiktok"],
                "example_url": "https://www.tiktok.com/@user/video/xxx",
                "supports_external": True,
                "supports_account": False
            },
            {
                "name": "bilibili",
                "display_name": "Bilibili",
                "url_keywords": ["bilibili", "b23.tv"],
                "example_url": "https://www.bilibili.com/video/BVxxx",
                "supports_external": True,
                "supports_account": True
            }
        ]
    }
