#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查素材库中视频的编码格式"""
import sys
import json
import sqlite3
import subprocess
from pathlib import Path

# 设置输出编码为 UTF-8（Windows 兼容）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_video_codec(file_path: str) -> str:
    """使用 ffprobe 获取视频编码"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=codec_name', '-of', 'json', file_path],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            if streams:
                return streams[0].get('codec_name', '未知')
    except Exception as e:
        return f'错误: {e}'
    return '未知'

# 连接数据库
db_path = Path(__file__).parent.parent.parent / 'syn_backend' / 'db' / 'database.db'
conn = sqlite3.connect(db_path)

print("=" * 80)
print("视频编码格式检查报告")
print("=" * 80)

cursor = conn.execute("""
    SELECT id, filename, file_path
    FROM file_records
    ORDER BY upload_time DESC
    LIMIT 20
""")

h264_count = 0
h265_count = 0
other_count = 0
error_count = 0

for row in cursor.fetchall():
    file_id, filename, file_path = row

    # 检查文件是否存在（尝试多个可能的路径）
    video_base_dir = Path(__file__).parent.parent.parent / 'syn_backend' / 'videoFile'

    possible_paths = [
        Path(file_path),  # 尝试原始路径
        video_base_dir / file_path,  # 相对于 videoFile 目录
        video_base_dir / Path(file_path).name,  # 只用文件名
    ]

    actual_path = None
    for p in possible_paths:
        if p.exists():
            actual_path = p
            break

    if not actual_path:
        print(f"\n❌ [{file_id}] {filename[:40]}")
        print(f"   文件不存在: {file_path}")
        error_count += 1
        continue

    # 获取编码
    codec = get_video_codec(str(actual_path))

    # 分类统计
    if 'h264' in codec.lower() or 'avc' in codec.lower():
        icon = '✅'
        h264_count += 1
    elif 'h265' in codec.lower() or 'hevc' in codec.lower():
        icon = '⚠️'
        h265_count += 1
    elif '错误' in codec:
        icon = '❌'
        error_count += 1
    else:
        icon = '❓'
        other_count += 1

    print(f"\n{icon} [{file_id}] {filename[:40]}")
    print(f"   编码: {codec}")
    print(f"   路径: {actual_path}")

conn.close()

print("\n" + "=" * 80)
print("统计结果:")
print(f"  ✅ H.264 (视频号兼容): {h264_count} 个")
print(f"  ⚠️  H.265 (需要转码):   {h265_count} 个")
print(f"  ❓ 其他格式:            {other_count} 个")
print(f"  ❌ 错误/不存在:        {error_count} 个")
print("=" * 80)

if h265_count > 0:
    print(f"\n⚠️  发现 {h265_count} 个 H.265 视频，需要转码为 H.264 才能上传到视频号！")
