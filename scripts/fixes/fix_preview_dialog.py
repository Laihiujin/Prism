#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Remove duplicate close button from materials preview dialog
"""

from pathlib import Path

materials_file = Path(r"d:\SynapseAutomation\syn_frontend_react\src\app\materials\page.tsx")

# Read file
content = materials_file.read_text(encoding='utf-8')

# Target pattern to remove (the custom close button)
old_section = '''              })()}
              <div className="absolute top-2 right-2 z-10">
                <Button
                  size="icon"
                  variant="secondary"
                  className="rounded-full bg-black/50 hover:bg-black/70 text-white"
                  onClick={() => setPreviewMaterial(null)}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </div>'''

new_section = '''              })()}
            </div>'''

if old_section in content:
    new_content = content.replace(old_section, new_section)
    materials_file.write_text(new_content, encoding='utf-8')
    print("✓ Successfully removed duplicate close button from preview dialog")
    print("  The Dialog component's built-in close button will be used instead")
else:
    print("✗ Pattern not found - file may have been already modified")
    print("\nSearching for similar patterns...")
    # Try to find the button element
    if 'absolute top-2 right-2 z-10' in content:
        print("  Found: Custom close button div exists")
    if 'onClick={() => setPreviewMaterial(null)}' in content:
        print("  Found: Close button onClick handler exists")
