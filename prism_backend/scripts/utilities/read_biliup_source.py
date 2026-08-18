import inspect
import inspect
import biliup.plugins.bili_chromeup as chromeup

print("Source code of biliup.plugins.bili_chromeup:")
try:
    print(inspect.getsource(chromeup))
except Exception as e:
    print(f"Error reading source: {e}")
