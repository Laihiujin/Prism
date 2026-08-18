#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频转码工具 - 将 H.265/HEVC 视频转换为 H.264
用于解决视频号不支持 H.265 的问题
"""
import subprocess
import json
from pathlib import Path
from typing import Optional, Tuple
from utils.log import get_logger

logger = get_logger("video_transcoder")


def get_video_codec(file_path: str) -> Optional[str]:
    """
    获取视频编码格式

    Args:
        file_path: 视频文件路径

    Returns:
        编码格式 (如 'h264', 'hevc', 'vp9') 或 None
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=codec_name', '-of', 'json', file_path],
            capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            if streams:
                return streams[0].get('codec_name')
    except Exception as e:
        logger.error(f"获取视频编码失败: {e}")

    return None


def is_h265_video(file_path: str) -> bool:
    """
    检查视频是否为 H.265/HEVC 编码

    Args:
        file_path: 视频文件路径

    Returns:
        是否为 H.265
    """
    codec = get_video_codec(file_path)
    if not codec:
        return False

    return codec.lower() in ['hevc', 'h265']


def transcode_to_h264(
    input_path: str,
    output_path: Optional[str] = None,
    preset: str = 'medium',
    crf: int = 23
) -> Tuple[bool, str]:
    """
    将视频转码为 H.264 格式

    Args:
        input_path: 输入视频路径
        output_path: 输出路径（如果为 None，则自动生成）
        preset: FFmpeg 预设 (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)
        crf: 质量参数 (18-28，越小质量越好，23为推荐值)

    Returns:
        (成功标志, 输出文件路径或错误信息)
    """
    input_file = Path(input_path)

    if not input_file.exists():
        return False, f"输入文件不存在: {input_path}"

    # 自动生成输出路径
    if output_path is None:
        output_file = input_file.parent / f"{input_file.stem}_h264{input_file.suffix}"
    else:
        output_file = Path(output_path)

    # 构建 FFmpeg 命令
    # -c:v libx264: 使用 H.264 编码器
    # -preset: 编码速度预设
    # -crf: 质量参数
    # -c:a copy: 音频直接复制（不重新编码）
    # -movflags +faststart: 优化流媒体播放
    cmd = [
        'ffmpeg',
        '-i', str(input_file),
        '-c:v', 'libx264',
        '-preset', preset,
        '-crf', str(crf),
        '-c:a', 'copy',
        '-movflags', '+faststart',
        '-y',  # 覆盖已存在的文件
        str(output_file)
    ]

    logger.info(f"开始转码: {input_file.name} -> {output_file.name}")
    logger.debug(f"FFmpeg 命令: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )

        if result.returncode == 0:
            logger.success(f"转码成功: {output_file}")
            return True, str(output_file)
        else:
            error_msg = result.stderr[-500:] if result.stderr else "未知错误"
            logger.error(f"转码失败: {error_msg}")
            return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = "转码超时（超过10分钟）"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"转码异常: {e}"
        logger.error(error_msg)
        return False, error_msg


def ensure_h264_compatible(
    file_path: str,
    force_transcode: bool = False
) -> Tuple[bool, str]:
    """
    确保视频为 H.264 兼容格式

    如果视频已经是 H.264，直接返回原路径
    如果是 H.265 或其他格式，则转码为 H.264

    Args:
        file_path: 视频文件路径
        force_transcode: 是否强制转码（即使已经是 H.264）

    Returns:
        (成功标志, 视频路径或错误信息)
    """
    codec = get_video_codec(file_path)

    if not codec:
        return False, "无法获取视频编码信息"

    logger.info(f"检测到视频编码: {codec}")

    # 检查是否需要转码
    is_h264 = codec.lower() in ['h264', 'avc']

    if is_h264 and not force_transcode:
        logger.info(f"视频已经是 H.264 格式，无需转码")
        return True, file_path

    # 需要转码
    if is_h264:
        logger.info(f"强制转码 H.264 视频")
    else:
        logger.warning(f"视频编码为 {codec}，需要转码为 H.264")

    return transcode_to_h264(file_path)


def check_ffmpeg_available() -> bool:
    """
    检查 FFmpeg 是否可用

    Returns:
        FFmpeg 是否已安装
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


# 快速测试
if __name__ == '__main__':
    import sys

    if not check_ffmpeg_available():
        print("❌ FFmpeg 未安装或不在 PATH 中")
        sys.exit(1)

    print("✅ FFmpeg 可用")

    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        print(f"\n测试文件: {test_file}")

        codec = get_video_codec(test_file)
        print(f"编码格式: {codec}")

        if is_h265_video(test_file):
            print("⚠️  这是 H.265 视频，建议转码")

            success, result = transcode_to_h264(test_file)
            if success:
                print(f"✅ 转码成功: {result}")
            else:
                print(f"❌ 转码失败: {result}")
