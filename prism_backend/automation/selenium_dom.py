from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from loguru import logger

from .ocr_client import ocr_image_bytes
from utils.playwright_bootstrap import ensure_playwright_chromium_installed


@dataclass
class SeleniumCaptureResult:
    url: str
    html_path: Path
    screenshot_path: Path
    ocr_text_path: Optional[Path] = None


def new_chrome_driver(headless: bool = False, user_data_dir: Optional[str] = None) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # Prefer bundled Playwright Chromium so the project is self-contained.
    try:
        r = ensure_playwright_chromium_installed(auto_install=False)
        if r.chromium_executable:
            opts.binary_location = r.chromium_executable
    except Exception:
        pass
    if user_data_dir:
        opts.add_argument(f"--user-data-dir={user_data_dir}")
    return webdriver.Chrome(options=opts)


def try_click_any(driver: webdriver.Chrome, selectors: Iterable[tuple[str, str]]) -> bool:
    for by, sel in selectors:
        try:
            el = driver.find_element(by, sel)
            el.click()
            return True
        except NoSuchElementException:
            continue
        except Exception:
            continue
    return False


def capture_debug_bundle(
    driver: webdriver.Chrome,
    out_dir: str,
    prefix: str,
    run_ocr: bool = True,
) -> SeleniumCaptureResult:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    url = driver.current_url
    html_path = out / f"{prefix}.html"
    screenshot_path = out / f"{prefix}.png"

    html_path.write_text(driver.page_source, encoding="utf-8")
    driver.save_screenshot(str(screenshot_path))

    ocr_text_path: Optional[Path] = None
    if run_ocr:
        try:
            img = screenshot_path.read_bytes()
            text = ocr_image_bytes(img)
            ocr_text_path = out / f"{prefix}.ocr.txt"
            ocr_text_path.write_text(text, encoding="utf-8")
        except Exception as e:
            logger.warning(f"[Selenium] OCR failed: {e}")

    return SeleniumCaptureResult(
        url=url,
        html_path=html_path,
        screenshot_path=screenshot_path,
        ocr_text_path=ocr_text_path,
    )


def dismiss_common_popups(driver: webdriver.Chrome) -> bool:
    selectors = [
        (By.XPATH, "//button[contains(., '关闭')]"),
        (By.XPATH, "//button[contains(., '我知道了')]"),
        (By.XPATH, "//button[contains(., '知道了')]"),
        (By.XPATH, "//button[contains(., '跳过')]"),
        (By.XPATH, "//button[contains(., '下一步')]"),
        (By.CSS_SELECTOR, "[aria-label='Skip'], [aria-label='Close']"),
        (By.CSS_SELECTOR, ".close, .modal-close, .dialog-close"),
    ]
    return try_click_any(driver, selectors)


def discover_clickable_selector(driver: webdriver.Chrome, keywords: list[str]) -> Optional[str]:
    """
    Try to discover a stable CSS selector for a visible close/skip button.
    Returns something like '#id', '[aria-label=\"Skip\"]', or 'button.class1.class2'.
    """
    try:
        for aria in ["Skip", "Close"]:
            try:
                el = driver.find_element(By.CSS_SELECTOR, f"[aria-label='{aria}']")
                if el:
                    return f"[aria-label='{aria}']"
            except Exception:
                pass

        for kw in keywords:
            if not kw:
                continue
            xpath = f"//button[contains(., '{kw}')] | //div[contains(@role,'button') and contains(., '{kw}')]"
            try:
                el = driver.find_element(By.XPATH, xpath)
            except Exception:
                continue
            if not el:
                continue

            el_id = (el.get_attribute('id') or '').strip()
            if el_id:
                return f"#{el_id}"
            aria = (el.get_attribute('aria-label') or '').strip()
            if aria:
                return f"[aria-label='{aria}']"
            classes = (el.get_attribute('class') or '').strip().split()
            tag = (el.tag_name or 'button').strip() or 'button'
            safe = []
            for c in classes:
                if c and all(ch.isalnum() or ch in ('-', '_') for ch in c):
                    safe.append(c)
                if len(safe) >= 3:
                    break
            if safe:
                return tag + "".join([f".{c}" for c in safe])
            return tag
    except Exception:
        return None
    return None
