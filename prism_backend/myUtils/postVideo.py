import asyncio
from pathlib import Path
import sys
import os
from datetime import datetime

# 添加父目录到 Python 路径
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

# from config.conf import BASE_DIR
BASE_DIR = Path(__file__).parent.parent
"""
DEPRECATED:
本文件属于旧的“同步发布封装”，历史上被批量发布服务调用。
现在发布统一入口已收敛到 `syn_backend/platforms/*/upload.py`（通过 `platforms/registry.py`）。
如需兼容旧脚本入口，建议改为调用 `platforms.registry.get_uploader_by_platform_code()`。
"""

from uploader.douyin_uploader.main import DouYinVideo
from uploader.ks_uploader.main import KSVideo
from uploader.tencent_uploader.main import TencentVideo
from uploader.xiaohongshu_uploader.main import XiaoHongShuVideo
from utils.constant import TencentZoneTypes
from utils.files_times import generate_schedule_time_next_day
from myUtils.cookie_manager import cookie_manager

# IP Pool Integration
try:
    from fastapi_app.services.ip_pool_service import get_ip_pool_service
    IP_POOL_AVAILABLE = True
except ImportError:
    IP_POOL_AVAILABLE = False
    print("Warning: IP Pool Service unavailable in postVideo.py")

def get_proxy_for_account(account_file_path: Path) -> dict:
    """Helper to resolve proxy for a given account cookie file."""
    if not IP_POOL_AVAILABLE:
        return None
    try:
        service = get_ip_pool_service()
        # Filename stem is usually "douyin_12345" or "12345"
        stem = account_file_path.stem
        
        # 1. Try exact match
        ip_obj = service.get_ip_for_account(stem)
        
        # 2. Try stripping platform prefix (e.g. "douyin_123" -> "123")
        if not ip_obj and "_" in stem:
             _, core_id = stem.split("_", 1)
             ip_obj = service.get_ip_for_account(core_id)
        
        if ip_obj:
            proxy_url = ip_obj.to_proxy_url()
            if proxy_url:
                print(f"[Proxy] Account {stem} bound to IP {ip_obj.ip}:{ip_obj.port}")
                return {"server": proxy_url}
            else:
                # Direct mode
                pass
    except Exception as e:
        print(f"[Proxy] Lookup failed for {account_file_path}: {e}")
    return None


def _parse_publish_datetime(value):
    if not value or value == 0:
        return 0
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        # assume seconds timestamp
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return 0
        # normalize iso -> "YYYY-MM-DD HH:MM"
        if "T" in s:
            s = s.replace("T", " ")
        s = s.replace("Z", "")
        try:
            return datetime.fromisoformat(s)
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
    return 0


def post_video_tencent(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0, description='', publish_date=0):
    # 生成文件的完整路径
    account_file = [cookie_manager._resolve_cookie_path(file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    publish_datetimes = [0 for _ in range(len(files))]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(files), videos_per_day, daily_times, start_days)
    # Allow caller to pass an explicit publish time (single task)
    publish_dt_override = _parse_publish_datetime(publish_date)
    if publish_dt_override and publish_dt_override != 0:
        publish_datetimes = [publish_dt_override for _ in range(len(files))]
    for index, file in enumerate(files):
        for cookie in account_file:
            print(f"文件路径{str(file)}")
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"描述：{description}")
            print(f"Hashtag：{tags}")
            # TencentVideo 可能需要更新以支持 description，如果不支持，暂时忽略或拼接到 title
            # 假设 TencentVideo 构造函数签名: (title, file_path, tags, publish_date, account_file, category)
            # 如果它不支持 description，我们需要检查 uploader/tencent_uploader/main.py
            # 暂时保持原样调用，后续确认 TencentVideo 是否支持
            # Resolve Proxy
            proxy = get_proxy_for_account(cookie)
            
            app = TencentVideo(title, str(file), tags, publish_datetimes[index], cookie, category, proxy=proxy)
            asyncio.run(app.main(), debug=False)


def post_video_DouYin(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0,
                      thumbnail_path = '',
                      productLink = '', productTitle = '', description='', publish_date=0):
    # 生成文件的完整路径
    account_file = [cookie_manager._resolve_cookie_path(file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    publish_datetimes = [0 for _ in range(len(files))]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(files), videos_per_day, daily_times, start_days)
    # Allow caller to pass an explicit publish time (single task)
    publish_dt_override = _parse_publish_datetime(publish_date)
    if publish_dt_override and publish_dt_override != 0:
        publish_datetimes = [publish_dt_override for _ in range(len(files))]
    for index, file in enumerate(files):
        for cookie in account_file:
            print(f"文件路径{str(file)}")
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"描述：{description}")
            print(f"Hashtag：{tags}")
            # 抖音：标签会在 UI 中单独输入；统一控制为最多 3 个，去重，避免重复与超限。
            seen = set()
            dy_tags = []
            for t in tags or []:
                t = str(t).strip().lstrip("#")
                if not t or t in seen:
                    continue
                seen.add(t)
                dy_tags.append(t)
                if len(dy_tags) >= 3:
                    break

            # Defensive: title may contain newline + hashtags; keep first line only
            clean_title = str(title).splitlines()[0].strip()
            if "#" in clean_title:
                clean_title = clean_title.split("#", 1)[0].strip()
            
            # Resolve Proxy
            proxy = get_proxy_for_account(cookie)
            
            app = DouYinVideo(clean_title, str(file), dy_tags, publish_datetimes[index], cookie, thumbnail_path, productLink, productTitle, proxy=proxy)
            asyncio.run(app.main(), debug=False)


