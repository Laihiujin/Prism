#!/usr/bin/env python3
"""测试配置读取"""
import sys
import os
from pathlib import Path

# 添加 syn_backend 到路径
sys.path.insert(0, str(Path(__file__).parent / "syn_backend"))

print("=" * 60)
print("测试配置读取")
print("=" * 60)

# 测试环境变量
print(f"\n1. 直接读取环境变量:")
print(f"   PLAYWRIGHT_HEADLESS (env) = {os.getenv('PLAYWRIGHT_HEADLESS', 'NOT SET')}")

# 测试从 config.conf 导入
try:
    from config.conf import PLAYWRIGHT_HEADLESS
    print(f"\n2. 从 config.conf 导入:")
    print(f"   PLAYWRIGHT_HEADLESS = {PLAYWRIGHT_HEADLESS}")
    print(f"   类型: {type(PLAYWRIGHT_HEADLESS)}")
    print(f"   浏览器窗口: {'隐藏 (headless)' if PLAYWRIGHT_HEADLESS else '显示 (visible)'}")
except Exception as e:
    print(f"\n2. 导入配置失败: {e}")

print("\n" + "=" * 60)
