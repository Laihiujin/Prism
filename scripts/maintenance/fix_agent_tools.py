#!/usr/bin/env python3
"""
修复 GetFileDetailTool 的数据格式问题
"""
import sys
from pathlib import Path

def fix_get_file_detail_tool():
    """修复 GetFileDetailTool 的代码"""
    file_path = Path(__file__).parent / "prism_backend" / "fastapi_app" / "agent" / "manus_tools.py"

    # 读取文件
    content = file_path.read_text(encoding='utf-8')

    # 需要替换的旧代码块
    old_code = """            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{API_BASE_URL}/files/{file_id}")
                response.raise_for_status()
                result = response.json()
                file_data = result.get("data", {})

                output = f"📄 文件详情：\\n\\n"
                output += f"- ID: {file_data.get('id')}\\n"
                output += f"- 文件名: {file_data.get('filename')}\\n"
                output += f"- 类型: {file_data.get('file_type')}\\n"
                output += f"- 路径: {file_data.get('file_path')}\\n"
                output += f"- 大小: {file_data.get('size', 0) / 1024 / 1024:.2f} MB\\n"

                if file_data.get('duration'):
                    output += f"- 时长: {file_data.get('duration')}秒\\n"

                output += f"- 状态: {file_data.get('status', 'unknown')}\\n"
                output += f"- 上传时间: {file_data.get('created_at', 'N/A')}\\n"

                return ToolResult(output=output)"""

    # 新的正确代码
    new_code = """            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{API_BASE_URL}/files/{file_id}")
                response.raise_for_status()
                # API 直接返回 FileResponse 对象，无需 .get("data")
                file_data = response.json()

                output = f"📄 文件详情：\\n\\n"
                output += f"- ID: {file_data.get('id')}\\n"
                output += f"- 文件名: {file_data.get('filename')}\\n"
                output += f"- 路径: {file_data.get('file_path')}\\n"
                # API 返回的是 filesize (MB)，已经是 MB 单位
                output += f"- 大小: {file_data.get('filesize', 0):.2f} MB\\n"

                if file_data.get('duration'):
                    output += f"- 时长: {file_data.get('duration'):.2f}秒\\n"

                output += f"- 状态: {file_data.get('status', 'unknown')}\\n"
                # API 返回的是 upload_time 而不是 created_at
                output += f"- 上传时间: {file_data.get('upload_time', 'N/A')}\\n"

                return ToolResult(output=output)"""

    # 检查旧代码是否存在
    if old_code not in content:
        print("[ERROR] Could not find code block to replace")
        print("        File may have been modified or code format doesn't match exactly")
        return False

    # 替换代码
    new_content = content.replace(old_code, new_code, 1)

    # 确保只替换了一次
    if content.count(old_code) > 1:
        print("[WARNING] Found multiple matching code blocks, only replaced the first one")

    # 写回文件
    file_path.write_text(new_content, encoding='utf-8')
    print(f"[SUCCESS] Fixed {file_path}")
    return True

if __name__ == "__main__":
    success = fix_get_file_detail_tool()
    sys.exit(0 if success else 1)
