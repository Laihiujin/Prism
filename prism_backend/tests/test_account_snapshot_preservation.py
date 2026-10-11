import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from myUtils.cookie_manager import CookieManager

class AccountSnapshotPreservationTests(unittest.TestCase):
    def test_stale_client_and_saved_snapshot_preserve_new_login(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = CookieManager.__new__(CookieManager)
            manager.db_path = root / "accounts.db"
            manager.cookies_dir = root / "cookiesFile"
            manager.cookies_dir.mkdir()
            manager.frontend_snapshot_path = root / "snapshot.json"
            cookie = manager.cookies_dir / "fixture.json"
            cookie.write_text('{"cookies": []}', encoding="utf-8")
            with closing(sqlite3.connect(manager.db_path)) as connection:
                connection.execute("CREATE TABLE cookie_accounts (account_id TEXT, platform TEXT, user_id TEXT, cookie_file TEXT)")
                connection.execute("INSERT INTO cookie_accounts VALUES ('new-login', 'douyin', '123', 'fixture.json')")
                connection.commit()
            stale = [{"account_id": "old-login", "platform": "douyin"}]
            manager.save_frontend_snapshot(stale)
            for result in (manager.prune_accounts_not_in_frontend(stale), manager.prune_accounts_from_snapshot()):
                self.assertEqual(result["removed"], 0)
            with closing(sqlite3.connect(manager.db_path)) as connection:
                self.assertEqual(connection.execute("SELECT account_id FROM cookie_accounts").fetchall(), [("new-login",)])
            self.assertTrue(cookie.exists())

if __name__ == "__main__":
    unittest.main()
