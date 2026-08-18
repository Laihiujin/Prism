from pathlib import Path

from config.conf import BASE_DIR

Path(BASE_DIR / "cookies" / "xiaohongshu_uploader").mkdir(exist_ok=True)