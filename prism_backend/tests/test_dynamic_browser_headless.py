import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import conf
from automation_worker import worker
from fastapi_app.api.v1.system import router as system
from app_new.platforms.base import QRCodeData


class DynamicBrowserTests(unittest.TestCase):
    def test_cms_change_controls_next_login_without_restart(self):
        async def scenario(root):
            modes = []
            ids = []
            class Adapter:
                def __init__(self, config):
                    modes.append(config['headless'])
                async def get_qrcode(self):
                    sid = f'dynamic-mode-{len(modes)}'
                    ids.append(sid)
                    return QRCodeData(sid, 'fixture', 'fixture')
                async def cleanup_session(self, sid):
                    pass
            try:
                with patch.object(conf, '_root_env', root / '.env'), patch.object(system, '_repo_root', return_value=root), patch.object(worker, 'DouyinAdapter', Adapter):
                    for mode in (False, True, False):
                        response = await system.set_browser_headless(mode)
                        self.assertFalse(response['restart_required'])
                        self.assertEqual(conf.get_playwright_headless(), mode)
                        self.assertEqual(worker._env_bool('PLAYWRIGHT_HEADLESS', True), mode)
                        await worker.generate_qrcode('douyin', f'fixture-{len(modes)}')
                    self.assertEqual(modes, [False, True, False])
            finally:
                for sid in ids:
                    worker.sessions.pop(sid, None)
        with tempfile.TemporaryDirectory() as temporary:
            asyncio.run(scenario(Path(temporary)))


if __name__ == '__main__':
    unittest.main()
