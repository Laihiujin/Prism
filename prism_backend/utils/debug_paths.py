from pathlib import Path
import sys
import os

print(f"__file__: {__file__}")
print(f"Path(__file__).resolve(): {Path(__file__).resolve()}")
print(f"Path(__file__).resolve().parent: {Path(__file__).resolve().parent}")
try:
    from config.conf import BASE_DIR
    print(f"BASE_DIR: {BASE_DIR}")
except ImportError:
    print("Could not import conf")

stealth_path = Path(__file__).resolve().parent / "stealth.min.js"
print(f"Calculated stealth path: {stealth_path}")
print(f"Exists: {stealth_path.exists()}")
