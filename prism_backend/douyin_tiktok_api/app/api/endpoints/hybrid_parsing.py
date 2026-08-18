import asyncio

from fastapi import APIRouter, Body, Query, Request, HTTPException  # 导入FastAPI组件

from ..models.APIResponseModel import ResponseModel, ErrorResponseModel  # 导入响应模型

# 爬虫/Crawler
from crawlers.hybrid.hybrid_crawler import HybridCrawler  # 导入混合爬虫

HybridCrawler = HybridCrawler()  # 实例化混合爬虫

router = APIRouter()


@router.get("/video_data", response_model=ResponseModel, tags=["Hybrid-API"],
            summary="混合解析单一视频接口/Hybrid parsing single video endpoint")
async def hybrid_parsing_single_video(request: Request,
                                      url: str = Query(examples={"example": {"value": "https://v.douyin.com/L4FJNR3/"}}),
                                      minimal: bool = Query(default=False)):
    """
    # [中文]
    ### 用途:
    - 该接口用于解析抖音/TikTok单一视频的数据。
    ### 参数:
    - `url`: 视频链接、分享链接、分享文本。
    ### 返回:
    - `data`: 视频数据。

    # [English]
    ### Purpose:
    - This endpoint is used to parse data of a single Douyin/TikTok video.
    ### Parameters:
    - `url`: Video link, share link, or share text.
    ### Returns:
    - `data`: Video data.

    # [Example]
    url = "https://v.douyin.com/L4FJNR3/"
    """
    try:
        # 解析视频/Parse video
        data = await HybridCrawler.hybrid_parsing_single_video(url=url, minimal=minimal)
        # 返回数据/Return data
        return ResponseModel(code=200,
                             router=request.url.path,
                             data=data)
    except Exception as e:
        status_code = 400
        detail = ErrorResponseModel(code=status_code,
                                    router=request.url.path,
                                    params=dict(request.query_params),
                                    )
        raise HTTPException(status_code=status_code, detail=detail.dict())

# 更新Cookie
@router.post("/update_cookie",
             response_model=ResponseModel,
             summary="更新Cookie/Update Cookie")
async def update_cookie_api(request: Request,
                           service: str = Body(examples={"example": {"value": "douyin"}}, description="服务名称/Service name"),
                           cookie: str = Body(examples={"example": {"value": "YOUR_NEW_COOKIE"}}, description="新的Cookie值/New Cookie value")):
    """
    # [中文]
    ### 用途:
    - 更新指定服务的Cookie
    ### 参数:
    - service: 服务名称 (如: douyin_web)
    - cookie: 新的Cookie值
    ### 返回:
    - 更新结果

    # [English]
    ### Purpose:
    - Update Cookie for specified service
    ### Parameters:
    - service: Service name (e.g.: douyin_web)
    - cookie: New Cookie value
    ### Return:
    - Update result

    # [示例/Example]
    service = "douyin_web"
    cookie = "YOUR_NEW_COOKIE"
    """
    try:
        if service == "douyin":
            from crawlers.douyin.web.web_crawler import DouyinWebCrawler
            douyin_crawler = DouyinWebCrawler()
            await douyin_crawler.update_cookie(cookie)
            return ResponseModel(code=200,
                                router=request.url.path,
                                data={"message": f"Cookie for {service} updated successfully"})
        elif service == "tiktok":
            # 这里可以添加TikTok的cookie更新逻辑
            # from crawlers.tiktok.web.web_crawler import TikTokWebCrawler
            # tiktok_crawler = TikTokWebCrawler()
            # await tiktok_crawler.update_cookie(cookie)
            return ResponseModel(code=200,
                                router=request.url.path,
                                data={"message": f"Cookie for {service} will be updated (not implemented yet)"})
        elif service == "bilibili":
            # 这里可以添加Bilibili的cookie更新逻辑
            # from crawlers.bilibili.web.web_crawler import BilibiliWebCrawler
            # bilibili_crawler = BilibiliWebCrawler()
            # await bilibili_crawler.update_cookie(cookie)
            return ResponseModel(code=200,
                                router=request.url.path,
                                data={"message": f"Cookie for {service} will be updated (not implemented yet)"})
        else:
            raise ValueError(f"Service '{service}' is not supported. Supported services: douyin, tiktok, bilibili")
    except Exception as e:
        status_code = 400
        detail = ErrorResponseModel(code=status_code,
                                    router=request.url.path,
                                    params=dict(request.query_params),
                                    )
        raise HTTPException(status_code=status_code, detail=detail.dict())
