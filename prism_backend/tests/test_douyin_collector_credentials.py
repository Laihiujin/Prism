import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "douyin_tiktok_api"))
from crawlers.douyin.web import web_crawler


class CredentialsTests(unittest.IsolatedAsyncioTestCase):
    async def test_account_cookies_are_isolated_and_token_is_signed(self):
        first, second = web_crawler.DouyinWebCrawler(), web_crawler.DouyinWebCrawler()
        await first.set_account_cookie("sessionid=first; msToken=token-one")
        await second.set_account_cookie("sessionid=second; msToken=token-two")
        original = web_crawler.config["TokenManager"]["douyin"]["headers"]["Cookie"]
        self.assertEqual((await first.get_douyin_headers())["headers"]["Cookie"], "sessionid=first; msToken=token-one")
        self.assertEqual((await second.get_douyin_headers())["headers"]["Cookie"], "sessionid=second; msToken=token-two")
        self.assertEqual(web_crawler.config["TokenManager"]["douyin"]["headers"]["Cookie"], original)
        seen = []
        class Transport:
            def __init__(self, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def fetch_get_json(self, endpoint):
                seen.append(parse_qs(urlsplit(endpoint).query))
                return {"status_code": 0, "aweme_list": []}
        with patch.object(web_crawler, "BaseCrawler", Transport), patch.object(web_crawler.BogusManager, "ab_model_2_endpoint", return_value="signature") as sign:
            await first.fetch_user_post_videos("user", 0, 20)
            self.assertEqual(sign.call_args.args[0]["msToken"], "token-one")
            self.assertEqual(seen[0]["msToken"], ["token-one"])


if __name__ == "__main__":
    unittest.main()
