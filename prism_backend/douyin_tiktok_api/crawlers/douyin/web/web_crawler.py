# ==============================================================================
# Copyright (C) 2021 Evil0ctal
#
# This file is part of the Douyin_TikTok_Download_API project.
#
# This project is licensed under the Apache License 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
# 　　　　 　　  ＿＿
# 　　　 　　 ／＞　　フ
# 　　　 　　| 　_　 _ l
# 　 　　 　／` ミ＿xノ
# 　　 　 /　　　 　 |       Feed me Stars ⭐ ️
# 　　　 /　 ヽ　　 ﾉ
# 　 　 │　　|　|　|
# 　／￣|　　 |　|　|
# 　| (￣ヽ＿_ヽ_)__)
# 　＼二つ
# ==============================================================================
#
# Contributor Link:
# - https://github.com/Evil0ctal
# - https://github.com/Johnserf-Seed
#
# ==============================================================================


import asyncio  # 异步I/O
import os  # 系统操作
import time  # 时间操作
from urllib.parse import urlencode, quote  # URL编码
import yaml  # 配置文件

# 基础爬虫客户端和抖音API端点
from crawlers.base_crawler import BaseCrawler
from crawlers.douyin.web.endpoints import DouyinAPIEndpoints
# 抖音接口数据请求模型
from crawlers.douyin.web.models import (
    BaseRequestModel, LiveRoomRanking, PostComments,
    PostCommentsReply, PostDetail,
    UserProfile, UserCollection, UserLike, UserLive,
    UserLive2, UserMix, UserPost
)
# 抖音应用的工具类
from crawlers.douyin.web.utils import (AwemeIdFetcher,  # Aweme ID获取
                                       BogusManager,  # XBogus管理
                                       SecUserIdFetcher,  # 安全用户ID获取
                                       TokenManager,  # 令牌管理
                                       VerifyFpManager,  # 验证管理
                                       WebCastIdFetcher,  # 直播ID获取
                                       extract_valid_urls  # URL提取
                                       )

# 配置文件路径
path = os.path.abspath(os.path.dirname(__file__))

