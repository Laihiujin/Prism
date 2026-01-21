"""
浏览器配置迁移脚本
将所有上传器从硬编码路径迁移到自动检测模块
"""
import os
import re
from pathlib import Path


def migrate_uploader_file(file_path: Path) -> bool:
    """
    迁移单个上传器文件
    
    Args:
        file_path: 上传器文件路径
        
    Returns:
        bool: 是否成功迁移
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # 1. 替换 import 语句
        content = re.sub(
            r'from config\.conf import LOCAL_CHROME_PATH',
            'from utils.chrome_detector import get_chrome_executable',
            content
        )
        
        # 2. 替换赋值语句
        content = re.sub(
            r'self\.local_executable_path = LOCAL_CHROME_PATH',
            'self.local_executable_path = get_chrome_executable()',
            content
        )
        
        # 3. 如果有变化，写回文件
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            print(f"✓ 已迁移: {file_path.relative_to(Path.cwd())}")
            return True
        else:
            print(f"- 跳过（无需迁移）: {file_path.relative_to(Path.cwd())}")
            return False
            
    except Exception as e:
        print(f"✗ 迁移失败: {file_path.relative_to(Path.cwd())} - {e}")
        return False


def find_uploader_files() -> list[Path]:
    """
    查找所有需要迁移的上传器文件
    
    Returns:
        list[Path]: 上传器文件路径列表
    """
    uploader_dir = Path(__file__).parent.parent / "uploader"
    
    if not uploader_dir.exists():
        print(f"✗ 上传器目录不存在: {uploader_dir}")
        return []
    
    # 查找所有 main.py 和 main_chrome.py
    files = []
    for pattern in ["**/main.py", "**/main_chrome.py"]:
        files.extend(uploader_dir.glob(pattern))
    
    return files


def main():
    """主函数"""
    print("=" * 60)
    print("浏览器配置迁移脚本")
    print("=" * 60)
    print()
    
    # 查找文件
    files = find_uploader_files()
    
    if not files:
        print("✗ 未找到需要迁移的文件")
        return
    
    print(f"找到 {len(files)} 个文件需要检查:")
    print()
    
    # 迁移文件
    migrated_count = 0
    for file_path in files:
        if migrate_uploader_file(file_path):
            migrated_count += 1
    
    print()
    print("=" * 60)
    print(f"迁移完成: {migrated_count}/{len(files)} 个文件已更新")
    print("=" * 60)
    print()
    print("下一步:")
    print("1. 检查迁移结果")
    print("2. 运行测试确保功能正常")
    print("3. 安装 Playwright 浏览器: playwright install chromium")
    print()


if __name__ == "__main__":
    main()
