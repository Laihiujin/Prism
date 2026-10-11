import asyncio
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platforms.verification import VerificationManager
from fastapi_app.cache.redis_client import get_redis


class SharedVerificationTests(unittest.TestCase):
    def test_worker_request_is_delivered_by_another_process(self):
        client = get_redis()
        try:
            client.ping()
        except Exception:
            self.skipTest("Redis is unavailable")
        manager = VerificationManager(client)
        manager.prefix = "prism:verification:test:" + str(uuid.uuid4()) + ":"
        event = manager.request_verification("fixture-account", 3)
        try:
            self.assertEqual(manager.get_pending_events()[0]["id"], event["id"])
            child = '''import sys
from platforms.verification import VerificationManager
m=VerificationManager();m.prefix=sys.argv[1]
assert m.submit_code(sys.argv[2], '864209')
assert not m.submit_code(sys.argv[2], '864209')
'''
            subprocess.run([sys.executable, "-c", child, manager.prefix, event["id"]], check=True, capture_output=True)
            self.assertEqual(asyncio.run(manager.wait_for_code(event["id"], timeout=2)), "864209")
            self.assertEqual(manager.get_pending_events(), [])
            self.assertFalse(manager.submit_code(event["id"], "864209"))
        finally:
            keys = list(client.scan_iter(manager.prefix + "*"))
            if keys:
                client.delete(*keys)


if __name__ == "__main__":
    unittest.main()
