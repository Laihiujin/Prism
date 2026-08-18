import json
import pathlib
import random
import asyncio
from biliup.plugins.bili_webup import BiliBili, Data

from utils.log import bilibili_logger
from .cookie_refresher import refresh_bilibili_cookies, to_biliup_cookie_format


def extract_keys_from_json(data):
    """
    Normalize cookie json into biliup expected format:
      {"cookie_info":{"cookies":[{"name","value",...}, ...]}, "token_info":{"access_token": "..."}}
    """
    return to_biliup_cookie_format(data)


def cookie_dict_for_biliup(cookie_data):
    """
    Convert nested cookie format to flat dict for biliup's login_by_cookies
    Input: {"cookie_info": {"cookies": [{"name": "X", "value": "Y"}, ...]}}
    Output: {"X": "Y", ...}
    """
    result = {}
    if isinstance(cookie_data, dict):
        # Handle nested format
        if "cookie_info" in cookie_data and isinstance(cookie_data["cookie_info"], dict):
            cookies_list = cookie_data["cookie_info"].get("cookies", [])
            if isinstance(cookies_list, list):
                for cookie in cookies_list:
                    if isinstance(cookie, dict):
                        name = cookie.get("name")
                        value = cookie.get("value")
                        if name and value is not None:
                            # Ensure value is string
                            result[name] = str(value) if not isinstance(value, str) else value
        # Handle flat format
        elif "cookies" in cookie_data and isinstance(cookie_data["cookies"], list):
            for cookie in cookie_data["cookies"]:
                if isinstance(cookie, dict):
                    name = cookie.get("name")
                    value = cookie.get("value")
                    if name and value is not None:
                        result[name] = str(value) if not isinstance(value, str) else value
        # Handle direct key-value format
        else:
            for key, value in cookie_data.items():
                if value is not None and key not in ["token_info", "cookie_info"]:
                    result[key] = str(value) if not isinstance(value, str) else value
    return result


def read_cookie_json_file(filepath: pathlib.Path):
    with open(filepath, 'r', encoding='utf-8') as file:
        content = json.load(file)
        return content


def random_emoji():
    emoji_list = ["🍏", "🍎", "🍊", "🍋", "🍌", "🍉", "🍇", "🍓", "🍈", "🍒", "🍑", "🍍", "🥭", "🥥", "🥝",
                  "🍅", "🍆", "🥑", "🥦", "🥒", "🥬", "🌶", "🌽", "🥕", "🥔", "🍠", "🥐", "🍞", "🥖", "🥨", "🥯", "🧀", "🥚", "🍳", "🥞",
                  "🥓", "🥩", "🍗", "🍖", "🌭", "🍔", "🍟", "🍕", "🥪", "🥙", "🌮", "🌯", "🥗", "🥘", "🥫", "🍝", "🍜", "🍲", "🍛", "🍣",
                  "🍱", "🥟", "🍤", "🍙", "🍚", "🍘", "🍥", "🥮", "🥠", "🍢", "🍡", "🍧", "🍨", "🍦", "🥧", "🍰", "🎂", "🍮", "🍭", "🍬",
                  "🍫", "🍿", "🧂", "🍩", "🍪", "🌰", "🥜", "🍯", "🥛", "🍼", "☕️", "🍵", "🥤", "🍶", "🍻", "🥂", "🍷", "🥃", "🍸", "🍹",
                  "🍾", "🥄", "🍴", "🍽", "🥣", "🥡", "🥢"]
    return random.choice(emoji_list)


class BilibiliUploader(object):
    def __init__(self, cookie_data, file: pathlib.Path, title, desc, tid, tags, dtime, proxy=None):
        self.upload_thread_num = 3
        self.copyright = 1
        self.lines = 'AUTO'
        self.cookie_data = cookie_data
        self.file = file
        self.title = title
        self.desc = desc
        self.tid = tid
        self.tags = tags
        self.dtime = dtime
        self.proxy = proxy
        self._init_data()

    def _init_data(self):
        self.data = Data()
        self.data.copyright = self.copyright
        self.data.title = self.title
        self.data.desc = self.desc
        self.data.tid = self.tid
        self.data.set_tag(self.tags)
        self.data.dtime = self.dtime

    def upload(self):
        import sys
        import os
        from contextlib import redirect_stdout, redirect_stderr

        # 先通过浏览器刷新 Cookie（获取最完整的认证信息）
        bilibili_logger.info('[+] 准备刷新 Bilibili Cookie...')
        try:
            # 使用 asyncio 运行异步刷新函数
            refreshed_cookie_data = asyncio.run(refresh_bilibili_cookies(self.cookie_data, proxy=self.proxy))

            # 检查刷新后的 Cookie 是否更好
            refreshed_count = len((refreshed_cookie_data.get("cookie_info") or {}).get("cookies") or [])
            original_count = len((self.cookie_data.get("cookie_info") or {}).get("cookies") or [])
            if refreshed_count >= original_count:
                bilibili_logger.success(f'[+] Cookie 刷新成功，获得 {refreshed_count} 个 Cookie')
                self.cookie_data = refreshed_cookie_data
            else:
                bilibili_logger.warning('[+] Cookie 刷新后数量减少，保留原 Cookie')
        except Exception as e:
            bilibili_logger.warning(f'[+] Cookie 刷新失败: {e}，将使用原 Cookie')

        # 抑制 biliup 库的标准输出（防止终端轮询日志爆炸）
        # 创建一个空的输出目标
        # Create a devnull sink for biliup stdout/stderr.
        devnull = open(os.devnull, 'w')

        try:
            with redirect_stdout(devnull), redirect_stderr(devnull):
                with BiliBili(self.data) as bili:
                    # 使用 login_by_cookies 登录
                    cookie_payload = self.cookie_data
                    if not isinstance(cookie_payload, dict) or "cookie_info" not in cookie_payload:
                        cookie_payload = to_biliup_cookie_format(cookie_payload or {})
                    bili.login_by_cookies(cookie_payload)
                    bilibili_logger.info('[+] 使用 Cookie 登录成功')

                    # 尝试获取 access_token
                    if not bili.access_token:
                        bili.access_token = (self.cookie_data.get("token_info") or {}).get("access_token") or ""

                    bilibili_logger.info(f"[+] Cookie cookies count: {len((self.cookie_data.get('cookie_info') or {}).get('cookies') or [])}")
                    bilibili_logger.info(f'[+] Access Token present: {bool(bili.access_token)}')

                    # 如果 access_token 仍为空，尝试设置为空字符串，以防 biliup 检查 None
                    if bili.access_token is None:
                        bilibili_logger.warning('[+] Access Token is None, setting to empty string to try Web upload')
                        bili.access_token = ''

                    # 上传视频
                    video_part = bili.upload_file(str(self.file), lines=self.lines, tasks=self.upload_thread_num)
                    video_part['title'] = self.title
                    self.data.append(video_part)

                    # 提交视频
                    ret = bili.submit()
                    if ret.get('code') == 0:
                        bilibili_logger.success(f'[+] {self.file.name}上传 成功')
                        return True

                    bilibili_logger.error(f'[-] {self.file.name}上传 失败: {ret}')
                    raise RuntimeError(f"Bilibili submit failed: {ret}")
        except Exception as e:
            bilibili_logger.error(f'[-] {self.file.name}上传 异常: {e}')
            raise
        finally:
            devnull.close()
