"""
Quick fix script for GetFileDetailTool
"""

# Manual fix: Edit lines 1372-1386 in manus_tools.py

# Change line 1372-1373:
# OLD:
#                 result = response.json()
#                 file_data = result.get("data", {})

# NEW:
#                 # API directly returns FileResponse, no .get("data") needed
#                 file_data = response.json()

# Remove line 1378 (file_type):
# OLD:
#                 output += f"- 类型: {file_data.get('file_type')}\\n"
# NEW:
#                 # (remove this line)

# Change line 1380:
# OLD:
#                 output += f"- 大小: {file_data.get('size', 0) / 1024 / 1024:.2f} MB\\n"
# NEW:
#                 output += f"- 大小: {file_data.get('filesize', 0):.2f} MB\\n"

# Change line 1382-1383:
# OLD:
#                 if file_data.get('duration'):
#                     output += f"- 时长: {file_data.get('duration')}秒\\n"
# NEW:
#                 if file_data.get('duration'):
#                     output += f"- 时长: {file_data.get('duration'):.2f}秒\\n"

# Change line 1386:
# OLD:
#                 output += f"- 上传时间: {file_data.get('created_at', 'N/A')}\\n"
# NEW:
#                 output += f"- 上传时间: {file_data.get('upload_time', 'N/A')}\\n"

print(__doc__)
