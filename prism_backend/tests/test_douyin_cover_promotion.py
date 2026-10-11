import ast
import asyncio
import logging
import unittest
from pathlib import Path
from patchright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]

def load_method(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8-sig'))
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef) and node.name == name)
    method.returns = None
    for arg in method.args.args:
        arg.annotation = None
    namespace = {'logger': logging.getLogger('cover-test'), 'douyin_logger': logging.getLogger('cover-test'),
                 'asyncio': asyncio, '_msg': lambda icon, text: text}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
    return namespace[name]

class CoverPromotionTests(unittest.IsolatedAsyncioTestCase):
    async def test_optional_promotion_preserves_cover_editor(self):
        methods = [
            (load_method('platforms/douyin/upload.py', '_dismiss_landscape_cover_tip'), {}),
            (load_method('uploader/douyin_uploader/main_refactored.py', '_handle_cover_recommend_modal'), {'want_portrait': True}),
        ]
        async with async_playwright() as runtime:
            browser = await runtime.chromium.launch(headless=True, channel='chrome')
            try:
                page = await browser.new_page()
                for method, kwargs in methods:
                    for wording in ('设置横封面获取更多流量', '设置横封面获更多流量'):
                        with self.subTest(method=method.__name__, wording=wording):
                            await page.set_content(f'<div id="editor"><button>完成</button></div><div id="tip"><h2>{wording}</h2><button onclick="document.getElementById(\'tip\').remove()">暂不设置</button><button>设置横封面</button></div>')
                            self.assertTrue(await method(None, page, **kwargs))
                            self.assertFalse(await page.locator('#tip').count())
                            self.assertTrue(await page.locator('#editor').is_visible())
                            self.assertTrue(await page.get_by_role('button', name='完成', exact=True).is_enabled())
            finally:
                await browser.close()

if __name__ == '__main__':
    unittest.main()
