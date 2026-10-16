import json
import pathlib
import random
import asyncio
import aiohttp
from dataclasses import dataclass
from biliup.plugins.bili_webup import BiliBili as BaseBiliBili, Data as BaseData
from uploader.bilibili_uploader.line_probe import probe_upload_lines


@dataclass
class Data(BaseData):
    """biliup `Data` plus the submission fields biliup-rs `Studio` sends.

    python biliup 1.2.x only declares a subset of the archive fields, so
    asdict() silently dropped options like no_reprint. Declaring them here puts
    them into the submit payload with the same names and defaults as biliup-rs.
    """
    no_reprint: int = 0
    is_only_self: int = 0
    dolby: int = 0
    lossless_music: int = 0
    # up_selection_reply / up_close_reply / up_close_danmu are left out: a test
    # submission through the web API (BV1P3Jt6MEYE) kept comments open, matching
    # biliup-rs' note that they only apply via the app submit API.


# Archive options accepted from platform settings, mapped to Data fields.
STUDIO_FLAG_FIELDS = {
    "no_reprint": int,
    "is_only_self": int,
    "dolby": int,
    "lossless_music": int,
}


class BiliBili(BaseBiliBili):
    def probe(self):
        return probe_upload_lines(self._BiliBili__session)

    @staticmethod
    async def _upload(params, file, chunk_size, afunc, tasks=3):
        completed = set()
        failures = {}

        async def tracked_upload(session, data, chunk):
            index = chunk['chunk']
            try:
                await afunc(session, data, chunk)
            except Exception as exc:
                failures[index] = type(exc).__name__
                raise
            completed.add(index)

        # Use the system resolver: aiodns can fail on Windows even when the
        # same upload host resolves successfully through requests/socket.
        next_chunk = 0

        async def worker(session):
            nonlocal next_chunk
            while True:
                data = file.read(chunk_size)
                if not data:
                    return
                index = next_chunk
                next_chunk += 1
                chunk = dict(params, chunk=index, size=len(data), partNumber=index + 1,
                             start=index * chunk_size, end=index * chunk_size + len(data))
                for attempt in range(10):
                    try:
                        await tracked_upload(session, data, chunk)
                        break
                    except (asyncio.TimeoutError, aiohttp.ClientError):
                        if attempt < 9:
                            await asyncio.sleep(min(attempt + 1, 3))

        connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
        async with aiohttp.ClientSession(connector=connector, trust_env=True,
                                        timeout=aiohttp.ClientTimeout(total=120)) as session:
            await asyncio.gather(*(worker(session) for _ in range(max(1, tasks))))
        missing = sorted(set(range(params['chunks'])) - completed)
        if missing:
            details = ', '.join(f'{index + 1}: {failures.get(index, "未完成")}' for index in missing)
            raise RuntimeError(f'B站分片上传重试耗尽，停止合并；失败分片：{details}')


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
    def __init__(self, cookie_data, file: pathlib.Path, title, desc, tid, tags, dtime, proxy=None,
                 files=None, part_titles=None, extra=None):
        """
        B站稿件上传器（支持单视频与分P/多P）。

        Args:
            cookie_data: Prism cookie json
            file: 主视频路径（兼容单文件调用）
            title: 稿件主标题
            desc: 简介
            tid: 分区 ID
            tags: 标签列表
            dtime: 定时发布时间（10位秒时间戳）
            proxy: 可选代理
            files: 分P文件列表（若提供，file 视为 P1，其余依次为 P2..Pn）
            part_titles: 各分P标题（缺省使用统一 title）
            extra: 稿件级附加配置 dict，key 与 biliup Data 声明字段同名：
                   copyright(1自制/2转载), source, cover(URL 或 cover_local 本地图),
                   dynamic, desc_v2, subtitle/open_subtitle，以及与 biliup-rs
                   Studio 同名的 no_reprint/is_only_self/dolby/lossless_music。
        """
        self.upload_thread_num = 3
        self.copyright = 1
        self.lines = 'AUTO'
        self.cookie_data = cookie_data
        self.file = file
        self.files = files or []
        self.part_titles = part_titles or []
        self.extra = extra or {}
        self.title = title
        self.desc = desc
        self.tid = tid
        self.tags = tags
        self.dtime = dtime
        self.proxy = proxy
        self._init_data()

    def _init_data(self):
        self.data = Data()
        self.data.title = self.title[:80]
        # 稿件级字段：版权 / 来源 / 封面 / 简介富文本 / 粉丝动态
        # 只设置本文件 Data 声明过、submit 会随 asdict 提交的字段。
        extra = self.extra or {}
        copyright_val = extra.get("copyright", self.copyright)
        self.data.copyright = int(copyright_val) if copyright_val else 2
        self.data.source = str(extra.get("source") or "")
        if extra.get("cover"):
            self.data.cover = str(extra["cover"])
        self.data.desc = self.desc
        self.data.dynamic = str(extra.get("dynamic") or "")
        if isinstance(extra.get("desc_v2"), list):
            self.data.desc_v2 = extra["desc_v2"]
        if isinstance(extra.get("subtitle"), dict):
            self.data.subtitle = extra["subtitle"]
        elif extra.get("open_subtitle") is not None:
            self.data.subtitle = {"open": int(bool(extra["open_subtitle"])), "lan": ""}
        for name, cast in STUDIO_FLAG_FIELDS.items():
            if extra.get(name) is not None:
                setattr(self.data, name, cast(extra[name]))
        if self.data.copyright != 1:
            self.data.no_reprint = 0  # 禁止转载仅对自制稿件有效
        self.data.tid = int(self.tid) if str(self.tid).isdigit() else self.tid
        self.data.set_tag(self.tags or [])
        if self.dtime:
            self.data.delay_time(int(self.dtime))

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
        devnull = open(os.devnull, 'w', encoding='utf-8', errors='backslashreplace')

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

                    # 本地封面：上传拿 URL（biliup cover_up 会裁剪为 16:10）
                    cover_local = (self.extra or {}).get("cover_local") or ""
                    if cover_local and os.path.isfile(str(cover_local)):
                        try:
                            self.data.cover = bili.cover_up(str(cover_local))
                            bilibili_logger.success(f'[+] 本地封面上传成功: {self.data.cover}')
                        except Exception as e:
                            raise RuntimeError('B站封面上传失败，已停止投稿') from e

                    # 组装分P：主文件 + files 列表（顺序 = P1..Pn）
                    part_paths = [self.file]
                    if self.files:
                        part_paths.extend(self.files)
                    part_paths = [p for p in part_paths if p and os.path.isfile(str(p))]
                    if not part_paths:
                        raise FileNotFoundError(f"没有可上传的视频文件: {self.file}")

                    is_multipart = len(part_paths) > 1
                    for idx, path in enumerate(part_paths):
                        bilibili_logger.info(f'[+] 上传分P {idx + 1}/{len(part_paths)}: {path}')
                        upload_diagnostics = []
                        def record_upload_response(response, *args, **kwargs):
                            if "bilivideo.com" in response.url and response.request.method == "POST":
                                try:
                                    payload = response.json()
                                    details = {key: payload[key] for key in ("code", "message", "msg", "OK") if key in payload}
                                except ValueError:
                                    details = {"message": "非JSON响应"}
                                upload_diagnostics.append({"http_status": response.status_code, **details})
                                del upload_diagnostics[:-6]
                            return response
                        session = bili._BiliBili__session
                        session.hooks.setdefault("response", []).append(record_upload_response)
                        try:
                            video_part = bili.upload_file(str(path), lines=self.lines, tasks=self.upload_thread_num)
                        finally:
                            session.hooks["response"].remove(record_upload_response)
                        if not isinstance(video_part, dict):
                            raise RuntimeError(f"B站分片上传/合并失败，未获得视频信息；接口诊断：{json.dumps(upload_diagnostics, ensure_ascii=False)}")
                        part_title = ""
                        if is_multipart:
                            part_title = (self.part_titles[idx] if idx < len(self.part_titles) else "") or ""
                        if not part_title:
                            part_title = (self.title if not is_multipart else f"{self.title} P{idx + 1}")
                        video_part['title'] = part_title
                        self.data.append(video_part)

                    execution_id = (self.extra or {}).get("_execution_task_id")
                    if execution_id:
                        from fastapi_app.tasks.task_state_manager import task_state_manager
                        if (task_state_manager.get_task_state(execution_id) or {}).get("status") == "cancelled":
                            raise RuntimeError("任务已取消，停止向B站提交稿件")
                    # 提交视频
                    ret = bili.submit()
                    if ret.get('code') == 0:
                        bilibili_logger.success(f'[+] {len(part_paths)}个分P上传 成功: {self.title}')
                        return True

                    bilibili_logger.error(f'[-] {self.title}上传 失败: {ret}')
                    raise RuntimeError(f"Bilibili submit failed: {ret}")
        except Exception as e:
            bilibili_logger.error(f'[-] {self.title}上传 异常: {e}')
            raise
        finally:
            devnull.close()
