import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys
import os
from loguru import logger

# 添加父目录到 Python 路径
sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

# Define BASE_DIR locally
BASE_DIR = Path(__file__).parent.parent


def _is_dev_repo(base_dir: Path) -> bool:
    env = (os.getenv("SYNAPSE_ENV") or os.getenv("NODE_ENV") or "").strip().lower()
    if env in ("dev", "development", "local"):
        return True
    try:
        return (base_dir.parent / ".git").exists()
    except Exception:
        return False


def _resolve_data_dir() -> Path:
    env_dir = os.getenv("SYNAPSE_DATA_DIR")
    if env_dir:
        return Path(env_dir)

    if _is_dev_repo(BASE_DIR):
        return BASE_DIR

    candidates = []
    appdata = os.getenv("APPDATA")
    local_root = os.getenv("LOCALAPPDATA")
    if appdata:
        candidates.append(Path(appdata) / "SynapseAutomation" / "data")
    if local_root and local_root != appdata:
        candidates.append(Path(local_root) / "SynapseAutomation" / "data")

    for candidate in candidates:
        if (candidate / "cookiesFile").exists() or (candidate / "db").exists():
            return candidate

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return BASE_DIR


PLATFORM_CODES = {
    "xiaohongshu": 1,
    "channels": 2,
    "douyin": 3,
    "kuaishou": 4,
    "bilibili": 5,
}
CODE_TO_PLATFORM = {value: key for key, value in PLATFORM_CODES.items()}


