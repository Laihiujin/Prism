from pathlib import Path
import os

from config.conf import BASE_DIR

# 使用环境变量配置的 cookies 目录，默认为 cookiesFile
cookies_dir_name = os.getenv("COOKIES_DIR_NAME", "syn_backend/cookiesFile").split("/")[-1]
try:
    from fastapi_app.core.config import settings
    cookies_root = Path(settings.COOKIE_FILES_DIR)
except Exception:
    cookies_root = Path(BASE_DIR) / cookies_dir_name
Path(cookies_root / "bilibili_uploader").mkdir(parents=True, exist_ok=True)