# 读取配置文件
with open(f"{path}/config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)


class DouyinWebCrawler:

    def __init__(self):
        self.cookie_override = None

    async def set_account_cookie(self, cookie: str):
        """Use account credentials without mutating shared YAML configuration."""
        self.cookie_override = cookie

    # 从配置文件中获取抖音的请求头
    async def get_douyin_headers(self):
        douyin_config = config["TokenManager"]["douyin"]
        kwargs = {
            "headers": {
                "Accept-Language": douyin_config["headers"]["Accept-Language"],
                "User-Agent": douyin_config["headers"]["User-Agent"],
                "Referer": douyin_config["headers"]["Referer"],
                "Cookie": self.cookie_override if self.cookie_override is not None else douyin_config["headers"]["Cookie"],
            },
            "proxies": {"http://": douyin_config["proxies"]["http"], "https://": douyin_config["proxies"]["https"]},
        }
        return kwargs

    "-------------------------------------------------------handler接口列表-------------------------------------------------------"

    # 获取单个作品数据
    async def fetch_one_video(self, aweme_id: str):
        # 获取抖音的实时Cookie
        kwargs = await self.get_douyin_headers()
        # 创建一个基础爬虫
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            # 创建一个作品详情的BaseModel参数
            params = PostDetail(aweme_id=aweme_id)
            # 生成一个作品详情的带有加密参数的Endpoint
            # 2024年6月12日22:41:44 由于XBogus加密已经失效，所以不再使用XBogus加密参数，转移至a_bogus加密参数。
            # endpoint = BogusManager.xb_model_2_endpoint(
            #     DouyinAPIEndpoints.POST_DETAIL, params.dict(), kwargs["headers"]["User-Agent"]
            # )

            # 生成一个作品详情的带有a_bogus加密参数的Endpoint
            params_dict = params.dict()
            params_dict["msToken"] = ''
            a_bogus = BogusManager.ab_model_2_endpoint(params_dict, kwargs["headers"]["User-Agent"])
            endpoint = f"{DouyinAPIEndpoints.POST_DETAIL}?{urlencode(params_dict)}&a_bogus={a_bogus}"

            response = await crawler.fetch_get_json(endpoint)
        return response

    # 获取用户发布作品数据
    async def fetch_user_post_videos(self, sec_user_id: str, max_cursor: int, count: int):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = UserPost(sec_user_id=sec_user_id, max_cursor=max_cursor, count=count)
            # endpoint = BogusManager.xb_model_2_endpoint(
            #     DouyinAPIEndpoints.USER_POST, params.dict(), kwargs["headers"]["User-Agent"]
            # )
            # response = await crawler.fetch_get_json(endpoint)

            # 生成一个用户发布作品数据的带有a_bogus加密参数的Endpoint
            params_dict = params.dict()
            from http.cookies import SimpleCookie
            account_cookies = SimpleCookie()
            account_cookies.load(kwargs["headers"].get("Cookie", ""))
            if "msToken" in account_cookies:
                params_dict["msToken"] = account_cookies["msToken"].value
            a_bogus = BogusManager.ab_model_2_endpoint(params_dict, kwargs["headers"]["User-Agent"])
            endpoint = f"{DouyinAPIEndpoints.USER_POST}?{urlencode(params_dict)}&a_bogus={a_bogus}"

            response = await crawler.fetch_get_json(endpoint)
        return response

    # 获取用户喜欢作品数据
    async def fetch_user_like_videos(self, sec_user_id: str, max_cursor: int, count: int):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = UserLike(sec_user_id=sec_user_id, max_cursor=max_cursor, count=count)
            # endpoint = BogusManager.xb_model_2_endpoint(
            #     DouyinAPIEndpoints.USER_FAVORITE_A, params.dict(), kwargs["headers"]["User-Agent"]
            # )
            # response = await crawler.fetch_get_json(endpoint)

            params_dict = params.dict()
            params_dict["msToken"] = ''
            a_bogus = BogusManager.ab_model_2_endpoint(params_dict, kwargs["headers"]["User-Agent"])
            endpoint = f"{DouyinAPIEndpoints.USER_FAVORITE_A}?{urlencode(params_dict)}&a_bogus={a_bogus}"

            response = await crawler.fetch_get_json(endpoint)
        return response

    # 获取用户收藏作品数据（用户提供自己的Cookie）
    async def fetch_user_collection_videos(self, cookie: str, cursor: int = 0, count: int = 20):
        kwargs = await self.get_douyin_headers()
        kwargs["headers"]["Cookie"] = cookie
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = UserCollection(cursor=cursor, count=count)
            endpoint = BogusManager.xb_model_2_endpoint(
                DouyinAPIEndpoints.USER_COLLECTION, params.dict(), kwargs["headers"]["User-Agent"]
            )
            response = await crawler.fetch_post_json(endpoint)
        return response

    # 获取用户合辑作品数据
    async def fetch_user_mix_videos(self, mix_id: str, cursor: int = 0, count: int = 20):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = UserMix(mix_id=mix_id, cursor=cursor, count=count)
            endpoint = BogusManager.xb_model_2_endpoint(
                DouyinAPIEndpoints.MIX_AWEME, params.dict(), kwargs["headers"]["User-Agent"]
            )
            response = await crawler.fetch_get_json(endpoint)
        return response

    # 获取用户直播流数据
    async def fetch_user_live_videos(self, webcast_id: str, room_id_str=""):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = UserLive(web_rid=webcast_id, room_id_str=room_id_str)
            endpoint = BogusManager.xb_model_2_endpoint(
                DouyinAPIEndpoints.LIVE_INFO, params.dict(), kwargs["headers"]["User-Agent"]
            )
            response = await crawler.fetch_get_json(endpoint)
        return response

    # 获取指定用户的直播流数据
    async def fetch_user_live_videos_by_room_id(self, room_id: str):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = UserLive2(room_id=room_id)
            endpoint = BogusManager.xb_model_2_endpoint(
                DouyinAPIEndpoints.LIVE_INFO_ROOM_ID, params.dict(), kwargs["headers"]["User-Agent"]
            )
            response = await crawler.fetch_get_json(endpoint)
        return response

    # 获取直播间送礼用户排行榜
    async def fetch_live_gift_ranking(self, room_id: str, rank_type: int = 30):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = LiveRoomRanking(room_id=room_id, rank_type=rank_type)
            endpoint = BogusManager.xb_model_2_endpoint(
                DouyinAPIEndpoints.LIVE_GIFT_RANK, params.dict(), kwargs["headers"]["User-Agent"]
            )
            response = await crawler.fetch_get_json(endpoint)
        return response

    # 获取指定用户的信息
    async def handler_user_profile(self, sec_user_id: str):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = UserProfile(sec_user_id=sec_user_id)
            endpoint = BogusManager.xb_model_2_endpoint(
                DouyinAPIEndpoints.USER_DETAIL, params.dict(), kwargs["headers"]["User-Agent"]
            )
            response = await crawler.fetch_get_json(endpoint)
        return response

    # 获取指定视频的评论数据
    async def fetch_video_comments(self, aweme_id: str, cursor: int = 0, count: int = 20):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = PostComments(aweme_id=aweme_id, cursor=cursor, count=count)
            endpoint = BogusManager.xb_model_2_endpoint(
                DouyinAPIEndpoints.POST_COMMENT, params.dict(), kwargs["headers"]["User-Agent"]
            )
            response = await crawler.fetch_get_json(endpoint)
        return response

    # 获取指定视频的评论回复数据
    async def fetch_video_comments_reply(self, item_id: str, comment_id: str, cursor: int = 0, count: int = 20):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = PostCommentsReply(item_id=item_id, comment_id=comment_id, cursor=cursor, count=count)
            endpoint = BogusManager.xb_model_2_endpoint(
                DouyinAPIEndpoints.POST_COMMENT_REPLY, params.dict(), kwargs["headers"]["User-Agent"]
            )
            response = await crawler.fetch_get_json(endpoint)
        return response

    # 获取抖音热榜数据
    async def fetch_hot_search_result(self):
        kwargs = await self.get_douyin_headers()
        base_crawler = BaseCrawler(proxies=kwargs["proxies"], crawler_headers=kwargs["headers"])
        async with base_crawler as crawler:
            params = BaseRequestModel()
            endpoint = BogusManager.xb_model_2_endpoint(
                DouyinAPIEndpoints.DOUYIN_HOT_SEARCH, params.dict(), kwargs["headers"]["User-Agent"]
            )
            response = await crawler.fetch_get_json(endpoint)
        return response

    "-------------------------------------------------------utils接口列表-------------------------------------------------------"

    # 生成真实msToken
    async def gen_real_msToken(self, ):
        result = {
            "msToken": TokenManager().gen_real_msToken()
        }
        return result

    # 生成ttwid
    async def gen_ttwid(self, ):
        result = {
            "ttwid": TokenManager().gen_ttwid()
        }
        return result

    # 生成verify_fp
    async def gen_verify_fp(self, ):
        result = {
            "verify_fp": VerifyFpManager.gen_verify_fp()
        }
        return result

    # 生成s_v_web_id
    async def gen_s_v_web_id(self, ):
        result = {
            "s_v_web_id": VerifyFpManager.gen_s_v_web_id()
        }
        return result

    # 使用接口地址生成Xb参数
    async def get_x_bogus(self, url: str, user_agent: str):
        url = BogusManager.xb_str_2_endpoint(url, user_agent)
        result = {
            "url": url,
            "x_bogus": url.split("&X-Bogus=")[1],
            "user_agent": user_agent
        }
        return result

    # 使用接口地址生成Ab参数
    async def get_a_bogus(self, url: str, user_agent: str):
        endpoint = url.split("?")[0]
        # 将URL参数转换为dict
        params = dict([i.split("=") for i in url.split("?")[1].split("&")])
        # 去除URL中的msToken参数
        params["msToken"] = ""
        a_bogus = BogusManager.ab_model_2_endpoint(params, user_agent)
        result = {
            "url": f"{endpoint}?{urlencode(params)}&a_bogus={a_bogus}",
            "a_bogus": a_bogus,
            "user_agent": user_agent
        }
        return result

    # 提取单个用户id
    async def get_sec_user_id(self, url: str):
        return await SecUserIdFetcher.get_sec_user_id(url)

    # 提取列表用户id
    async def get_all_sec_user_id(self, urls: list):
        # 提取有效URL
        urls = extract_valid_urls(urls)

        # 对于URL列表
        return await SecUserIdFetcher.get_all_sec_user_id(urls)

    # 提取单个作品id
    async def get_aweme_id(self, url: str):
        return await AwemeIdFetcher.get_aweme_id(url)

    # 提取列表作品id
    async def get_all_aweme_id(self, urls: list):
        # 提取有效URL
        urls = extract_valid_urls(urls)

        # 对于URL列表
        return await AwemeIdFetcher.get_all_aweme_id(urls)

    # 提取单个直播间号
    async def get_webcast_id(self, url: str):
        return await WebCastIdFetcher.get_webcast_id(url)

    # 提取列表直播间号
    async def get_all_webcast_id(self, urls: list):
        # 提取有效URL
        urls = extract_valid_urls(urls)

        # 对于URL列表
        return await WebCastIdFetcher.get_all_webcast_id(urls)

    async def update_cookie(self, cookie: str):
        """
        更新指定服务的Cookie
        
        Args:
            service: 服务名称 (如: douyin_web)
            cookie: 新的Cookie值
        """
        global config
        service = "douyin"
        # 1. 更新内存中的配置（立即生效）
        config["TokenManager"][service]["headers"]["Cookie"] = cookie
        # 2. 写入配置文件（持久化）
        config_path = f"{path}/config.yaml"
        with open(config_path, 'w', encoding='utf-8') as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True, indent=2)

    async def main(self):
        """-------------------------------------------------------handler接口列表-------------------------------------------------------"""

        # 获取单一视频信息
        # aweme_id = "7372484719365098803"
        # result = await self.fetch_one_video(aweme_id)
        # print(result)

        # 获取用户发布作品数据
        # sec_user_id = "MS4wLjABAAAANXSltcLCzDGmdNFI2Q_QixVTr67NiYzjKOIP5s03CAE"
        # max_cursor = 0
        # count = 10
        # result = await self.fetch_user_post_videos(sec_user_id, max_cursor, count)
        # print(result)

        # 获取用户喜欢作品数据
        # sec_user_id = "MS4wLjABAAAAW9FWcqS7RdQAWPd2AA5fL_ilmqsIFUCQ_Iym6Yh9_cUa6ZRqVLjVQSUjlHrfXY1Y"
        # max_cursor = 0
        # count = 10
        # result = await self.fetch_user_like_videos(sec_user_id, max_cursor, count)
        # print(result)

        # 获取用户收藏作品数据（用户提供自己的Cookie）
        # cookie = "带上你的Cookie/Put your Cookie here"
        # cursor = 0
        # counts = 20
        # result = await self.fetch_user_collection_videos(__cookie, cursor, counts)
        # print(result)

        # 获取用户合辑作品数据
        # https://www.douyin.com/collection/7348687990509553679
        # mix_id = "7348687990509553679"
        # cursor = 0
        # counts = 20
        # result = await self.fetch_user_mix_videos(mix_id, cursor, counts)
        # print(result)

        # 获取用户直播流数据
        # https://live.douyin.com/285520721194
        # webcast_id = "285520721194"
        # result = await self.fetch_user_live_videos(webcast_id)
        # print(result)

        # 获取指定用户的直播流数据
        # # https://live.douyin.com/7318296342189919011
        # room_id = "7318296342189919011"
        # result = await self.fetch_user_live_videos_by_room_id(room_id)
        # print(result)

        # 获取直播间送礼用户排行榜
        # room_id = "7356585666190461731"
        # rank_type = 30
        # result = await self.fetch_live_gift_ranking(room_id, rank_type)
        # print(result)

        # 获取指定用户的信息
        # sec_user_id = "MS4wLjABAAAAW9FWcqS7RdQAWPd2AA5fL_ilmqsIFUCQ_Iym6Yh9_cUa6ZRqVLjVQSUjlHrfXY1Y"
        # result = await self.handler_user_profile(sec_user_id)
        # print(result)

        # 获取单个视频评论数据
        # aweme_id = "7334525738793618688"
        # result = await self.fetch_video_comments(aweme_id)
        # print(result)

        # 获取单个视频评论回复数据
        # item_id = "7344709764531686690"
        # comment_id = "7346856757471953698"
        # result = await self.fetch_video_comments_reply(item_id, comment_id)
        # print(result)

        # 获取指定关键词的综合搜索结果
        # keyword = "中华娘"
        # offset = 0
        # count = 20
        # sort_type = "0"
        # publish_time = "0"
        # filter_duration = "0"
        # result = await self.fetch_general_search_result(keyword, offset, count, sort_type, publish_time, filter_duration)
        # print(result)

        # 获取抖音热榜数据
        # result = await self.fetch_hot_search_result()
        # print(result)

        """-------------------------------------------------------utils接口列表-------------------------------------------------------"""

        # 获取抖音Web的游客Cookie
        # user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
        # result = await self.fetch_douyin_web_guest_cookie(user_agent)
        # print(result)

        # 生成真实msToken
        # result = await self.gen_real_msToken()
        # print(result)

        # 生成ttwid
        # result = await self.gen_ttwid()
        # print(result)

        # 生成verify_fp
        # result = await self.gen_verify_fp()
        # print(result)

        # 生成s_v_web_id
        # result = await self.gen_s_v_web_id()
        # print(result)

        # 使用接口地址生成Xb参数
        # url = "https://www.douyin.com/aweme/v1/web/comment/list/?device_platform=webapp&aid=6383&channel=channel_pc_web&aweme_id=7334525738793618688&cursor=0&count=20&item_type=0&insert_ids=&whale_cut_token=&cut_version=1&rcFT=&pc_client_type=1&version_code=170400&version_name=17.4.0&cookie_enabled=true&screen_width=1344&screen_height=756&browser_language=zh-CN&browser_platform=Win32&browser_name=Firefox&browser_version=124.0&browser_online=true&engine_name=Gecko&engine_version=124.0&os_name=Windows&os_version=10&cpu_core_num=16&device_memory=&platform=PC&webid=7348962975497324070"
        # user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
        # result = await self.get_x_bogus(url, user_agent)
        # print(result)

        # 提取单个用户id
        # raw_url = "https://www.douyin.com/user/MS4wLjABAAAANXSltcLCzDGmdNFI2Q_QixVTr67NiYzjKOIP5s03CAE?vid=7285950278132616463"
        # result = await self.get_sec_user_id(raw_url)
        # print(result)

        # 提取列表用户id
        # raw_urls = [
        #     "https://www.douyin.com/user/MS4wLjABAAAANXSltcLCzDGmdNFI2Q_QixVTr67NiYzjKOIP5s03CAE?vid=7285950278132616463",
        #     "https://www.douyin.com/user/MS4wLjABAAAAVsneOf144eGDFf8Xp9QNb1VW6ovXnNT5SqJBhJfe8KQBKWKDTWK5Hh-_i9mJzb8C",
        #     "长按复制此条消息，打开抖音搜索，查看TA的更多作品。 https://v.douyin.com/idFqvUms/",
        #     "https://v.douyin.com/idFqvUms/",
        # ]
        # result = await self.get_all_sec_user_id(raw_urls)
        # print(result)

        # 提取单个作品id
        # raw_url = "https://www.douyin.com/video/7298145681699622182?previous_page=web_code_link"
        # result = await self.get_aweme_id(raw_url)
        # print(result)

        # 提取列表作品id
        # raw_urls = [
        #     "0.53 02/26 I@v.sE Fus:/ 你别太帅了郑润泽# 现场版live # 音乐节 # 郑润泽  https://v.douyin.com/iRNBho6u/ 复制此链接，打开Dou音搜索，直接观看视频!",
        #     "https://v.douyin.com/iRNBho6u/",
        #     "https://www.iesdouyin.com/share/video/7298145681699622182/?region=CN&mid=7298145762238565171&u_code=l1j9bkbd&did=MS4wLjABAAAAtqpCx0hpOERbdSzQdjRZw-wFPxaqdbAzsKDmbJMUI3KWlMGQHC-n6dXAqa-dM2EP&iid=MS4wLjABAAAANwkJuWIRFOzg5uCpDRpMj4OX-QryoDgn-yYlXQnRwQQ&with_sec_did=1&titleType=title&share_sign=05kGlqGmR4_IwCX.ZGk6xuL0osNA..5ur7b0jbOx6cc-&share_version=170400&ts=1699262937&from_aid=6383&from_ssr=1&from=web_code_link",
        #     "https://www.douyin.com/video/7298145681699622182?previous_page=web_code_link",
        #     "https://www.douyin.com/video/7298145681699622182",
        # ]
        # result = await self.get_all_aweme_id(raw_urls)
        # print(result)

        # 提取单个直播间号
        # raw_url = "https://live.douyin.com/775841227732"
        # result = await self.get_webcast_id(raw_url)
        # print(result)

        # 提取列表直播间号
        # raw_urls = [
        #     "https://live.douyin.com/775841227732",
        #     "https://live.douyin.com/775841227732?room_id=7318296342189919011&enter_from_merge=web_share_link&enter_method=web_share_link&previous_page=app_code_link",
        #     'https://webcast.amemv.com/douyin/webcast/reflow/7318296342189919011?u_code=l1j9bkbd&did=MS4wLjABAAAAEs86TBQPNwAo-RGrcxWyCdwKhI66AK3Pqf3ieo6HaxI&iid=MS4wLjABAAAA0ptpM-zzoliLEeyvWOCUt-_dQza4uSjlIvbtIazXnCY&with_sec_did=1&use_link_command=1&ecom_share_track_params=&extra_params={"from_request_id":"20231230162057EC005772A8EAA0199906","im_channel_invite_id":"0"}&user_id=3644207898042206&liveId=7318296342189919011&from=share&style=share&enter_method=click_share&roomId=7318296342189919011&activity_info={}',
        #     "6i- Q@x.Sl 03/23 【醒子8ke的直播间】  点击打开👉https://v.douyin.com/i8tBR7hX/  或长按复制此条消息，打开抖音，看TA直播",
        #     "https://v.douyin.com/i8tBR7hX/",
        # ]
        # result = await self.get_all_webcast_id(raw_urls)
        # print(result)

        # 占位
        pass


if __name__ == "__main__":
    # 初始化
    DouyinWebCrawler = DouyinWebCrawler()

    # 开始时间
    start = time.time()

    asyncio.run(DouyinWebCrawler.main())

    # 结束时间
    end = time.time()
    print(f"耗时：{end - start}")
