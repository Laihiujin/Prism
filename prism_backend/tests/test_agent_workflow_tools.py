import asyncio
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi_app.services.agent_workflow_tools import build_workflow_tool_specs
from fastapi_app.agent import mcp_server


class WorkflowToolsTests(unittest.TestCase):
    def setUp(self):
        self.specs = {spec.name: spec for spec in build_workflow_tool_specs()}

    def test_all_workflows_are_discoverable_in_mcp_and_cli_catalog(self):
        from fastapi_app.services.tool_catalog import all_tools
        catalog = {spec.name for spec in all_tools()}
        mcp = mcp_server._collect_tools()
        self.assertTrue(set(self.specs) <= catalog)
        self.assertTrue(set(self.specs) <= set(mcp))
        self.assertTrue(all(mcp[name]['inputSchema']['additionalProperties'] is False for name in self.specs))

    def test_mcp_calls_correct_bound_catalog_handler(self):
        async def scenario():
            tools = mcp_server._collect_tools()
            response = httpx.Response(200, json={'events': []})
            with patch('httpx.AsyncClient.request', AsyncMock(return_value=response)) as request:
                result = await mcp_server._call_tool(tools['list_publish_verifications'], {})
            self.assertFalse(result['isError'])
            self.assertEqual(request.await_args.args, ('GET', '/api/v1/verification/otp-events'))
            self.assertEqual(json.loads(result['content'][0]['text'])['data'], {'events': []})
        asyncio.run(scenario())

    def test_cover_jobs_use_form_encoding_and_status_uses_job_id(self):
        async def scenario():
            response = httpx.Response(200, json={'success': True, 'data': {'job_id': 'fixture'}})
            with patch('httpx.AsyncClient.request', AsyncMock(return_value=response)) as request:
                await self.specs['generate_cover'].handler(file_id=3, prompt='fixture')
                self.assertEqual(request.await_args.args, ('POST', '/api/v1/files/3/ai-cover-job'))
                self.assertEqual(request.await_args.kwargs, {'data': {'prompt': 'fixture'}})
                await self.specs['get_cover_job'].handler(job_id='fixture')
                self.assertEqual(request.await_args.args, ('GET', '/api/v1/files/ai-cover-jobs/fixture'))
        asyncio.run(scenario())

    def test_validation_prevents_bad_codes_and_http_errors_mark_mcp_failure(self):
        async def scenario():
            with patch('httpx.AsyncClient.request', AsyncMock()) as request:
                with self.assertRaises(ValueError):
                    await self.specs['submit_publish_verification'].handler(account_id='fixture', code='abc')
                request.assert_not_awaited()
            tools = mcp_server._collect_tools()
            response = httpx.Response(429, json={'detail': '请稍后重试'})
            with patch('httpx.AsyncClient.request', AsyncMock(return_value=response)):
                result = await mcp_server._call_tool(tools['resend_publish_verification'], {'account_id': 'fixture'})
            self.assertTrue(result['isError'])
        asyncio.run(scenario())


if __name__ == '__main__':
    unittest.main()
