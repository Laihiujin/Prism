from pathlib import Path
from typing import List
import os

from config.conf import BASE_DIR, PLAYWRIGHT_HEADLESS

SOCIAL_MEDIA_DOUYIN = "douyin"
SOCIAL_MEDIA_TENCENT = "tencent"
SOCIAL_MEDIA_TIKTOK = "tiktok"
SOCIAL_MEDIA_BILIBILI = "bilibili"
SOCIAL_MEDIA_KUAISHOU = "kuaishou"

try:
    HEADLESS_FLAG = PLAYWRIGHT_HEADLESS
except NameError:
    HEADLESS_FLAG = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"


def get_supported_social_media() -> List[str]:
    return [SOCIAL_MEDIA_DOUYIN, SOCIAL_MEDIA_TENCENT, SOCIAL_MEDIA_TIKTOK, SOCIAL_MEDIA_KUAISHOU]


def get_cli_action() -> List[str]:
    return ["upload", "login", "watch"]


async def set_init_script(context):
    """Optionally install the historical Puppeteer stealth bundle.

    Patchright already applies its own browser evasion.  The bundled legacy script
    mutates browser APIs again and, with the local Chrome 151 runtime, prevents
    navigation before a platform page can load.  Keep it as an explicit fallback
    for an adapter that has been verified to need it instead of enabling it for
    every login and upload flow.
    """
    if os.getenv("PRISM_LEGACY_STEALTH", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return context

    # 兼容多路径，优先当前目录，其次 BASE_DIR/utils
    candidates = [
        Path(__file__).resolve().parent / "stealth.min.js",
        Path(BASE_DIR) / "utils" / "stealth.min.js",
    ]
    for path in candidates:
        if path.exists():
            await context.add_init_script(path=path)
            return context
    raise FileNotFoundError(f"未找到 stealth.min.js，尝试路径: {', '.join(str(p) for p in candidates)}")
    return context
