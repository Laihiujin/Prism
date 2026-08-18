import os
import zipfile
import subprocess
import tempfile

import aiofiles
import httpx
import yaml
from fastapi import APIRouter, Request, Query, HTTPException  # 导入FastAPI组件
from starlette.responses import FileResponse

from ..models.APIResponseModel import ErrorResponseModel  # 导入响应模型
from crawlers.hybrid.hybrid_crawler import HybridCrawler  # 导入混合数据爬虫

router = APIRouter()
HybridCrawler = HybridCrawler()

# 读取上级再上级目录的配置文件
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'config.yaml')
with open(config_path, 'r', encoding='utf-8') as file:
    config = yaml.safe_load(file)

async def fetch_data(url: str, headers: dict = None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    } if headers is None else headers.get('headers')
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()  # 确保响应是成功的
        return response

# 下载视频专用
async def fetch_data_stream(url: str, request:Request , headers: dict = None, file_path: str = None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    } if headers is None else headers.get('headers')
    async with httpx.AsyncClient() as client:
        # 启用流式请求
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()

            # 流式保存文件
            async with aiofiles.open(file_path, 'wb') as out_file:
                async for chunk in response.aiter_bytes():
                    if await request.is_disconnected():
                        print("客户端断开连接，清理未完成的文件")
                        await out_file.close()
                        os.remove(file_path)
                        return False
                    await out_file.write(chunk)
            return True

