#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Fix campaigns router mount point in main.py
"""

import sys
from pathlib import Path

main_py = Path(r"d:\SynapseAutomation\syn_backend\fastapi_app\main.py")

# Read the file
content = main_py.read_text(encoding='utf-8')

# Replace the incorrect mount point
old_line = 'app.include_router(campaigns_router, prefix="/api/campaigns"'
new_line = 'app.include_router(campaigns_router, prefix="/api/v1"'

if old_line in content:
    new_content = content.replace(old_line, new_line)
    main_py.write_text(new_content, encoding='utf-8')
    print(f"✓ Fixed: Changed campaigns router from /api/campaigns to /api/v1")
    print(f"  This allows frontend to call /api/v1/campaigns/... correctly")
else:
    print(f"✗ Pattern not found in main.py")
    print(f"  Looking for: {old_line}")

print("\nCurrent campaigns router configuration:")
for i, line in enumerate(content.split('\n'), 1):
    if 'campaigns_router' in line and 'include_router' in line:
        print(f"  Line {i}: {line.strip()}")
