import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi import FastAPI
from patchright.async_api import async_playwright
from automation_worker import worker
from automation_worker.client import AutomationWorkerClient
from fastapi_app.api.v1.auth import router as auth

class RemoteLoginTests(unittest.TestCase):
    def test_headless_viewport_and_ordered_pointer_through_api(self):
        async def run():
            async with async_playwright() as p:
                browser = await p.chromium.launch(channel='chrome', headless=True)
                page = await browser.new_page(viewport={'width': 800, 'height': 600})
                await page.set_content('''<style>body{margin:0}</style><div style="width:800px;height:600px;background:#eee">Manual pointer fixture</div>
                <script>window.events=[]; for(const type of ['mousedown','mousemove','mouseup'])document.addEventListener(type,e=>{events.push({type,x:e.clientX,y:e.clientY});document.body.dataset.events=JSON.stringify(events)});</script>''')
                sid = 'remote-fixture-worker'
                public = 'remote-fixture-api'
                worker.sessions[sid] = {'adapter': SimpleNamespace(page=page), 'platform': 'kuaishou', 'type': 'sms', 'created_at': asyncio.get_running_loop().time()}
                auth.login_sessions[public] = {'worker_session_id': sid}
                client = AutomationWorkerClient()
                await client.client.aclose()
                client.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=worker.app), base_url='http://worker')
                app = FastAPI(); app.include_router(auth.router, prefix='/api/v1')
                try:
                    with patch('automation_worker.client.get_worker_client', return_value=client):
                        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://api') as api:
                            frame = await api.get(f'/api/v1/auth/qrcode/view/{public}')
                            self.assertEqual(frame.status_code, 200)
                            self.assertEqual(frame.json()['width'], 800)
                            self.assertTrue(frame.json()['image'].startswith('data:image/jpeg;base64,'))
                            for action, x in [('down', .25), ('move', .5), ('up', .75)]:
                                response = await api.post(f'/api/v1/auth/qrcode/pointer/{public}', json={'action': action, 'x': x, 'y': .5})
                                self.assertEqual(response.status_code, 200)
                            events = await page.evaluate('JSON.parse(document.body.dataset.events)')
                            self.assertEqual([event['type'] for event in events if event['type'] != 'mousemove'], ['mousedown','mouseup'])
                            self.assertAlmostEqual(events[-1]['x'], 599, delta=1)
                            self.assertFalse(worker.sessions[sid]['pointer_down'])
                            invalid = await api.post(f'/api/v1/auth/qrcode/pointer/{public}', json={'action':'move','x':2,'y':0})
                            self.assertEqual(invalid.status_code, 422)
                            self.assertEqual((await api.get('/api/v1/auth/qrcode/view/other-session')).status_code, 404)
                            worker.sessions[sid]['created_at'] -= 601
                            self.assertEqual((await api.get(f'/api/v1/auth/qrcode/view/{public}')).status_code, 410)
                finally:
                    worker.sessions.pop(sid,None); auth.login_sessions.pop(public,None)
                    await client.client.aclose(); await browser.close()
        asyncio.run(run())

if __name__ == '__main__':
    unittest.main()
