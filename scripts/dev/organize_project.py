"""
项目文件整理脚本
Organize project files into proper directories
"""
import os
import shutil
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent

# 文件分类
FILE_CATEGORIES = {
    'tests': [
        'test_*.py',
    ],
    'scripts': [
        'add_ai_config.py',
        'add_chat_config_via_api.py',
        'update_chat_config.py',
        'diagnose_celery.bat',
        'parse_video_data.py',
    ],
    'data/videos': [
        'douyin_video_data.json',
        'douyin_video_data_detailed.json',
    ],
    'logs': [
        '*.log',
    ],
    'docs': [
        '*.md',
        '*.txt',
    ],
    'build': [
        'build-*.bat',
        'clean-dist.bat',
    ],
}

def move_files_by_pattern(target_dir: str, patterns: list):
    """移动匹配模式的文件到目标目录"""
    target_path = ROOT_DIR / target_dir
    target_path.mkdir(parents=True, exist_ok=True)

    moved_files = []
    for pattern in patterns:
        for file_path in ROOT_DIR.glob(pattern):
            # 跳过目录和特殊文件
            if file_path.is_dir() or file_path.name.startswith('.'):
                continue

            # 跳过已经在目标目录中的文件
            if file_path.parent == target_path:
                continue

            # 移动文件
            try:
                dest = target_path / file_path.name
                if dest.exists():
                    print(f"[SKIP] {file_path.name} -> {target_dir}/ (already exists)")
                else:
                    shutil.move(str(file_path), str(dest))
                    moved_files.append(file_path.name)
                    print(f"[OK] {file_path.name} -> {target_dir}/")
            except Exception as e:
                print(f"[ERROR] {file_path.name} - {e}")

    return moved_files

def main():
    print("=" * 60)
    print("Project File Organization")
    print("=" * 60)
    print()

    # 创建 .gitignore（如果不存在）
    gitignore_path = ROOT_DIR / '.gitignore'
    if not gitignore_path.exists():
        gitignore_content = """# Data files
data/
*.json

# Log files
logs/
*.log

# Temp files
*.tmp
*.temp
dump.rdb
nul

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# Node
node_modules/

# Environment
.env
.env.local
synenv/

# Build artifacts
desktop-electron/dist/
"""
        gitignore_path.write_text(gitignore_content, encoding='utf-8')
        print("[OK] Created .gitignore")

    print()
    print("Starting file organization...")
    print()

    # 按分类移动文件
    total_moved = 0
    for target_dir, patterns in FILE_CATEGORIES.items():
        print(f"\n[DIR] {target_dir}/")
        print("-" * 60)
        moved = move_files_by_pattern(target_dir, patterns)
        total_moved += len(moved)

    print()
    print("=" * 60)
    print(f"Complete! Moved {total_moved} files")
    print("=" * 60)
    print()
    print("Organized directory structure:")
    print("├── tests/          # Test scripts")
    print("├── scripts/        # Utility scripts")
    print("├── data/          # Data files")
    print("├── logs/          # Log files")
    print("├── docs/          # Documentation")
    print("└── build/         # Build scripts")
    print()

if __name__ == "__main__":
    main()
