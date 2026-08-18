import sys
import os
sys.path.append(os.getcwd())
try:
    import biliup
    print("biliup package found")
    print(f"Version: {getattr(biliup, '__version__', 'unknown')}")
    
    from biliup.plugins.bili_webup import BiliBili
    print("BiliBili class found")
    print(dir(BiliBili))
    
    # Check if there is a login function in plugins
    import biliup.plugins.bili_webup as webup
    print("webup module content:")
    print(dir(webup))
    
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Error: {e}")