class CookieManager:
    def __init__(self, storage_path: Optional[Path] = None):
        # 优先使用 settings，否则使用 _resolve_data_dir() 动态解析数据目录
        data_dir = None
        try:
            from fastapi_app.core.config import settings
            data_dir = Path(settings.DATA_DIR)
            self.cookies_dir = Path(settings.COOKIE_FILES_DIR)
        except Exception:
            data_dir = _resolve_data_dir()
            self.cookies_dir = data_dir / "cookiesFile"

        # 数据库路径也使用动态解析，不再硬编码 BASE_DIR
        if storage_path:
            self.db_path = Path(storage_path)
        else:
            try:
                from fastapi_app.core.config import settings
                self.db_path = Path(settings.COOKIE_DB_PATH)
            except Exception:
                self.db_path = data_dir / "db" / "cookie_store.db"

        self.frontend_snapshot_path = data_dir / "db" / "frontend_accounts_snapshot.json"

        # 确保目录存在
        self.cookies_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.frontend_snapshot_path.parent.mkdir(parents=True, exist_ok=True)

        self.lock = threading.Lock()
        self._ensure_database()
        self._migrate_legacy_json()
        try:
            self.reconcile_missing_user_ids()
        except Exception as exc:
            logger.warning(f"[CookieManager] reconcile_missing_user_ids failed: {exc}")

    def _resolve_cookie_path(self, cookie_file: str) -> Path:
        if not cookie_file:
            return self.cookies_dir / ""
        raw = Path(cookie_file)
        if raw.is_absolute() and raw.exists():
            return raw
        candidate = self.cookies_dir / cookie_file
        if candidate.exists():
            return candidate
        return self.cookies_dir / raw.name

    def _normalize_cookie_ref(self, cookie_file: str) -> str:
        if not cookie_file:
            return ""
        raw = Path(cookie_file)
        if raw.is_absolute():
            try:
                return raw.relative_to(self.cookies_dir).as_posix()
            except Exception:
                return raw.name
        cookie_str = str(cookie_file).replace("\\", "/")
        marker = "/cookiesFile/"
        if marker in cookie_str:
            return cookie_str.split(marker, 1)[1]
        return cookie_str

    def ensure_cookie_file(self, account: Dict[str, Any]) -> Optional[str]:
        """
        Ensure cookie file exists and normalized to platform_user_id naming.
        Returns the normalized cookie filename when found.
        """
        platform = (account.get("platform") or "").strip().lower()
        user_id = account.get("user_id")
        account_id = account.get("account_id") or account.get("id")
        cookie_file = account.get("cookie_file") or account.get("cookieFile")

        if not platform or not user_id:
            return None

        candidates = []
        if cookie_file:
            candidates.append(cookie_file)
        candidates.append(self._build_cookie_filename(platform, user_id))
        # Legacy names for migration only (will rename to platform_user_id).
        if account_id:
            candidates.append(f"{platform}_{account_id}.json")
            candidates.append(f"{account_id}.json")

        for candidate in candidates:
            resolved = self._resolve_cookie_path(candidate)
            if not resolved:
                continue
            path = Path(resolved)
            if not path.exists():
                continue

            expected = self._build_cookie_filename(platform, user_id)
            expected_path = self.cookies_dir / expected
            if path.name != expected:
                try:
                    if not expected_path.exists():
                        import shutil
                        shutil.move(str(path), str(expected_path))
                        path = expected_path
                except Exception:
                    pass
                candidate = expected

            if candidate != cookie_file:
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute(
                            "UPDATE cookie_accounts SET cookie_file = ? WHERE account_id = ?",
                            (Path(candidate).name, account_id),
                        )
                        conn.commit()
                except Exception:
                    pass

            return Path(candidate).name

        return None

    def _migrate_schema(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(cookie_accounts)")
            columns = [row[1] for row in cursor.fetchall()]
            if "avatar" not in columns:
                conn.execute("ALTER TABLE cookie_accounts ADD COLUMN avatar TEXT")
            if "original_name" not in columns:
                conn.execute("ALTER TABLE cookie_accounts ADD COLUMN original_name TEXT")
            if "note" not in columns:
                conn.execute("ALTER TABLE cookie_accounts ADD COLUMN note TEXT")
            if "user_id" not in columns:
                conn.execute("ALTER TABLE cookie_accounts ADD COLUMN user_id TEXT")
            if "login_status" not in columns:
                conn.execute("ALTER TABLE cookie_accounts ADD COLUMN login_status TEXT DEFAULT 'unknown'")

    def _ensure_database(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cookie_accounts (
                    account_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    platform_code INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cookie_file TEXT NOT NULL,
                    last_checked TEXT,
                    avatar TEXT,
                    original_name TEXT,
                    note TEXT,
                    user_id TEXT
                )
                """
            )
        self._migrate_schema()

    def _migrate_legacy_json(self):
        legacy_path = Path(__file__).with_name("cookies.json")
        if not legacy_path.exists():
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(1) FROM cookie_accounts")
                count = cursor.fetchone()[0]
                if count:
                    return

            with legacy_path.open("r", encoding="utf-8") as legacy_file:
                data = json.load(legacy_file)
        except Exception:
            return

        for platform in data.get("platforms", []):
            platform_name = platform.get("name")
            for account in platform.get("accounts", []):
                try:
                    self.add_account(platform_name, account)
                except Exception:
                    continue

    def _persist_account(self, account: Dict[str, Any]):
        """将内存中的账号字典写回数据库（用于DeepSync补全）。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    UPDATE cookie_accounts
                    SET name = ?, status = ?, cookie_file = ?, last_checked = ?, avatar = ?, original_name = ?, note = ?, user_id = ?
                    WHERE account_id = ? AND platform = ?
                    """,
                    (
                        account.get("name", ""),
                        account.get("status", "expired"),
                        account.get("cookie_file", ""),
                        account.get("last_checked"),
                        account.get("avatar"),
                        account.get("original_name"),
                        account.get("note"),
                        account.get("user_id"),
                        account.get("account_id"),
                        account.get("platform"),
                    ),
                )
        except Exception as e:
            logger.warning(f"[CookieManager] 持久化账号失败 {account.get('account_id')}: {e}")

    def _write_cookie_file(self, cookie_file: str, payload: Any):
        target = self.cookies_dir / cookie_file
        target.parent.mkdir(parents=True, exist_ok=True)
        data = payload
        if isinstance(payload, str):
            try:
                json.loads(payload)
            except json.JSONDecodeError:
                data = {"raw": payload}
        with target.open("w", encoding="utf-8") as fp:
            if isinstance(data, str):
                fp.write(data)
            else:
                json.dump(data, fp, ensure_ascii=False, indent=2)

    def _read_cookie_file(self, cookie_file: str) -> Dict[str, Any]:
        target = self.cookies_dir / cookie_file
        if not target.exists():
            return {}
        try:
            with target.open("r", encoding="utf-8") as fp:
                return json.load(fp)
        except Exception:
            return {}

    def _normalize_platform(self, platform_name: str) -> str:
        return (platform_name or "").strip().lower()

    def _infer_user_id_from_filename(self, platform: str, cookie_file: str) -> Optional[str]:
        if not platform or not cookie_file:
            return None
        name = Path(cookie_file).name
        prefix = f"{platform}_"
        if not name.startswith(prefix) or not name.endswith(".json"):
            return None
        suffix = name[len(prefix):-5]
        if not suffix or suffix.startswith("account_") or suffix.startswith("pending_"):
            return None
        return suffix

    def _infer_user_id(self, platform: str, cookie_file: str) -> Optional[str]:
        inferred = self._infer_user_id_from_filename(platform, cookie_file)
        if inferred:
            return inferred
        data = self._read_cookie_file(cookie_file)
        if data:
            extracted = self._extract_user_info_from_cookie(platform, data)
            if extracted.get("user_id"):
                return str(extracted["user_id"])
        return None

    def reconcile_missing_user_ids(self) -> None:
        """Backfill missing user_id and normalize cookie filenames to platform_user_id."""
        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT account_id, platform, user_id, cookie_file FROM cookie_accounts"
            ).fetchall()

            for row in rows:
                account_id = row["account_id"]
                platform = self._normalize_platform(row["platform"])
                user_id = row["user_id"]
                cookie_file = row["cookie_file"] or ""

                inferred = user_id or self._infer_user_id(platform, cookie_file)
                if not inferred:
                    continue

                expected = self._build_cookie_filename(platform, inferred)
                expected_path = self.cookies_dir / expected
                current_path = self._resolve_cookie_path(cookie_file)

                if current_path.exists() and current_path.name != expected:
                    if not expected_path.exists():
                        try:
                            import shutil
                            shutil.move(str(current_path), str(expected_path))
                            cookie_file = expected
                        except Exception as exc:
                            logger.warning(f"[CookieManager] Rename cookie file failed: {current_path} -> {expected_path} ({exc})")
                    else:
                        cookie_file = expected

                if inferred != user_id or cookie_file != row["cookie_file"]:
                    conn.execute(
                        "UPDATE cookie_accounts SET user_id = ?, cookie_file = ? WHERE account_id = ?",
                        (inferred, cookie_file, account_id),
                    )
            conn.commit()

    def _build_cookie_filename(self, platform: str, user_id: str) -> str:
        if not platform or not user_id:
            raise ValueError("platform and user_id are required to build cookie filename")
        return f"{platform}_{user_id}.json"

    def _extract_user_id_from_cookie(self, platform: str, cookie_data: Any) -> Optional[str]:
        """从Cookie数据中提取user_id"""
        try:
            # 优先从 user_info 字段提取(最准确)
            if isinstance(cookie_data, dict):
                user_info = cookie_data.get('user_info', {})
                if user_info and user_info.get('user_id'):
                    return str(user_info['user_id'])

            # 处理不同格式的cookie数据
            cookies_list = []
            if isinstance(cookie_data, dict):
                if 'cookies' in cookie_data:
                    cookies_list = cookie_data['cookies']
                elif 'origins' in cookie_data:
                    # Playwright格式
                    for origin in cookie_data.get('origins', []):
                        cookies_list.extend(origin.get('cookies', []))
            elif isinstance(cookie_data, list):
                cookies_list = cookie_data

            # 根据平台提取对应的user_id字段(注意:抖音的uid_tt是加密字符串,不使用)
            # Channels: try localStorage finder_username first
            if platform == 'channels' and isinstance(cookie_data, dict):
                for origin in cookie_data.get('origins', []) or []:
                    if not isinstance(origin, dict):
                        continue
                    local_storage = origin.get('localStorage') or []
                    for item in local_storage:
                        if not isinstance(item, dict):
                            continue
                        if item.get('name') == 'finder_username' and item.get('value'):
                            return str(item.get('value'))

            platform_id_map = {
                'kuaishou': ['userId', 'bUserId'],  # 快手 - userId优先
                'douyin': [],  # 抖音 - 不从cookie提取,只用user_info.user_id
                'xiaohongshu': [],  # 小红书 - 不从cookie提取,只能从DOM/JS提取（customer-sso-sid/web_session是会话ID，不是user_id）
                'channels': ['wxuin', 'uin'],  # 视频号
                'bilibili': ['DedeUserID', 'DedeUserID__ckMd5'],  # B站
            }

            id_fields = platform_id_map.get(platform, [])

            # 按照优先级顺序查找（先遍历id_fields，再遍历cookies）
            for id_field in id_fields:
                for cookie in cookies_list:
                    if isinstance(cookie, dict):
                        cookie_name = cookie.get('name', '')
                        if cookie_name == id_field:
                            value = cookie.get('value', '')
                            if value and value != '':
                                return str(value)

            return None

        except Exception as e:
            logger.warning(f"[CookieManager] 提取UserID失败: {e}")
            return None

    def _extract_user_info_from_cookie(self, platform: str, cookie_data: Any) -> Dict[str, Any]:
        """
        尝试从 cookie/json 文件中提取 user_id/name/avatar（尽力而为，未找到则为空）
        """
        info = {"user_id": None, "name": None, "avatar": None}
        try:
            # Playwright storageState 格式中的 cookies 在 origins 里也可能存在
            def collect_cookies(data):
                cookies_list = []
                if isinstance(data, dict):
                    if isinstance(data.get("cookies"), list):
                        cookies_list.extend(data.get("cookies", []))
                    if isinstance(data.get("origins"), list):
                        for origin in data.get("origins", []):
                            cookies_list.extend(origin.get("cookies", []))
                elif isinstance(data, list):
                    cookies_list.extend(data)
                return cookies_list

            # 先用已有的 user_id 提取逻辑
            uid = self._extract_user_id_from_cookie(platform, cookie_data)
            if uid:
                info["user_id"] = uid

            # 常见结构：user_info、token_info、platform_tokens
            user_info = {}
            if isinstance(cookie_data, dict):
                user_info = cookie_data.get("user_info") or cookie_data.get("login_info") or {}
                tokens = cookie_data.get("platform_tokens") or cookie_data.get("token_info") or {}
                # user_id
                for key in ["user_id", "finder_username", "mid", "redId", "red_id"]:
                    if not info["user_id"] and tokens.get(key):
                        info["user_id"] = str(tokens.get(key))
                if platform == "douyin" and not info["user_id"] and isinstance(user_info, dict):
                    for key in ["unique_id", "short_id", "douyin_id", "douyinId"]:
                        value = user_info.get(key)
                        if value:
                            info["user_id"] = str(value)
                            break
                    if not info["user_id"] and user_info.get("sec_uid"):
                        info["user_id"] = str(user_info.get("sec_uid"))
                # name
                for key in ["name", "username", "finder_username", "finderUsername", "user_id", "redId", "red_id"]:
                    if not info["name"] and user_info.get(key):
                        info["name"] = str(user_info.get(key))
                if not info["name"]:
                    for key in ["name", "username"]:
                        if tokens.get(key):
                            info["name"] = str(tokens.get(key))
                            break
                # avatar
                for key in ["avatar", "head_img_url", "headImgUrl", "face", "imageb"]:
                    if not info["avatar"] and (user_info.get(key) or tokens.get(key)):
                        info["avatar"] = user_info.get(key) or tokens.get(key)
                        break
                # 兜底：从 cookies 里找头像/名称字段（部分平台会塞在 cookie 值里）
                cookies_list = collect_cookies(cookie_data)
                if cookies_list:
                    for ck in cookies_list:
                        if not isinstance(ck, dict):
                            continue
                        if not info["user_id"] and ck.get("name") in ["userId", "bUserId", "kuaishou.user.id", "DedeUserID"]:
                            info["user_id"] = str(ck.get("value"))
                        if not info["name"] and ck.get("name") in ["finder_username", "finderUsername"]:
                            info["name"] = str(ck.get("value"))
            return info
        except Exception as e:
            logger.warning(f"[CookieManager] 提取用户信息失败: {e}")
            return info

    def _enrich_with_fast_validator(self, platform: str, cookie_file: str, account: Dict[str, Any]):
        """使用 Worker（Playwright）补全 name/user_id/avatar（DOM + cookie，不做扫码）。"""
        try:
            storage_state = self._read_cookie_file(cookie_file)
            if not storage_state or not isinstance(storage_state, dict):
                return

            import httpx

            worker_base_url = os.environ.get("PLAYWRIGHT_WORKER_URL", "http://127.0.0.1:7001").rstrip("/")
            try:
                from config.conf import PLAYWRIGHT_HEADLESS
                desired_headless = bool(PLAYWRIGHT_HEADLESS)
            except Exception:
                desired_headless = True

            resp = httpx.post(
                f"{worker_base_url}/account/enrich",
                json={
                    "platform": self._normalize_platform(platform),
                    "storage_state": storage_state,
                    "headless": desired_headless,
                    "account_id": account.get("account_id"),
                },
                timeout=30.0,
            )
            if resp.status_code >= 400:
                return
            payload = resp.json()
            if not payload.get("success"):
                return
            enriched = (payload.get("data") or {}) if isinstance(payload, dict) else {}

            if enriched.get("user_id") and not account.get("user_id"):
                account["user_id"] = str(enriched["user_id"])
            if enriched.get("name"):
                current_name = account.get("name")
                if (
                    not current_name
                    or current_name == "-"
                    or (isinstance(current_name, str) and current_name.startswith("未命名账号"))
                    or (account.get("user_id") and str(current_name) == str(account.get("user_id")))
                ):
                    account["name"] = str(enriched["name"])
            if enriched.get("avatar") and not account.get("avatar"):
                account["avatar"] = enriched["avatar"]
        except Exception as e:
            logger.warning(f"[CookieManager] Fast validator enrich failed: {e}")

    def _resolve_platform(self, platform_name: str) -> int:
        normalized = self._normalize_platform(platform_name)
        if normalized not in PLATFORM_CODES:
            raise ValueError(f"Unsupported platform: {platform_name}")
        return PLATFORM_CODES[normalized]

    def add_account(self, platform_name: str, account_details: Dict[str, Any]):
        platform_code = self._resolve_platform(platform_name)
        normalized_platform = CODE_TO_PLATFORM.get(platform_code, platform_name)

        # 尝试从Cookie中提取user_id（如果传入的user_id为空）
        user_id = account_details.get("user_id")
        cookie_data = account_details.get("cookie", {})

        if not user_id and cookie_data:
            user_id = self._extract_user_id_from_cookie(normalized_platform, cookie_data)
            if user_id:
                logger.info(f"[CookieManager] 从Cookie中提取到UserID: {user_id}")
                account_details["user_id"] = user_id
        
        # 尝试补全 name/avatar（直接从 cookie 数据结构中获取）
        if cookie_data:
            extracted = self._extract_user_info_from_cookie(normalized_platform, cookie_data)
            if extracted.get("user_id") and not account_details.get("user_id"):
                account_details["user_id"] = extracted["user_id"]
            if extracted.get("name"):
                current_name = account_details.get("name")
                # 覆盖空值、默认占位或等于 user_id 的名称
                if (
                    not current_name
                    or current_name == "-"
                    or (isinstance(current_name, str) and current_name.startswith("未命名账号"))
                    or (account_details.get("user_id") and str(current_name) == str(account_details.get("user_id")))
                ):
                    account_details["name"] = extracted["name"]
            if extracted.get("avatar") and not account_details.get("avatar"):
                account_details["avatar"] = extracted["avatar"]

        temp_cookie_file = None
        if not account_details.get("user_id") and cookie_data:
            temp_cookie_file = f"{normalized_platform}_pending_{uuid.uuid4().hex[:12]}.json"
            try:
                self._write_cookie_file(temp_cookie_file, cookie_data)
                self._enrich_with_fast_validator(normalized_platform, temp_cookie_file, account_details)
            except Exception:
                pass

        if not account_details.get("user_id"):
            if temp_cookie_file:
                try:
                    (self.cookies_dir / temp_cookie_file).unlink()
                except Exception:
                    pass
            raise ValueError(f"user_id is required for {normalized_platform} cookie persistence")
        user_id = account_details.get("user_id")

        # 检查是否存在相同的 user_id
        existing_account_id = None
        existing_note = None
        existing_cookie_file = None

        if user_id:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT account_id, note, cookie_file, last_checked FROM cookie_accounts WHERE platform = ? AND user_id = ? ORDER BY last_checked DESC",
                    (normalized_platform, user_id)
                )
                rows = cursor.fetchall()
                if rows:
                    row = rows[0]
                    existing_account_id = row['account_id']
                    existing_note = row['note']
                    existing_cookie_file = row['cookie_file']
                    logger.info(f"[CookieManager] 检测到已存在的账号: {existing_account_id} (UserID: {user_id}, Note: {existing_note})")
                    if len(rows) > 1:
                        remove_ids = [r["account_id"] for r in rows[1:] if r.get("account_id")]
                        if remove_ids:
                            conn.execute(
                                f"DELETE FROM cookie_accounts WHERE account_id IN ({','.join(['?'] * len(remove_ids))})",
                                remove_ids,
                            )
                            conn.commit()
                            logger.info(f"[CookieManager] 清理重复账号: {remove_ids}")

        # 智能备注更新逻辑
        new_note = account_details.get("note") or "-"  # 默认备注为 "-"

        # 决定最终账号ID和备注
        if existing_account_id:
            # 账号已存在，根据备注优先级决定是否覆盖
            if new_note and "派发" in new_note:
                # 新备注包含"派发"，优先级最高，覆盖现有账号
                account_id = existing_account_id
                note = new_note
                logger.info(f"[CookieManager] 派发账号覆盖: {existing_note} -> {new_note} (UserID: {user_id})")
            elif existing_note and "派发" in existing_note:
                # 现有备注包含"派发"，保持现有备注（派发账号不被普通账号覆盖）
                account_id = existing_account_id
                note = existing_note
                logger.info(f"[CookieManager] 保留派发账号备注: {existing_note} (UserID: {user_id})")
            elif existing_note and existing_note != "-":
                # 现有备注存在且不是默认值，保留现有备注
                account_id = existing_account_id
                note = existing_note
                logger.info(f"[CookieManager] 保留现有备注: {existing_note} (UserID: {user_id})")
            else:
                # 现有备注为空或默认值，使用新备注
                account_id = existing_account_id
                note = new_note
                logger.info(f"[CookieManager] 更新账号备注: {existing_note} -> {new_note} (UserID: {user_id})")
        else:
            # 新账号，使用新的账号ID和备注
            account_id = account_details.get("id") or account_details.get("account_id")
            note = new_note
            logger.info(f"[CookieManager] 创建新账号: ID={account_id}, Note={note}, UserID={user_id}")

        if not account_id:
            raise ValueError("Account id is required")

        # 使用现有的cookie文件名或创建新的（规范格式：platform_userid.json）
        if existing_account_id and existing_cookie_file:
            # 检查现有文件名是否符合规范格式
            expected_filename = self._build_cookie_filename(normalized_platform, account_details.get("user_id"))
            if existing_cookie_file != expected_filename:
                # 重命名为规范格式
                old_path = self.cookies_dir / existing_cookie_file
                new_path = self.cookies_dir / expected_filename
                if old_path.exists():
                    import shutil
                    shutil.move(str(old_path), str(new_path))
                    cookie_file = expected_filename
                    logger.info(f"[CookieManager] Cookie文件重命名为规范格式: {existing_cookie_file} -> {expected_filename}")
                else:
                    cookie_file = expected_filename
            else:
                cookie_file = existing_cookie_file
            logger.info(f"[CookieManager] 覆盖已有账号的Cookie文件: {cookie_file} (UserID: {user_id})")
        else:
            # 新账号：使用规范格式
            cookie_file = self._build_cookie_filename(normalized_platform, account_details.get("user_id"))
            logger.info(f"[CookieManager] 校验 Cookie 文件是否存在: {cookie_file}")

        # 写入cookie文件
        self._write_cookie_file(cookie_file, account_details.get("cookie", {}))

        # 若缺少关键字段，再用快速校验补全（会就地更新 account_details）
        if (not account_details.get("name") or not account_details.get("user_id") or not account_details.get("avatar")):
            self._enrich_with_fast_validator(normalized_platform, cookie_file, account_details)

        # 若通过补全拿到了 user_id，确保 cookie 文件名与 user_id 对齐
        if account_details.get("user_id"):
            expected_filename = self._build_cookie_filename(normalized_platform, account_details["user_id"])
            if cookie_file != expected_filename:
                old_path = self.cookies_dir / cookie_file
                new_path = self.cookies_dir / expected_filename
                if old_path.exists() and not new_path.exists():
                    try:
                        import shutil
                        shutil.move(str(old_path), str(new_path))
                    except Exception:
                        pass
                cookie_file = expected_filename
        if temp_cookie_file and temp_cookie_file != cookie_file:
            try:
                (self.cookies_dir / temp_cookie_file).unlink()
            except Exception:
                pass

        # 二次去重：若补全后有 user_id，清理同平台同 user_id 的旧记录
        if account_details.get("user_id"):
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.execute(
                        "SELECT account_id, cookie_file FROM cookie_accounts WHERE platform = ? AND user_id = ?",
                        (normalized_platform, account_details.get("user_id")),
                    )
                    rows = cursor.fetchall()
                    for row in rows:
                        if row["account_id"] == account_id:
                            continue
                        drop_cookie = row.get("cookie_file")
                        if drop_cookie:
                            drop_path = self._resolve_cookie_path(drop_cookie)
                            if drop_path.exists():
                                try:
                                    drop_path.unlink()
                                except Exception:
                                    pass
                        conn.execute("DELETE FROM cookie_accounts WHERE account_id = ?", (row["account_id"],))
                    conn.commit()
            except Exception:
                pass

        # 最终使用补全后的字段
        account_name = account_details.get("name") or account_details.get("userName") or account_id
        # 如果是覆盖已有账号（重新登录），强制设置status为valid
        if existing_account_id:
            status = "valid"
            logger.info(f"[CookieManager] 账号状态更新为valid (UserID: {user_id})")
        else:
            status = account_details.get("status") or "valid"
        last_checked = account_details.get("last_checked") or datetime.now(timezone.utc).isoformat()
        avatar = account_details.get("avatar")
        original_name = account_details.get("original_name")
        user_id = account_details.get("user_id")

        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO cookie_accounts (account_id, platform, platform_code, name, status, cookie_file, last_checked, avatar, original_name, note, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    platform=excluded.platform,
                    platform_code=excluded.platform_code,
                    name=excluded.name,
                    status=excluded.status,
                    cookie_file=excluded.cookie_file,
                    last_checked=excluded.last_checked,
                    avatar=excluded.avatar,
                    original_name=excluded.original_name,
                    note=excluded.note,
                    user_id=excluded.user_id
                """,
                (
                    account_id,
                    normalized_platform,
                    platform_code,
                    account_name,
                    status,
                    cookie_file,
                    last_checked,
                    avatar,
                    original_name,
                    note,
                    user_id,
                ),
            )
            logger.info(f"[CookieManager] 数据库插入/更新成功: ID={account_id}, Name={account_name}, Note={note}, UserID={user_id}")
            conn.commit()

        # 自动更新前端快照
        try:
            accounts = self.list_flat_accounts()
            snapshot_accounts = [{"account_id": acc["account_id"], "platform": acc["platform"], "user_id": acc.get("user_id")} for acc in accounts]
            self.save_frontend_snapshot(snapshot_accounts)
            logger.info(f"[CookieManager] 前端快照已自动更新: {len(snapshot_accounts)} 个账号")
        except Exception as e:
            logger.warning(f"[CookieManager] 更新前端快照失败: {e}")

    def _group_accounts(self, rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            account = {
                "id": row["account_id"],
                "name": row["name"],
                "status": row["status"],
                "cookie": self._read_cookie_file(row["cookie_file"]),
                "platform": row["platform"],
                "platform_code": row["platform_code"],
                "filePath": row["cookie_file"],
                "last_checked": row["last_checked"],
                "avatar": row["avatar"] if "avatar" in row.keys() else None,
                "original_name": row["original_name"] if "original_name" in row.keys() else None,
                "note": row["note"] if "note" in row.keys() else None,
                "user_id": row["user_id"] if "user_id" in row.keys() else None,
                "login_status": row["login_status"] if "login_status" in row.keys() else None,
            }
            grouped.setdefault(row["platform"], []).append(account)
        return [{"name": name, "accounts": accounts} for name, accounts in grouped.items()]

    def get_all_accounts(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT account_id, platform, platform_code, name, status, cookie_file, last_checked, avatar, original_name, note, user_id, login_status FROM cookie_accounts "
                "ORDER BY platform, name"
            ).fetchall()
        return self._group_accounts(rows)

    def list_flat_accounts(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT account_id, platform, platform_code, name, status, cookie_file, last_checked, avatar, original_name, note, user_id, login_status FROM cookie_accounts "
                "ORDER BY platform, name"
            ).fetchall()
        return [dict(row) for row in rows]

    def cleanup_duplicate_accounts(self) -> Dict[str, int]:
        """Remove duplicated accounts with same platform + user_id, keep the latest one."""
        removed = 0
        kept = 0
        groups = 0

        def _parse_dt(raw: Optional[str]) -> float:
            if not raw:
                return 0.0
            try:
                return datetime.fromisoformat(raw).timestamp()
            except Exception:
                return 0.0

        with self.lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT account_id, platform, user_id, last_checked, cookie_file FROM cookie_accounts "
                "WHERE user_id IS NOT NULL AND user_id != ''"
            ).fetchall()

            grouped: Dict[tuple, List[Dict[str, Any]]] = {}
            for row in rows:
                item = dict(row)
                key = (item.get("platform"), item.get("user_id"))
                grouped.setdefault(key, []).append(item)

            for key, items in grouped.items():
                if len(items) <= 1:
                    continue
                groups += 1
                items_sorted = sorted(
                    items,
                    key=lambda item: (_parse_dt(item.get("last_checked")), item.get("account_id") or ""),
                    reverse=True,
                )
                kept += 1
                for drop in items_sorted[1:]:
                    cookie_file = drop.get("cookie_file")
                    if cookie_file:
                        file_path = self.cookies_dir / cookie_file
                        if file_path.exists():
                            file_path.unlink()
                    conn.execute("DELETE FROM cookie_accounts WHERE account_id = ?", (drop.get("account_id"),))
                    removed += 1
            conn.commit()

        return {"groups": groups, "kept": kept, "removed": removed}

    def cleanup_orphan_cookie_files(self) -> Dict[str, int]:
        """Remove cookie files that do not exist in DB accounts."""
        removed = 0
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT cookie_file FROM cookie_accounts").fetchall()
        db_files = {self._normalize_cookie_ref(row["cookie_file"]) for row in rows if row["cookie_file"]}

        for file_path in self.cookies_dir.rglob("*.json"):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(self.cookies_dir).as_posix()
            if rel_path not in db_files:
                try:
                    file_path.unlink()
                    removed += 1
                except Exception as e:
                    logger.warning(f"[CookieManager] Failed to remove orphan cookie file: {file_path} ({e})")

        return {"removed": removed}

    def save_frontend_snapshot(self, accounts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Persist frontend account snapshot for later cleanup."""
        payload = {
            "updated_at": datetime.utcnow().isoformat(),
            "accounts": accounts,
        }
        try:
            self.frontend_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            self.frontend_snapshot_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
            return {"success": True, "count": len(accounts)}
        except Exception as e:
            logger.error(f"[CookieManager] Save frontend snapshot failed: {e}")
            return {"success": False, "error": str(e)}

    def load_frontend_snapshot(self) -> List[Dict[str, Any]]:
        if not self.frontend_snapshot_path.exists():
            return []
        try:
            payload = json.loads(self.frontend_snapshot_path.read_text(encoding="utf-8"))
            accounts = payload.get("accounts") if isinstance(payload, dict) else []
            return accounts if isinstance(accounts, list) else []
        except Exception:
            return []

    def prune_accounts_not_in_frontend(self, accounts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Remove cookie accounts not present in frontend snapshot."""
        normalized = []
        for acc in accounts:
            account_id = acc.get("account_id") or acc.get("id")
            platform = acc.get("platform")
            user_id = acc.get("user_id")
            if platform and (account_id or user_id):
                normalized.append({"account_id": str(account_id) if account_id else "", "user_id": str(user_id) if user_id else "", "platform": str(platform)})

        if not normalized:
            return {"removed": 0, "skipped": 1}

        allowed_accounts = {(acc["platform"], acc["account_id"]) for acc in normalized if acc["account_id"]}
        allowed_users = {(acc["platform"], acc["user_id"]) for acc in normalized if acc["user_id"]}
        removed = 0

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT account_id, platform, user_id, cookie_file FROM cookie_accounts"
            ).fetchall()
            for row in rows:
                key_account = (row["platform"], row["account_id"])
                key_user = (row["platform"], row["user_id"]) if row["user_id"] else None
                if key_account in allowed_accounts or (key_user and key_user in allowed_users):
                    continue
                conn.execute("DELETE FROM cookie_accounts WHERE account_id = ?", (row["account_id"],))
                removed += 1
                cookie_path = self._resolve_cookie_path(row["cookie_file"] or "")
                if cookie_path.exists():
                    try:
                        cookie_path.unlink()
                    except Exception:
                        pass

        return {"removed": removed}

    def prune_accounts_from_snapshot(self) -> Dict[str, int]:
        accounts = self.load_frontend_snapshot()
        return self.prune_accounts_not_in_frontend(accounts)

    def get_account_by_id(self, account_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT account_id, platform, platform_code, name, status, cookie_file, last_checked, avatar, original_name, note, user_id FROM cookie_accounts "
                "WHERE account_id = ?",
                (account_id,),
            )
            row = cursor.fetchone()
        if not row:
            platform_hint = None
            user_id_hint = None
            if account_id and "_" in account_id:
                prefix, rest = account_id.split("_", 1)
                if prefix in PLATFORM_CODES and rest:
                    platform_hint = prefix
                    user_id_hint = rest
            if user_id_hint:
                return self.get_account_by_user_id(user_id_hint, platform=platform_hint)
            return self.get_account_by_user_id(account_id)
        payload = dict(row)
        payload["cookie"] = self._read_cookie_file(payload["cookie_file"])
        return payload

    def get_account_by_user_id(self, user_id: str, platform: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not user_id:
            return None
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if platform:
                cursor = conn.execute(
                    "SELECT account_id, platform, platform_code, name, status, cookie_file, last_checked, avatar, original_name, note, user_id FROM cookie_accounts "
                    "WHERE user_id = ? AND platform = ?",
                    (user_id, platform),
                )
                row = cursor.fetchone()
            else:
                cursor = conn.execute(
                    "SELECT account_id, platform, platform_code, name, status, cookie_file, last_checked, avatar, original_name, note, user_id FROM cookie_accounts "
                    "WHERE user_id = ?",
                    (user_id,),
                )
                rows = cursor.fetchall()
                if not rows:
                    return None
                if len(rows) > 1:
                    logger.warning(f"[CookieManager] Multiple accounts share user_id={user_id}, using the first match")
                row = rows[0]
        if not row:
            return None
        payload = dict(row)
        payload["cookie"] = self._read_cookie_file(payload["cookie_file"])
        return payload

    def update_account_status(self, platform_name: str, account_id: str, status: str) -> bool:
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE cookie_accounts SET status = ?, last_checked = ? WHERE account_id = ?",
                (status, datetime.now(timezone.utc).isoformat(), account_id),
            )
            conn.commit()
        return cursor.rowcount > 0

    def update_account(self, account_id: str, *, name: Optional[str] = None, platform_code: Optional[int] = None, **kwargs) -> bool:
        updates: List[str] = []
        params: List[Any] = []
        if name:
            updates.append("name = ?")
            params.append(name)
        if platform_code:
            updates.append("platform_code = ?")
            params.append(platform_code)
            platform_name = CODE_TO_PLATFORM.get(platform_code)
            if platform_name:
                updates.append("platform = ?")
                params.append(platform_name)
        if "avatar" in kwargs:
            updates.append("avatar = ?")
            params.append(kwargs["avatar"])
        if "original_name" in kwargs:
            updates.append("original_name = ?")
            params.append(kwargs["original_name"])
        if "note" in kwargs:
            updates.append("note = ?")
            params.append(kwargs["note"])
        if "user_id" in kwargs:
            updates.append("user_id = ?")
            params.append(kwargs["user_id"])
        if "status" in kwargs:
            updates.append("status = ?")
            params.append(kwargs["status"])
        if "last_checked" in kwargs:
            updates.append("last_checked = ?")
            params.append(kwargs["last_checked"])
        if not updates:
            return False
        params.append(account_id)
        with self.lock, sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"UPDATE cookie_accounts SET {', '.join(updates)} WHERE account_id = ?", params)
            conn.commit()
        return cursor.rowcount > 0

    def delete_account(self, account_id: str) -> bool:
        with self.lock, sqlite3.connect(self.db_path) as conn:
            # 获取账号信息以删除相关文件
            cursor = conn.execute("SELECT cookie_file, platform, user_id FROM cookie_accounts WHERE account_id = ?", (account_id,))
            row = cursor.fetchone()
            if row:
                # 1. 删除Cookie文件
                file_path = self.cookies_dir / row[0]
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"[CookieManager] Deleted cookie file: {file_path}")

                # 2. 删除持久化浏览器目录
                platform = row[1] if row[1] else CODE_TO_PLATFORM.get(row[1], "")
                user_id = row[2]  # 获取 user_id
                if platform:
                    try:
                        from myUtils.browser_context import persistent_browser_manager
                        success = persistent_browser_manager.cleanup_user_data(account_id, platform, user_id)
                        if success:
                            logger.info(f"[CookieManager] Deleted browser profile for {platform}_{user_id or account_id}")
                    except Exception as e:
                        logger.warning(f"[CookieManager] Failed to delete browser profile: {e}")

            cursor = conn.execute("DELETE FROM cookie_accounts WHERE account_id = ?", (account_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_invalid_accounts(self) -> int:
        """删除所有状态不为 'valid' 的账号"""
        with self.lock, sqlite3.connect(self.db_path) as conn:
            # 获取所有失效账号的信息
            rows = conn.execute("SELECT cookie_file, platform, account_id, user_id FROM cookie_accounts WHERE status != 'valid'").fetchall()
            count = 0
            for row in rows:
                # 1. 删除Cookie文件
                if row[0]:
                    file_path = self.cookies_dir / row[0]
                    if file_path.exists():
                        file_path.unlink()
                        logger.info(f"[CookieManager] Deleted cookie file: {file_path}")

                # 2. 删除持久化浏览器目录
                platform = row[1] if row[1] else CODE_TO_PLATFORM.get(row[1], "")
                account_id = row[2]
                user_id = row[3]  # 获取 user_id
                if platform and account_id:
                    try:
                        from myUtils.browser_context import persistent_browser_manager
                        success = persistent_browser_manager.cleanup_user_data(account_id, platform, user_id)
                        if success:
                            logger.info(f"[CookieManager] Deleted browser profile for {platform}_{user_id or account_id}")
                    except Exception as e:
                        logger.warning(f"[CookieManager] Failed to delete browser profile: {e}")
                count += 1

            cursor = conn.execute("DELETE FROM cookie_accounts WHERE status != 'valid'")
            conn.commit()
            return cursor.rowcount

    def get_cookie(self, platform_name: str, account_name: str) -> Optional[Dict[str, Any]]:
        normalized = self._normalize_platform(platform_name)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT cookie_file FROM cookie_accounts WHERE platform = ? AND name = ?",
                (normalized, account_name),
            )
            row = cursor.fetchone()
        if not row:
            return None
        return self._read_cookie_file(row["cookie_file"])


    def _identify_platform_from_json(self, data: Any) -> str:
        """根据cookie数据识别平台"""
        # Normalize data
        if isinstance(data, dict) and 'cookies' in data:
            data = data['cookies']
        
        if not isinstance(data, list):
            return "unknown"
        
        domains = set()
        for cookie in data:
            if 'domain' in cookie:
                domains.add(cookie['domain'])
                
        for domain in domains:
            if "douyin" in domain: return "douyin"
            if "kuaishou" in domain: return "kuaishou"
            if "xiaohongshu" in domain: return "xiaohongshu"
            if "bilibili" in domain: return "bilibili"
            if "channels.weixin.qq.com" in domain: return "channels"
            if "qq.com" in domain and not "bilibili" in domain: return "channels"
            
        return "unknown"

    def deep_sync_accounts(self, validate_cookies: bool = False) -> Dict[str, int]:
        """
        深度同步：
        1. 检查库中账号，文件丢失的标记为 file_missing
        2. 对现有账号尽量补全 name/avatar/user_id
        3. 验证Cookie有效性（可选）
        4. 返回同步统计

        说明：
        - 关闭“自动备份”和“自动扫描磁盘添加新账号”，避免重复 cookie / 误改文件名。
        """
        stats = {"added": 0, "marked_missing": 0, "validated": 0, "expired": 0, "total_files": 0, "backed_up": 0, "cleaned_up": 0}

        # 1. 获取所有磁盘文件
        disk_files = {f.name: f for f in self.cookies_dir.glob("*.json")}
        stats["total_files"] = len(disk_files)

        # 2. 获取所有数据库账号
        db_accounts = self.list_flat_accounts()
        db_filenames = {a['cookie_file']: a for a in db_accounts}

        # 不再自动添加无主文件，避免重复账号/改名

        # 3. 处理文件丢失的账号（标记为file_missing）
        for account in db_accounts:
            filename = account['cookie_file']
            if not filename or filename not in disk_files:
                if account['status'] not in ['file_missing', 'expired']:
                    self.update_account_status(account['platform'], account['account_id'], "file_missing")
                    stats["marked_missing"] += 1
                    print(f"[DeepSync] 标记文件丢失: {account['name']} (status: file_missing)")
            else:
                # 文件存在，尝试补全 user_id/name/avatar
                try:
                    data = json.load(open(disk_files[filename], 'r', encoding='utf-8'))
                    extracted = self._extract_user_info_from_cookie(account['platform'], data)
                    needs_update = False
                    if extracted.get("user_id") and not account.get("user_id"):
                        account['user_id'] = extracted["user_id"]
                        needs_update = True
                    if extracted.get("avatar") and not account.get("avatar"):
                        account['avatar'] = extracted["avatar"]
                        needs_update = True
                    if extracted.get("name") and account.get("name") in [None, "", "-", "未命名账号"]:
                        account['name'] = extracted["name"]
                        needs_update = True
                    # 如果仍缺关键字段，尝试 HTTP 快速校验补全
                    if (not account.get("name") or not account.get("user_id") or not account.get("avatar")):
                        self._enrich_with_fast_validator(account['platform'], filename, account)
                        if account.get("name") or account.get("user_id") or account.get("avatar"):
                            needs_update = True
                    # 再兜底：直接访问页面抓取（重用 fetch_user_info_service 逻辑）
                    if (not account.get("name") or not account.get("user_id") or not account.get("avatar")):
                        try:
                            from myUtils.fetch_user_info_service import fetch_single_user_info
                            info = asyncio.run(fetch_single_user_info(account['platform'], disk_files[filename]))
                            if info:
                                if info.get("name"):
                                    account["name"] = info["name"]
                                if info.get("avatar"):
                                    account["avatar"] = info["avatar"]
                                if info.get("user_id"):
                                    account["user_id"] = info["user_id"]
                                needs_update = True
                        except Exception as e:
                            print(f"[DeepSync] 页面抓取补全失败 {account.get('account_id')}: {e}")
                    if needs_update:
                        self._persist_account(account)
                        print(f"[DeepSync] 补全账号信息: {account['account_id']} ({account['platform']})")
                except Exception as e:
                    print(f"[DeepSync] 补全失败 {account.get('account_id')}: {e}")

        # 4. 验证Cookie有效性（如果启用）
        if validate_cookies:
            print("[DeepSync] 开始验证Cookie有效性...")
            db_accounts_refreshed = self.list_flat_accounts()  # 重新获取账号列表
            for account in db_accounts_refreshed:
                if account['status'] in ['valid', 'unchecked']:  # 只验证valid和unchecked状态的账号
                    filename = account['cookie_file']
                    if filename and filename in disk_files:
                        try:
                            # 使用fast_validator快速验证
                            platform_code = PLATFORM_CODES.get(self._normalize_platform(account['platform']))
                            if platform_code:
                                self._enrich_with_fast_validator(account['platform'], filename, account)
                                # 检查验证结果（通过比较是否有user_id判断）
                                if not account.get('user_id'):
                                    # 验证失败，标记为expired
                                    self.update_account_status(account['platform'], account['account_id'], "expired")
                                    stats["expired"] += 1
                                    print(f"[DeepSync] Cookie已失效: {account['name']} ({account['platform']})")
                                else:
                                    stats["validated"] += 1
                                    # 更新为valid状态
                                    if account['status'] == 'unchecked':
                                        self.update_account_status(account['platform'], account['account_id'], "valid")
                        except Exception as e:
                            print(f"[DeepSync] 验证失败 {account.get('account_id')}: {e}")

        return stats

    async def run_maintenance(self, account_id: str = None) -> Dict[str, Any]:
        """
        运行账号维护任务
        :param account_id: 指定账号ID，如果为None则维护所有账号
        """
        from myUtils.maintenance import maintain_account
        
        accounts = []
        if account_id:
            acc = self.get_account_by_id(account_id)
            if acc: accounts.append(acc)
        else:
            accounts = self.list_flat_accounts()
            
        results = {"success": 0, "expired": 0, "error": 0, "details": []}
        
        for acc in accounts:
            if not acc['cookie_file']: continue
            
            logger.info(f"[CookieManager] 开始维护账号: {acc['name']}")
            status = await maintain_account(acc['platform_code'], acc['cookie_file'])
            
            results[status] = results.get(status, 0) + 1
            results["details"].append({
                "name": acc['name'],
                "platform": acc['platform'],
                "status": status
            })
            
            # Update status in DB if expired
            if status == "expired":
                self.update_account_status(acc['platform'], acc['account_id'], "expired")
                
        return results

cookie_manager = CookieManager()
