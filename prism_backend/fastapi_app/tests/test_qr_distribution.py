"""Offline distribution flow tests: real persistence/routes, synthetic login and publisher."""
import asyncio
import json
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi_app.services.qr_distribution import QRDistributionService, DistributionRequest, SHANGHAI


class DistributionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = sqlite3.connect(self.root / "fixture.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE TABLE file_records(id INTEGER PRIMARY KEY, filename TEXT, file_path TEXT)")
        self.db.executemany("INSERT INTO file_records VALUES (?,?,?)", [(i, f"fixture-{i}.mp4", f"fixture-{i}.mp4") for i in (1, 2, 3)])
        self.db.commit()
        (self.root / "covers").mkdir()
        for i in (1, 2, 3):
            (self.root / "covers" / f"library_{i}.json").write_text(json.dumps({"presets": {"fixture": {"name": "Fixture", "platform": "all", "data": {"form": {"title": f"Frozen {i}", "description": "fixture", "tags": ["tag"], "cover_image": "covers/fixture.png"}}}}}))
        self.service = QRDistributionService(self.root / "fixture.db")
        self.service.ensure_runner = Mock()
        self.settings_patch = patch('fastapi_app.core.config.settings.VIDEO_FILES_DIR', str(self.root))
        self.settings_patch.start()

    async def asyncTearDown(self):
        await self.service.close()
        self.settings_patch.stop()
        self.db.close()
        self.temp.cleanup()

    def request(self, **overrides):
        return DistributionRequest(**{"name": "Fixture", "materials": [{"file_id": i, "presets": {"douyin": "fixture", "tencent": "fixture"}} for i in (1, 2, 3)],
            "platforms": ["douyin", "tencent"], "allocation": "all_per_account", **overrides})

    def create(self, **overrides):
        return self.service.create(self.request(**overrides), self.db)

    async def test_freezes_platform_presets_and_survives_restart(self):
        task = self.create()
        (self.root / "covers" / "library_1.json").unlink()
        restarted = QRDistributionService(self.root / "fixture.db")
        loaded = restarted.get(task["id"])
        self.assertEqual(loaded["materials"][0]["configurations"]["douyin"]["title"], "Frozen 1")
        self.assertFalse(loaded["config"]["auto_publish"])

    async def test_login_claim_auto_publishes_materials_and_platforms(self):
        task = self.create(auto_publish=True)
        self.service.poll_login = AsyncMock(return_value=SimpleNamespace(status="confirmed", data={"user_info": {"user_id": "fixture-user"}}))
        self.service.publish_item = AsyncMock(return_value={"success_count": 1, "tasks": [{"task_id": "fixture-task"}]})
        manager = Mock()
        manager.get_account_by_user_id.return_value = {"account_id": "fixture-account", "status": "valid"}
        with patch('myUtils.cookie_manager.cookie_manager', manager):
            for platform, lane in task["lanes"].items():
                lane.update(session_id=f"fixture-{platform}", account_alias="fixture-alias")
                await self.service.tick_lane(task, platform, lane)
        self.assertEqual(len(task["packages"]), 2)
        self.assertEqual(self.service.publish_item.await_count, 6)
        self.assertTrue(all(lane["refreshes"] == [] for lane in task["lanes"].values()))
        self.assertTrue(all(i["status"] == "queued" for p in task["packages"] for i in p["items"]))
        for package in task["packages"]:
            self.assertIsNone(package["items"][0]["scheduled_time"])
            a, b = (datetime.fromisoformat(i["scheduled_time"]) for i in package["items"][1:])
            self.assertEqual((b-a).total_seconds(), 600)
        manager.get_account_by_user_id.assert_any_call("fixture-user", platform="channels")

    async def test_manual_count_schedule_frequency_and_remaining_items(self):
        task = self.create()
        pack = self.service.make_package(task, "douyin", "fixture-account")
        task["packages"].append(pack)
        self.service.save(task)
        future = (datetime.now(SHANGHAI) + timedelta(hours=2)).isoformat()
        schedule = {"schedule_type": "scheduled", "scheduled_time": future, "interval_seconds": 1800, "item_count": 2}
        await self.service.action(task["id"], "configure", package_id=pack["id"], schedule=schedule)
        self.service.publish_item = AsyncMock(return_value={"success_count": 1})
        saved = self.service.get(task["id"])["packages"][0]
        self.assertTrue(all(i["status"] == "ready" for i in saved["items"]))
        await self.service.action(task["id"], "publish", package_id=pack["id"], schedule=schedule)
        saved = self.service.get(task["id"])["packages"][0]
        self.assertEqual([i["status"] for i in saved["items"]], ["queued", "queued", "ready"])
        self.assertEqual((datetime.fromisoformat(saved["items"][1]["scheduled_time"]) - datetime.fromisoformat(saved["items"][0]["scheduled_time"])).total_seconds(), 1800)
        await self.service.action(task["id"], "publish", package_id=pack["id"], schedule={"schedule_type": "immediate", "interval_seconds": 600, "item_count": 1})
        self.assertEqual(self.service.publish_item.await_count, 3)
        with self.assertRaises(HTTPException):
            await self.service.action(task["id"], "publish", package_id=pack["id"])

    async def test_submit_error_is_not_automatically_retried(self):
        task = self.create()
        pack = self.service.make_package(task, "douyin", "fixture-account")
        task["packages"].append(pack)
        self.service.publish_item = AsyncMock(side_effect=TimeoutError)
        await self.service.submit_package(task, pack, {"item_count": 1})
        self.assertEqual(pack["items"][0]["status"], "needs_review")
        self.assertEqual(self.service.publish_item.await_count, 1)
        self.assertEqual(len([i for i in pack["items"] if i["status"] == "ready"]), 2)

    async def test_refresh_budget_survives_failure_and_respects_cooldown(self):
        task = self.create()
        lane = task["lanes"]["douyin"]
        self.service.begin_login = AsyncMock(side_effect=RuntimeError("fixture offline"))
        with self.assertRaises(RuntimeError):
            await self.service.refresh(task, "douyin", lane)
        stored = self.service.get(task["id"])["lanes"]["douyin"]
        self.assertEqual(len(stored["refreshes"]), 1)
        with self.assertRaises(HTTPException) as caught:
            await self.service.refresh(task, "douyin", lane)
        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(self.service.begin_login.await_count, 1)
        lane.update(refreshes=[time.time()-1000] * 12, next_refresh_at=0)
        await self.service.refresh(task, "douyin", lane)
        self.assertEqual(lane["status"], "cooldown")
        self.assertEqual(self.service.begin_login.await_count, 1)

    async def test_risk_control_does_not_refresh(self):
        task = self.create()
        lane = task["lanes"]["douyin"]
        lane.update(session_id="fixture-risk", account_alias="fixture-alias")
        self.service.poll_login = AsyncMock(return_value=SimpleNamespace(status="risk_control"))
        self.service.refresh = AsyncMock()
        await self.service.tick_lane(task, "douyin", lane)
        self.service.refresh.assert_not_awaited()
        self.assertEqual(lane["session_id"], "fixture-risk")

    async def test_duplicate_account_does_not_claim_again(self):
        task = self.create(accounts_per_platform=2, allocation="one_per_account")
        task["packages"].append(self.service.make_package(task, "douyin", "fixture-account"))
        task["lanes"]["douyin"]["completed"] = 1
        lane = task["lanes"]["douyin"]
        lane.update(session_id="fixture-duplicate", account_alias="fixture-alias")
        self.service.poll_login = AsyncMock(return_value=SimpleNamespace(status="confirmed", data={"user_info": {"user_id": "fixture-user"}}))
        manager = Mock(get_account_by_user_id=Mock(return_value={"account_id": "fixture-account", "status": "valid"}))
        with patch('myUtils.cookie_manager.cookie_manager', manager):
            await self.service.tick_lane(task, "douyin", lane)
        self.assertEqual(len(task["packages"]), 1)
        self.assertEqual(lane["completed"], 1)

    async def test_lease_prevents_concurrent_process_changes(self):
        task = self.create()
        other = QRDistributionService(self.root / "fixture.db")
        self.assertFalse(other.acquire(task["id"]))
        with self.assertRaises(HTTPException) as caught:
            await other.action(task["id"], "stop")
        self.assertEqual(caught.exception.status_code, 409)

    async def test_http_create_list_and_validation(self):
        from fastapi_app.api.v1.router import api_router
        from fastapi_app.db.session import get_main_db
        app = FastAPI()
        app.include_router(api_router, prefix="/api/v1")
        app.dependency_overrides[get_main_db] = lambda: self.db
        with patch('fastapi_app.api.v1.tasks.distribution_alias.get_qr_distribution_service', return_value=self.service):
            with TestClient(app) as client:
                response = client.post('/api/v1/tasks/distribution', json=self.request().model_dump(mode="json"))
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(len(client.get('/api/v1/tasks/distribution').json()["data"]), 1)
                invalid = self.request().model_dump(mode="json")
                invalid["materials"][0]["presets"] = {}
                self.assertEqual(client.post('/api/v1/tasks/distribution', json=invalid).status_code, 422)

    async def test_mcp_discovery_and_call_use_the_shared_catalog(self):
        from fastapi_app.agent.mcp_server import _collect_tools, _call_tool, _handle_request
        tools = _collect_tools()
        listing = _handle_request("tools/list", {}, 1, tools)
        self.assertIn("qr_distribution_action", {item["name"] for item in listing["result"]["tools"]})
        client = Mock(request=AsyncMock(return_value=Mock(is_success=True, json=Mock(return_value={"success": True, "data": {"id": "fixture"}}))))
        context = Mock(__aenter__=AsyncMock(return_value=client), __aexit__=AsyncMock())
        with patch('fastapi_app.services.agent_workflow_tools.httpx.AsyncClient', return_value=context):
            response = await _call_tool(tools["qr_distribution_action"], {"task_id": "fixture", "action": "configure", "package_id": "package", "schedule": {"schedule_type": "immediate", "interval_seconds": 600, "item_count": 2}})
        self.assertFalse(response["isError"])
        self.assertEqual(client.request.call_args.kwargs["json"]["schedule"]["item_count"], 2)

    async def test_worker_restart_recovers_uncertain_completed_package(self):
        task = self.create()
        task["status"] = "completed"
        package = self.service.make_package(task, "douyin", "fixture-account")
        package["items"][0]["status"] = "submitting"
        task["packages"].append(package)
        self.service.save(task)
        await self.service.close()
        restarted = QRDistributionService(self.root / "fixture.db")
        try:
            await restarted.start()
            recovered = restarted.get(task["id"])
            self.assertEqual(recovered["packages"][0]["items"][0]["status"], "needs_review")
        finally:
            await restarted.close()

    async def test_read_platform_updated_qr_without_refresh(self):
        task = self.create()
        lane = task["lanes"]["douyin"]
        lane.update(session_id="fixture-qr-read", account_alias="fixture-alias", qr_image="old", qr_expires_at=time.time()-10, next_refresh_at=0)
        self.service.poll_login = AsyncMock(return_value=SimpleNamespace(status="waiting"))
        self.service.refresh = AsyncMock()
        client = Mock(qrcode_image=AsyncMock(return_value={"qr_image": "new"}))
        with patch('automation_worker.client.get_worker_client', return_value=client):
            await self.service.tick_lane(task, "douyin", lane)
        self.assertEqual(lane["qr_image"], "new")
        self.assertGreater(lane["qr_expires_at"], time.time())
        self.service.refresh.assert_not_awaited()

    async def test_background_runner_completes_without_frontend_polling(self):
        task = self.create(auto_publish=True)
        self.service.begin_login = AsyncMock(side_effect=lambda platform, alias, sid=None: SimpleNamespace(qr_id="fixture-background-" + platform, qr_image="fixture", expires_in=300))
        self.service.poll_login = AsyncMock(return_value=SimpleNamespace(status="confirmed", data={"user_info": {"user_id": "fixture-user"}}))
        self.service.publish_item = AsyncMock(return_value={"success_count": 1})
        manager = Mock(get_account_by_user_id=Mock(return_value={"account_id": "fixture-account", "status": "valid"}))
        with patch('myUtils.cookie_manager.cookie_manager', manager), patch('fastapi_app.services.qr_distribution.asyncio.sleep', AsyncMock()):
            await asyncio.wait_for(self.service.run(task["id"]), 2)
        completed = self.service.get(task["id"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(len(completed["packages"]), 2)
        self.assertEqual(self.service.publish_item.await_count, 6)

    async def test_agent_tools_discover_and_forward(self):
        from fastapi_app.services.agent_workflow_tools import build_workflow_tool_specs
        specs = {s.name: s for s in build_workflow_tool_specs()}
        self.assertNotIn("$ref", json.dumps(specs["create_qr_distribution"].parameters))
        self.assertTrue({"create_qr_distribution", "list_qr_distributions", "get_qr_distribution", "qr_distribution_action"} <= specs.keys())
        client = Mock(request=AsyncMock(return_value=Mock(is_success=True, json=Mock(return_value={"success": True, "data": {"id": "fixture"}}))))
        context = Mock(__aenter__=AsyncMock(return_value=client), __aexit__=AsyncMock())
        with patch('fastapi_app.services.agent_workflow_tools.httpx.AsyncClient', return_value=context):
            result = await specs["create_qr_distribution"].handler(configuration=self.request().model_dump(mode="json"))
            self.assertTrue(result["ok"])
            self.assertEqual(client.request.call_args.kwargs["json"]["name"], "Fixture")


if __name__ == '__main__':
    unittest.main()
