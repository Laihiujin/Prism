from pathlib import Path

from config.conf import BASE_DIR

Path(BASE_DIR / "cookies").mkdir(exist_ok=True)