async def merge_bilibili_video_audio(video_url: str, audio_url: str, request: Request, output_path: str, headers: dict) -> bool:
    """
    下载并合并 Bilibili 的视频流和音频流
    """
    try:
        # 创建临时文件
        with tempfile.NamedTemporaryFile(suffix='.m4v', delete=False) as video_temp:
            video_temp_path = video_temp.name
        with tempfile.NamedTemporaryFile(suffix='.m4a', delete=False) as audio_temp:
            audio_temp_path = audio_temp.name
        
        # 下载视频流
        video_success = await fetch_data_stream(video_url, request, headers=headers, file_path=video_temp_path)
        # 下载音频流
        audio_success = await fetch_data_stream(audio_url, request, headers=headers, file_path=audio_temp_path)
        
        if not video_success or not audio_success:
            print("Failed to download video or audio stream")
            return False
        
        # 使用 FFmpeg 合并视频和音频
        ffmpeg_cmd = [
            'ffmpeg', '-y',  # -y 覆盖输出文件
            '-i', video_temp_path,  # 视频输入
            '-i', audio_temp_path,  # 音频输入
            '-c:v', 'copy',  # 复制视频编码，不重新编码
            '-c:a', 'copy',  # 复制音频编码，不重新编码（保持原始质量）
            '-f', 'mp4',     # 确保输出格式为MP4
            output_path
        ]
        
        print(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        print(f"FFmpeg return code: {result.returncode}")
        if result.stderr:
            print(f"FFmpeg stderr: {result.stderr}")
        if result.stdout:
            print(f"FFmpeg stdout: {result.stdout}")
        
        # 清理临时文件
        try:
            os.unlink(video_temp_path)
            os.unlink(audio_temp_path)
        except:
            pass
        
        return result.returncode == 0
        
    except Exception as e:
        # 清理临时文件
        try:
            os.unlink(video_temp_path)
            os.unlink(audio_temp_path)
        except:
            pass
        print(f"Error merging video and audio: {e}")
        return False

@router.get("/download", summary="在线下载抖音|TikTok|Bilibili视频/图片/Online download Douyin|TikTok|Bilibili video/image")
async def download_file_hybrid(request: Request,
                               url: str = Query(
                                   examples={"example": {"value": "https://www.douyin.com/video/7372484719365098803"}},
                                   description="视频或图片的URL地址，支持抖音|TikTok|Bilibili的分享链接，例如：https://v.douyin.com/e4J8Q7A/ 或 https://www.bilibili.com/video/BV1xxxxxxxxx"),
                               prefix: bool = True,
                               with_watermark: bool = False):
    """
    # [中文]
    ### 用途:
    - 在线下载抖音|TikTok|Bilibili 无水印或有水印的视频/图片
    - 通过传入的视频URL参数，获取对应的视频或图片数据，然后下载到本地。
    - 如果你在尝试直接访问TikTok单一视频接口的JSON数据中的视频播放地址时遇到HTTP403错误，那么你可以使用此接口来下载视频。
    - Bilibili视频会自动合并视频流和音频流，确保下载的视频有声音。
    - 这个接口会占用一定的服务器资源，所以在Demo站点是默认关闭的，你可以在本地部署后调用此接口。
    ### 参数:
    - url: 视频或图片的URL地址，支持抖音|TikTok|Bilibili的分享链接，例如：https://v.douyin.com/e4J8Q7A/ 或 https://www.bilibili.com/video/BV1xxxxxxxxx
    - prefix: 下载文件的前缀，默认为True，可以在配置文件中修改。
    - with_watermark: 是否下载带水印的视频或图片，默认为False。(注意：Bilibili没有水印概念)
    ### 返回:
    - 返回下载的视频或图片文件响应。

    # [English]
    ### Purpose:
    - Download Douyin|TikTok|Bilibili video/image with or without watermark online.
    - By passing the video URL parameter, get the corresponding video or image data, and then download it to the local.
    - If you encounter an HTTP403 error when trying to access the video playback address in the JSON data of the TikTok single video interface directly, you can use this interface to download the video.
    - Bilibili videos will automatically merge video and audio streams to ensure downloaded videos have sound.
    - This interface will occupy a certain amount of server resources, so it is disabled by default on the Demo site, you can call this interface after deploying it locally.
    ### Parameters:
    - url: The URL address of the video or image, supports Douyin|TikTok|Bilibili sharing links, for example: https://v.douyin.com/e4J8Q7A/ or https://www.bilibili.com/video/BV1xxxxxxxxx
    - prefix: The prefix of the downloaded file, the default is True, and can be modified in the configuration file.
    - with_watermark: Whether to download videos or images with watermarks, the default is False. (Note: Bilibili has no watermark concept)
    ### Returns:
    - Return the response of the downloaded video or image file.

    # [示例/Example]
    url: https://www.bilibili.com/video/BV1U5efz2Egn
    """
    # 是否开启此端点/Whether to enable this endpoint
    if not config["API"]["Download_Switch"]:
        code = 400
        message = "Download endpoint is disabled in the configuration file. | 配置文件中已禁用下载端点。"
        return ErrorResponseModel(code=code, message=message, router=request.url.path,
                                  params=dict(request.query_params))

    # 开始解析数据/Start parsing data
    try:
        data = await HybridCrawler.hybrid_parsing_single_video(url, minimal=True)
    except Exception as e:
        code = 400
        return ErrorResponseModel(code=code, message=str(e), router=request.url.path, params=dict(request.query_params))

    # 开始下载文件/Start downloading files
    try:
        data_type = data.get('type')
        platform = data.get('platform')
        video_id = data.get('video_id')  # 改为使用video_id
        file_prefix = config.get("API").get("Download_File_Prefix") if prefix else ''
        download_path = os.path.join(config.get("API").get("Download_Path"), f"{platform}_{data_type}")

        # 确保目录存在/Ensure the directory exists
        os.makedirs(download_path, exist_ok=True)

        # 下载视频文件/Download video file
        if data_type == 'video':
            file_name = f"{file_prefix}{platform}_{video_id}.mp4" if not with_watermark else f"{file_prefix}{platform}_{video_id}_watermark.mp4"
            file_path = os.path.join(download_path, file_name)

            # 判断文件是否存在，存在就直接返回
            if os.path.exists(file_path):
                return FileResponse(path=file_path, media_type='video/mp4', filename=file_name)

            # 获取对应平台的headers
            if platform == 'tiktok':
                __headers = await HybridCrawler.TikTokWebCrawler.get_tiktok_headers()
            elif platform == 'bilibili':
                __headers = await HybridCrawler.BilibiliWebCrawler.get_bilibili_headers()
            else:  # douyin
                __headers = await HybridCrawler.DouyinWebCrawler.get_douyin_headers()

            # Bilibili 特殊处理：音视频分离
            if platform == 'bilibili':
                video_data = data.get('video_data', {})
                video_url = video_data.get('nwm_video_url_HQ') if not with_watermark else video_data.get('wm_video_url_HQ')
                audio_url = video_data.get('audio_url')
                if not video_url or not audio_url:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to get video or audio URL from Bilibili"
                    )
                
                # 使用专门的函数合并音视频
                success = await merge_bilibili_video_audio(video_url, audio_url, request, file_path, __headers.get('headers'))
                if not success:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to merge Bilibili video and audio streams"
                    )
            else:
                # 其他平台的常规处理
                url = data.get('video_data').get('nwm_video_url_HQ') if not with_watermark else data.get('video_data').get('wm_video_url_HQ')
                success = await fetch_data_stream(url, request, headers=__headers, file_path=file_path)
                if not success:
                    raise HTTPException(
                        status_code=500,
                        detail="An error occurred while fetching data"
                    )

            # # 保存文件
            # async with aiofiles.open(file_path, 'wb') as out_file:
            #     await out_file.write(response.content)

            # 返回文件内容
            return FileResponse(path=file_path, filename=file_name, media_type="video/mp4")

        # 下载图片文件/Download image file
        elif data_type == 'image':
            # 压缩文件属性/Compress file properties
            zip_file_name = f"{file_prefix}{platform}_{video_id}_images.zip" if not with_watermark else f"{file_prefix}{platform}_{video_id}_images_watermark.zip"
            zip_file_path = os.path.join(download_path, zip_file_name)

            # 判断文件是否存在，存在就直接返回、
            if os.path.exists(zip_file_path):
                return FileResponse(path=zip_file_path, filename=zip_file_name, media_type="application/zip")

            # 获取图片文件/Get image file
            urls = data.get('image_data').get('no_watermark_image_list') if not with_watermark else data.get(
                'image_data').get('watermark_image_list')
            image_file_list = []
            for url in urls:
                # 请求图片文件/Request image file
                response = await fetch_data(url)
                index = int(urls.index(url))
                content_type = response.headers.get('content-type')
                file_format = content_type.split('/')[1]
                file_name = f"{file_prefix}{platform}_{video_id}_{index + 1}.{file_format}" if not with_watermark else f"{file_prefix}{platform}_{video_id}_{index + 1}_watermark.{file_format}"
                file_path = os.path.join(download_path, file_name)
                image_file_list.append(file_path)

                # 保存文件/Save file
                async with aiofiles.open(file_path, 'wb') as out_file:
                    await out_file.write(response.content)

            # 压缩文件/Compress file
            with zipfile.ZipFile(zip_file_path, 'w') as zip_file:
                for image_file in image_file_list:
                    zip_file.write(image_file, os.path.basename(image_file))

            # 返回压缩文件/Return compressed file
            return FileResponse(path=zip_file_path, filename=zip_file_name, media_type="application/zip")

    # 异常处理/Exception handling
    except Exception as e:
        print(e)
        code = 400
        return ErrorResponseModel(code=code, message=str(e), router=request.url.path, params=dict(request.query_params))