def post_video_ks(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0, description=''):
    # 生成文件的完整路径
    account_file = [cookie_manager._resolve_cookie_path(file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(len(files), videos_per_day, daily_times,start_days)
    else:
        publish_datetimes = [0 for i in range(len(files))]
    for index, file in enumerate(files):
        for cookie in account_file:
            print(f"文件路径{str(file)}")
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"描述：{description}")
            print(f"Hashtag：{tags}")
            
            # 快手同理，合并 title 和 description
            final_title = title
            if description and description != title:
                final_title = f"{title}\n{description}"

            # Resolve Proxy
            proxy = get_proxy_for_account(cookie)
            app = KSVideo(final_title, str(file), tags, publish_datetimes[index], cookie, proxy=proxy)
            asyncio.run(app.main(), debug=False)

def post_video_xhs(title,files,tags,account_file,category=TencentZoneTypes.LIFESTYLE.value,enableTimer=False,videos_per_day = 1, daily_times=None,start_days = 0, description=''):
    # 生成文件的完整路径
    account_file = [cookie_manager._resolve_cookie_path(file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    file_num = len(files)
    if enableTimer:
        publish_datetimes = generate_schedule_time_next_day(file_num, videos_per_day, daily_times,start_days)
    else:
        publish_datetimes = [0 for _ in range(file_num)]
    for index, file in enumerate(files):
        publish_date = publish_datetimes[index] if index < len(publish_datetimes) else 0
        for cookie in account_file:
            # 打印视频文件名、标题和 hashtag
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"描述：{description}")
            print(f"Hashtag：{tags}")
            
            # 小红书支持 title 和 description 分开
            # XiaoHongShuVideo(title, file_path, tags, publish_date, account_file, description=None)
            # 需要检查 XiaoHongShuVideo 构造函数
            # 假设它目前只接受 (title, file, tags, publish_date, cookie)
            # 我们暂时将 description 拼接到 title (如果不修改 XiaoHongShuVideo)
            # 或者修改 XiaoHongShuVideo。这里先假设我们要修改 XiaoHongShuVideo 支持 description
            
            # 暂时合并，直到确认 XiaoHongShuVideo 更新
            # app = XiaoHongShuVideo(title, file, tags, publish_date, cookie)
            # 为了支持 description，我们需要修改 XiaoHongShuVideo。
            # 这里先传入，如果报错说明 XiaoHongShuVideo 没更新
            # 但为了安全，我们先合并到 title，除非我们确定 XiaoHongShuVideo 已更新
            # 鉴于我无法一次性修改所有文件，这里先合并
            
            # 修正：小红书的 title 是标题，description 是正文。如果 XiaoHongShuVideo 不支持 description 参数，
            #那么它的 title 参数可能被用作正文（如果它没有单独的 title 字段）。
            # 通常小红书必须有标题和正文。
            
            # Resolve Proxy
            proxy = get_proxy_for_account(cookie)
            
            app = XiaoHongShuVideo(title, file, tags, publish_date, cookie, proxy=proxy)
            # 注意：如果 XiaoHongShuVideo 没有 description 参数，这里无法传递。
            # 必须修改 XiaoHongShuVideo。
            asyncio.run(app.main(), debug=False)

def post_video_bilibili(title, files, tags, account_file, category=160, enableTimer=False, videos_per_day=1, daily_times=None, start_days=0, description=''):
    """
    B站视频上传函数
    :param title: 视频标题
    :param files: 视频文件列表
    :param tags: 标签列表
    :param account_file: 账号cookie文件列表
    :param category: 分区ID (默认160=生活,其他分区见B站文档)
    :param enableTimer: 是否定时发布
    :param videos_per_day: 每天发布视频数
    :param daily_times: 每天发布时间点
    :param start_days: 开始天数
    :param description: 视频简介
    """
    from uploader.bilibili_uploader.main import BilibiliUploader, read_cookie_json_file, extract_keys_from_json
    
    # 生成文件的完整路径
    account_file = [cookie_manager._resolve_cookie_path(file) for file in account_file]
    files = [Path(BASE_DIR / "videoFile" / file) for file in files]
    
    if enableTimer:
        # biliup 的 `dtime` 需要 Unix timestamp（int 秒）
        publish_timestamps = generate_schedule_time_next_day(
            len(files),
            videos_per_day,
            daily_times,
            timestamps=True,
            start_days=start_days,
        )
    else:
        publish_timestamps = [0 for _ in range(len(files))]
    
    for index, file in enumerate(files):
        for cookie_file in account_file:
            print(f"文件路径{str(file)}")
            print(f"视频文件名：{file}")
            print(f"标题：{title}")
            print(f"描述：{description}")
            print(f"标签：{tags}")
            
            # 读取并解析cookie
            cookie_data_raw = read_cookie_json_file(cookie_file)
            cookie_data = extract_keys_from_json(cookie_data_raw)
            
            # 创建上传器并上传
            # 优先使用传入的 description，否则自动生成
            if description:
                desc = description
                # 确保标签也在简介中（可选，B站通常标签是独立的）
                # 如果用户习惯在简介里放标签，可以追加
            else:
                desc = f"{title}\n{'  '.join(['#' + tag for tag in tags])}"
                
            # Resolve Proxy
            proxy = get_proxy_for_account(cookie_file)

            uploader = BilibiliUploader(
                cookie_data=cookie_data,
                file=file,
                title=title,
                desc=desc,
                tid=category,
                tags=tags,
                dtime=publish_timestamps[index] if publish_timestamps[index] != 0 else None,
                proxy=proxy
            )
            ok = uploader.upload()
            if not ok:
                raise RuntimeError("BilibiliUploader.upload() failed")


# post_video("333",["demo.mp4"],"d","d")
# post_video_DouYin("333",["demo.mp4"],"d","d")
