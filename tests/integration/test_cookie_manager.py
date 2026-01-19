"""
完整测试Cookie提取流程
"""
import sys
import io
from pathlib import Path

# 设置UTF-8编码输出（Windows兼容）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent / "syn_backend"))

from myUtils.cookie_manager import cookie_manager

# 测试提取
cookie_file = "ffe0d3a1-cba7-11f0-87f6-00a747280720.json"
cookie_path = Path("syn_backend/cookiesFile") / cookie_file

print(f"测试文件: {cookie_file}")
print(f"文件路径: {cookie_path}")
print(f"文件存在: {cookie_path.exists()}")

# 读取Cookie
cookie_data = cookie_manager._read_cookie_file(cookie_path)
print(f"\ncookie_data 类型: {type(cookie_data)}")
print(f"cookie_data 键: {cookie_data.keys() if isinstance(cookie_data, dict) else 'N/A'}")

# 提取user_id
user_id = cookie_manager._extract_user_id_from_cookie('kuaishou', cookie_data)
print(f"\n提取到的user_id: {user_id}")
