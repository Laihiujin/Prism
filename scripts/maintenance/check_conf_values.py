import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'syn_backend'))
from config.conf import LOCAL_CHROME_PATH, BASE_DIR

print(f"LOCAL_CHROME_PATH: {LOCAL_CHROME_PATH}")
print(f"BASE_DIR: {BASE_DIR}")
print(f"Chrome Exists? {os.path.exists(LOCAL_CHROME_PATH)}")
