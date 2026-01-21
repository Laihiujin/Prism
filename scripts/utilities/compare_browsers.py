#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比不同浏览器的大小"""
from pathlib import Path

def get_dir_size(path):
    """获取目录大小（MB）"""
    if not path.exists():
        return 0
    total = 0
    for entry in path.rglob('*'):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except Exception:
                pass
    return total / (1024 ** 2)

# 检查各个浏览器
chrome_test = Path('.chrome-for-testing/chrome-143.0.7499.169')
chromium = Path('.playwright-browsers/chromium-1161')
chromium_headless = Path('.playwright-browsers/chromium_headless_shell-1161')

# Firefox 在系统目录
import os
firefox_system = Path(os.path.expanduser('~')) / 'AppData' / 'Local' / 'ms-playwright' / 'firefox-1495'

print("=" * 60)
print("浏览器大小对比")
print("=" * 60)
print()

results = []

if chrome_test.exists():
    size = get_dir_size(chrome_test)
    results.append(("Chrome for Testing", size, True))
    print(f"Chrome for Testing:      {size:>8.1f} MB  [支持 H.265]")
else:
    print(f"Chrome for Testing:      未安装")

if chromium.exists():
    size = get_dir_size(chromium)
    results.append(("Playwright Chromium", size, False))
    print(f"Playwright Chromium:     {size:>8.1f} MB  [不支持 H.265]")
else:
    print(f"Playwright Chromium:     未安装")

if chromium_headless.exists():
    size = get_dir_size(chromium_headless)
    results.append(("Chromium Headless Shell", size, False))
    print(f"Chromium Headless Shell: {size:>8.1f} MB  [无头模式]")
else:
    print(f"Chromium Headless Shell: 未安装")

if firefox_system.exists():
    size = get_dir_size(firefox_system)
    results.append(("Firefox", size, True))
    print(f"Firefox (Playwright):    {size:>8.1f} MB  [轻量级，需测试 H.265]")
else:
    print(f"Firefox (Playwright):    未安装")

print()
print("=" * 60)
print("推荐:")
print("  - 视频号:    Chrome for Testing (完整功能 + H.265 支持)")
print("  - 其他平台:  Firefox (轻量级) 或 Playwright Chromium")
print("=" * 60)

# Firefox 安装位置说明
print()
print("注意:")
print(f"  - Firefox 安装在系统目录: {firefox_system}")
print(f"  - 其他浏览器在项目目录: .playwright-browsers/")
print(f"  - Chrome for Testing 在: .chrome-for-testing/")
print()
print("如何使用不同浏览器:")
print("  - 视频号 (tencent_uploader):  已强制使用 Chrome for Testing")
print("  - 其他平台: 在 browser_context.py 中配置 executable_path")
print("  - Firefox 路径示例: playwright.firefox.launch()")

