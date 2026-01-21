"""
Full device fingerprint manager.
Generates and persists per-account fingerprints and provides init scripts.
"""
import json
import os
import hashlib
import random
import string
import re
from pathlib import Path
from typing import Dict, Optional
from loguru import logger

BASE_DIR = Path(__file__).resolve().parents[1]


def _is_dev_repo(base_dir: Path) -> bool:
    env = (os.getenv("SYNAPSE_ENV") or os.getenv("NODE_ENV") or "").strip().lower()
    if env in ("dev", "development", "local"):
        return True
    try:
        return (base_dir.parent / ".git").exists()
    except Exception:
        return False


class DeviceFingerprint:
    """Device fingerprint manager."""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    SCREEN_RESOLUTIONS = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 2560, "height": 1440},
        {"width": 1536, "height": 864},
    ]

    FONT_LIST = [
        "Arial",
        "Arial Black",
        "Calibri",
        "Cambria",
        "Cambria Math",
        "Comic Sans MS",
        "Consolas",
        "Courier New",
        "Georgia",
        "Helvetica",
        "Impact",
        "Lucida Console",
        "Microsoft YaHei",
        "Microsoft YaHei UI",
        "Microsoft Sans Serif",
        "Segoe UI",
        "Segoe UI Emoji",
        "Segoe UI Symbol",
        "Tahoma",
        "Times New Roman",
        "Trebuchet MS",
        "Verdana",
    ]

    PLUGINS = [
        {"name": "Chrome PDF Plugin", "filename": "internal-pdf-viewer", "description": "Portable Document Format"},
        {"name": "Chrome PDF Viewer", "filename": "mhjfbmdgcfjbbpaeojofohoefgiehjai", "description": ""},
        {"name": "Native Client", "filename": "internal-nacl-plugin", "description": ""},
    ]

    MIME_TYPES = [
        {"type": "application/pdf", "suffixes": "pdf", "description": "Portable Document Format"},
        {"type": "application/x-nacl", "suffixes": "", "description": "Native Client Executable"},
        {"type": "application/x-pnacl", "suffixes": "", "description": "Portable Native Client Executable"},
    ]

    MEDIA_DEVICES = [
        {"kind": "audioinput", "label": "Microphone (Realtek(R) Audio)", "groupId": "audio-group-1"},
        {"kind": "audiooutput", "label": "Speakers (Realtek(R) Audio)", "groupId": "audio-group-1"},
        {"kind": "videoinput", "label": "Integrated Camera", "groupId": "video-group-1"},
    ]

    def __init__(self, storage_dir: Path = None):
        if storage_dir is None:
            try:
                from fastapi_app.core.config import settings
                storage_dir = Path(settings.FINGERPRINTS_DIR)
            except Exception:
                env_dir = os.getenv("SYNAPSE_DATA_DIR")
                if not env_dir and _is_dev_repo(BASE_DIR):
                    env_dir = str(BASE_DIR)
                if not env_dir:
                    candidates = []
                    appdata = os.getenv("APPDATA")
                    local_root = os.getenv("LOCALAPPDATA")
                    if appdata:
                        candidates.append(Path(appdata) / "SynapseAutomation" / "data")
                    if local_root and local_root != appdata:
                        candidates.append(Path(local_root) / "SynapseAutomation" / "data")
                    for candidate in candidates:
                        if (candidate / "fingerprints").exists():
                            env_dir = str(candidate)
                            break
                    if not env_dir and candidates:
                        env_dir = str(candidates[0])
                if env_dir:
                    storage_dir = Path(env_dir) / "fingerprints"
                else:
                    storage_dir = BASE_DIR / "fingerprints"

        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _generate_device_id(self, account_id: str, platform: str) -> str:
        seed = f"{account_id}_{platform}_device"
        return hashlib.md5(seed.encode()).hexdigest()[:16]

    def _generate_webgl_vendor(self) -> str:
        vendors = [
            "Google Inc. (NVIDIA)",
            "Google Inc. (Intel)",
            "Google Inc. (AMD)",
        ]
        return random.choice(vendors)

    def _generate_canvas_fingerprint(self, device_id: str) -> str:
        seed = int(hashlib.md5(device_id.encode()).hexdigest()[:8], 16)
        random.seed(seed)
        fp = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        random.seed()
        return fp

    def _pick_subset(self, seed: int, items: list, min_count: int, max_count: int) -> list:
        if not items:
            return []
        random.seed(seed)
        count = min(len(items), random.randint(min_count, max_count))
        subset = random.sample(items, count)
        random.seed()
        return subset

    def _extract_chrome_version(self, user_agent: str) -> str:
        if not user_agent:
            return "120.0.0.0"
        match = re.search(r"Chrome/([0-9.]+)", user_agent)
        return match.group(1) if match else "120.0.0.0"

    def _build_client_hints(self, user_agent: str, platform: str) -> Dict:
        chrome_version = self._extract_chrome_version(user_agent)
        major = chrome_version.split(".")[0] if chrome_version else "120"
        brands = [
            {"brand": "Chromium", "version": major},
            {"brand": "Google Chrome", "version": major},
            {"brand": "Not A(Brand", "version": "99"},
        ]
        platform_map = {
            "win32": "Windows",
            "darwin": "macOS",
            "linux": "Linux",
        }
        ch_platform = platform_map.get(platform.lower(), "Windows") if platform else "Windows"
        return {
            "brands": brands,
            "mobile": False,
            "platform": ch_platform,
            "ua_full_version": chrome_version,
            "platform_version": "10.0.0",
            "architecture": "x86",
            "model": "",
            "bitness": "64",
            "wow64": False,
        }

    def generate_fingerprint(
        self,
        account_id: str,
        platform: str,
        policy: Optional[Dict] = None
    ) -> Dict:
        device_id = self._generate_device_id(account_id, platform)
        seed = int(hashlib.md5(device_id.encode()).hexdigest()[:8], 16)
        random.seed(seed)

        user_agent = random.choice(self.USER_AGENTS)
        screen = random.choice(self.SCREEN_RESOLUTIONS)
        fonts = self._pick_subset(seed + 7, self.FONT_LIST, 10, 16)
        plugins = list(self.PLUGINS)
        mime_types = list(self.MIME_TYPES)
        media_devices = list(self.MEDIA_DEVICES)
        client_hints = self._build_client_hints(user_agent, "win32")

        random.seed()

        webrtc_mode = ((policy or {}).get("webrtc") or {}).get("mode", "mask")
        audio_noise = ((policy or {}).get("audio") or {}).get("noise", 0.0001)

        return {
            "device_id": device_id,
            "user_agent": user_agent,
            "viewport": {"width": screen["width"], "height": screen["height"] - 100},
            "screen": screen,
            "timezone": "Asia/Shanghai",
            "language": "zh-CN",
            "languages": ["zh-CN", "zh", "en-US", "en"],
            "platform": "Win32",
            "webgl_vendor": self._generate_webgl_vendor(),
            "webgl_renderer": "ANGLE (NVIDIA GeForce GTX 1050 Ti Direct3D11 vs_5_0 ps_5_0)",
            "canvas_fp": self._generate_canvas_fingerprint(device_id),
            "audio_fp": hashlib.md5(device_id.encode()).hexdigest()[:16],
            "hardware_concurrency": 8,
            "device_memory": 8,
            "max_touch_points": 0,
            "color_depth": 24,
            "pixel_depth": 24,
            "fonts": fonts,
            "plugins": plugins,
            "mime_types": mime_types,
            "media_devices": media_devices,
            "client_hints": client_hints,
            "webrtc_mode": webrtc_mode,
            "audio_noise": audio_noise,
        }

    def get_or_create_fingerprint(
        self,
        account_id: str,
        platform: str,
        user_id: Optional[str] = None,
        policy: Optional[Dict] = None
    ) -> Dict:
        # Without user_id, skip persistence and generate a transient fingerprint.
        if not user_id:
            logger.warning(f"[fp] missing user_id for {platform} {account_id}; skip persistence")
            return self.generate_fingerprint(account_id, platform, policy=policy)
        identifier = user_id
        fingerprint_file = self.storage_dir / f"{platform}_{identifier}.json"

        if fingerprint_file.exists():
            try:
                with open(fingerprint_file, 'r', encoding='utf-8') as f:
                    fingerprint = json.load(f)
                    fingerprint = self._normalize_fingerprint(fingerprint, identifier, platform, policy)
                    logger.info(f"[fp] loaded: {platform} {account_id}")
                    return fingerprint
            except Exception as e:
                logger.warning(f"[fp] load failed: {e}; regenerate")

        fingerprint = self.generate_fingerprint(identifier, platform, policy=policy)

        try:
            with open(fingerprint_file, 'w', encoding='utf-8') as f:
                json.dump(fingerprint, f, ensure_ascii=False, indent=2)
            logger.info(f"[fp] saved: {platform} {account_id}")
        except Exception as e:
            logger.error(f"[fp] save failed: {e}")

        return fingerprint

    def _normalize_fingerprint(
        self,
        fingerprint: Dict,
        account_id: str,
        platform: str,
        policy: Optional[Dict],
    ) -> Dict:
        if not fingerprint.get("device_id"):
            fingerprint["device_id"] = self._generate_device_id(account_id, platform)
        if not fingerprint.get("user_agent"):
            fingerprint["user_agent"] = random.choice(self.USER_AGENTS)
        if "fonts" not in fingerprint:
            seed = int(hashlib.md5(fingerprint["device_id"].encode()).hexdigest()[:8], 16)
            fingerprint["fonts"] = self._pick_subset(seed + 7, self.FONT_LIST, 10, 16)
        if "plugins" not in fingerprint:
            fingerprint["plugins"] = list(self.PLUGINS)
        if "mime_types" not in fingerprint:
            fingerprint["mime_types"] = list(self.MIME_TYPES)
        if "media_devices" not in fingerprint:
            fingerprint["media_devices"] = list(self.MEDIA_DEVICES)
        if "client_hints" not in fingerprint:
            fingerprint["client_hints"] = self._build_client_hints(fingerprint.get("user_agent", ""), "win32")
        if "webrtc_mode" not in fingerprint:
            fingerprint["webrtc_mode"] = ((policy or {}).get("webrtc") or {}).get("mode", "mask")
        if "audio_noise" not in fingerprint:
            fingerprint["audio_noise"] = ((policy or {}).get("audio") or {}).get("noise", 0.0001)
        return fingerprint

    def apply_to_context(self, fingerprint: Dict, context_options: Dict) -> Dict:
        context_options.update({
            "user_agent": fingerprint["user_agent"],
            "viewport": fingerprint["viewport"],
            "screen": fingerprint["screen"],
            "locale": fingerprint["language"],
            "timezone_id": fingerprint["timezone"],
            "device_scale_factor": 1.0,
            "has_touch": False,
            "is_mobile": False,
        })
        return context_options

    def get_init_script(self, fingerprint: Dict) -> str:
        """Build a browser init script to spoof common fingerprint surfaces."""
        fp_payload = {
            "languages": fingerprint.get("languages", ["zh-CN", "zh"]),
            "hardwareConcurrency": fingerprint.get("hardware_concurrency", 8),
            "deviceMemory": fingerprint.get("device_memory", 8),
            "maxTouchPoints": fingerprint.get("max_touch_points", 0),
            "webglVendor": fingerprint.get("webgl_vendor", "Google Inc. (Intel)"),
            "webglRenderer": fingerprint.get("webgl_renderer", "ANGLE (Intel)"),
            "canvasFp": fingerprint.get("canvas_fp", ""),
            "colorDepth": fingerprint.get("color_depth", 24),
            "pixelDepth": fingerprint.get("pixel_depth", 24),
            "plugins": fingerprint.get("plugins", []),
            "mimeTypes": fingerprint.get("mime_types", []),
            "fonts": fingerprint.get("fonts", []),
            "mediaDevices": fingerprint.get("media_devices", []),
            "clientHints": fingerprint.get("client_hints", {}),
            "audioNoise": fingerprint.get("audio_noise", 0.0001),
            "webrtcMode": fingerprint.get("webrtc_mode", "mask"),
            "platform": fingerprint.get("platform", "Win32"),
        }
        fp_json = json.dumps(fp_payload)

        return f"""
        (() => {{
            const fp = {fp_json};

            Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
            Object.defineProperty(navigator, 'platform', {{ get: () => fp.platform }});

            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                if (parameter === 37445) return fp.webglVendor;
                if (parameter === 37446) return fp.webglRenderer;
                return getParameter.apply(this, arguments);
            }};

            Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => fp.hardwareConcurrency }});
            Object.defineProperty(navigator, 'deviceMemory', {{ get: () => fp.deviceMemory }});
            Object.defineProperty(navigator, 'maxTouchPoints', {{ get: () => fp.maxTouchPoints }});
            Object.defineProperty(navigator, 'languages', {{ get: () => fp.languages }});

            const toDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {{
                const result = toDataURL.apply(this, arguments);
                return result + fp.canvasFp;
            }};

            try {{
                Object.defineProperty(Notification, 'permission', {{ get: () => 'default' }});
            }} catch (e) {{}}

            Object.defineProperty(screen, 'colorDepth', {{ get: () => fp.colorDepth }});
            Object.defineProperty(screen, 'pixelDepth', {{ get: () => fp.pixelDepth }});

            const makeArrayLike = (items, nameKey) => {{
                const arr = items.map((item) => Object.assign({{}}, item));
                arr.item = (i) => arr[i] || null;
                arr.namedItem = (name) => arr.find((x) => x[nameKey] === name) || null;
                return arr;
            }};
            try {{
                const plugins = makeArrayLike(fp.plugins || [], 'name');
                Object.defineProperty(navigator, 'plugins', {{ get: () => plugins }});
                const mimeTypes = makeArrayLike(fp.mimeTypes || [], 'type');
                Object.defineProperty(navigator, 'mimeTypes', {{ get: () => mimeTypes }});
            }} catch (e) {{}}

            try {{
                const fontSet = new Set(fp.fonts || []);
                if (document.fonts && document.fonts.check) {{
                    const origCheck = document.fonts.check.bind(document.fonts);
                    document.fonts.check = (query) => {{
                        const match = /"([^"]+)"/.exec(query);
                        if (match && match[1]) {{
                            return fontSet.has(match[1]);
                        }}
                        return origCheck(query);
                    }};
                }}
            }} catch (e) {{}}

            try {{
                if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {{
                    navigator.mediaDevices.enumerateDevices = async () => (fp.mediaDevices || []);
                }}
            }} catch (e) {{}}

            try {{
                const data = fp.clientHints || {{}};
                const uaData = {{
                    brands: data.brands || [],
                    mobile: !!data.mobile,
                    platform: data.platform || 'Windows',
                    getHighEntropyValues: async (hints) => {{
                        const out = {{}};
                        (hints || []).forEach((key) => {{
                            if (key === 'architecture') out.architecture = data.architecture || 'x86';
                            if (key === 'bitness') out.bitness = data.bitness || '64';
                            if (key === 'model') out.model = data.model || '';
                            if (key === 'platform') out.platform = data.platform || 'Windows';
                            if (key === 'platformVersion') out.platformVersion = data.platform_version || '10.0.0';
                            if (key === 'uaFullVersion') out.uaFullVersion = data.ua_full_version || '';
                            if (key === 'fullVersionList') out.fullVersionList = data.brands || [];
                            if (key === 'wow64') out.wow64 = !!data.wow64;
                        }});
                        return out;
                    }}
                }};
                Object.defineProperty(navigator, 'userAgentData', {{ get: () => uaData }});
            }} catch (e) {{}}

            try {{
                const getChannelData = AudioBuffer.prototype.getChannelData;
                AudioBuffer.prototype.getChannelData = function() {{
                    const data = getChannelData.apply(this, arguments);
                    for (let i = 0; i < data.length; i += 100) {{
                        data[i] = data[i] + (Math.random() * fp.audioNoise);
                    }}
                    return data;
                }};
            }} catch (e) {{}}

            try {{
                if (fp.webrtcMode === 'mask') {{
                    RTCPeerConnection.prototype.addIceCandidate = function() {{
                        return Promise.resolve();
                    }};
                    const origCreateOffer = RTCPeerConnection.prototype.createOffer;
                    RTCPeerConnection.prototype.createOffer = async function() {{
                        const offer = await origCreateOffer.apply(this, arguments);
                        offer.sdp = offer.sdp.replace(/a=candidate:.*

/g, '');
                        return offer;
                    }};
                }}
            }} catch (e) {{}}
        }})();
        """


# Global instance
device_fingerprint_manager = DeviceFingerprint()
