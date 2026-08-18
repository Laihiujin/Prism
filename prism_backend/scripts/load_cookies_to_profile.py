#!/usr/bin/env python3
"""
Load cookies from cookie_manager into Chrome profile.
"""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from myUtils.cookie_manager import CookieManager
from loguru import logger


def load_cookies_to_profile(account_id: str, profile_path: Path):
    """Load cookies from cookie_manager into Chrome profile."""
    cm = CookieManager()
    accounts = cm.list_flat_accounts()

    # Find account
    account = None
    for acc in accounts:
        if acc.get('account_id') == account_id:
            account = acc
            break

    if not account:
        logger.error(f"Account {account_id} not found")
        return False

    platform = account['platform']
    cookie_file = account.get('cookie_file')

    if not cookie_file:
        logger.error(f"No cookie file for account {account_id}")
        return False

    # Load cookies
    cookie_path = Path("db/cookies") / cookie_file
    if not cookie_path.exists():
        logger.error(f"Cookie file not found: {cookie_path}")
        return False

    with open(cookie_path, 'r', encoding='utf-8') as f:
        cookies = json.load(f)

    logger.info(f"Loaded {len(cookies)} cookies from {cookie_file}")

    # Chrome cookies database path
    cookies_db = profile_path / "Default" / "Cookies"

    if not cookies_db.exists():
        logger.error(f"Chrome cookies database not found: {cookies_db}")
        logger.info("Profile might not have been initialized. Starting Chrome first...")
        return False

    # Connect to Chrome cookies database
    try:
        conn = sqlite3.connect(str(cookies_db))
        cursor = conn.cursor()

        # Clear existing cookies for this domain
        domains = set()
        for cookie in cookies:
            domain = cookie.get('domain', '')
            if domain:
                domains.add(domain)

        for domain in domains:
            cursor.execute("DELETE FROM cookies WHERE host_key = ?", (domain,))
            cursor.execute("DELETE FROM cookies WHERE host_key = ?", ('.' + domain.lstrip('.'),))

        logger.info(f"Cleared cookies for domains: {domains}")

        # Insert cookies
        inserted = 0
        for cookie in cookies:
            name = cookie.get('name')
            value = cookie.get('value')
            domain = cookie.get('domain', '')
            path = cookie.get('path', '/')
            secure = 1 if cookie.get('secure', False) else 0
            httponly = 1 if cookie.get('httpOnly', False) else 0

            # Convert expiry
            expires_utc = 0
            if 'expirationDate' in cookie:
                # Chrome uses Windows epoch (1601-01-01), Unix uses 1970-01-01
                # Conversion: add 11644473600 seconds then multiply by 1000000 for microseconds
                unix_timestamp = cookie['expirationDate']
                chrome_timestamp = int((unix_timestamp + 11644473600) * 1000000)
                expires_utc = chrome_timestamp

            # Insert cookie
            cursor.execute("""
                INSERT INTO cookies (
                    creation_utc, host_key, top_frame_site_key, name, value,
                    encrypted_value, path, expires_utc, is_secure, is_httponly,
                    samesite, priority, source_scheme, is_persistent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(datetime.now(timezone.utc).timestamp() * 1000000),  # creation_utc
                domain,  # host_key
                "",  # top_frame_site_key
                name,  # name
                value,  # value
                b"",  # encrypted_value
                path,  # path
                expires_utc,  # expires_utc
                secure,  # is_secure
                httponly,  # is_httponly
                0,  # samesite (0=no_restriction)
                1,  # priority (1=medium)
                2,  # source_scheme (2=secure)
                1 if expires_utc > 0 else 0,  # is_persistent
            ))
            inserted += 1

        conn.commit()
        conn.close()

        logger.success(f"Successfully imported {inserted} cookies into Chrome profile")
        return True

    except Exception as e:
        logger.error(f"Failed to import cookies: {e}")
        return False


if __name__ == "__main__":
    account_id = "account_1767153564266"
    profile_path = Path("browser_profiles/xiaohongshu_account_1767153564266")

    logger.info(f"Loading cookies for {account_id} into {profile_path}")
    success = load_cookies_to_profile(account_id, profile_path)

    sys.exit(0 if success else 1)
