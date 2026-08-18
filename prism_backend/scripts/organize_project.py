"""
项目文件组织脚本
将散落的文件移动到合适的目录结构中
"""
import os
import shutil
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent

# 定义文件移动规则
MOVE_RULES = {
    # 测试文件 -> tests/legacy/
    "tests/legacy": [
        "test_all_platforms.py",
        "test_batch_publish.py",
        "test_execute_publish.py",
        "test_kuaishou_only.py",
        "test_login_qr.py",
        "test_platforms_api.py",
        "test_platforms_final.py",
        "test_routes.py",
        "test_user_id_extraction.py",
        "test_final_output.log",
        "test_report_20251127_193311.json",
        "test_report_api_20251127_200430.json",
        "test_report_final_20251127_210914.json",
        "test_report_final_20251127_212616.json",
    ],
    
    # 数据库文件 -> db/
    "db": [
        "cookie_store.db",
        "cookies.db",
        "data.db",
    ],
    
    # 维护脚本 -> scripts/maintenance/
    "scripts/maintenance": [
        "manual_sync.py",
        "sync_db_files.py",
        "check_config.py",
    ],
    
    # 工具脚本 -> scripts/utilities/
    "scripts/utilities": [
        "inspect_biliup.py",
        "read_biliup_source.py",
    ],
    
    # 废弃模块 -> archive/deprecated/
    "archive/deprecated": [
        "accounts.py",
        "campaigns.py",
        "recovery.py",
    ],
}

# 需要删除的文件
DELETE_FILES = [
    "requirements copy.txt",
    "package-lock.json",
]


def create_directories():
    """创建目标目录"""
    for target_dir in MOVE_RULES.keys():
        dir_path = BASE_DIR / target_dir
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ 创建目录: {target_dir}")


def move_files():
    """移动文件到目标目录"""
    moved_count = 0
    skipped_count = 0
    
    for target_dir, files in MOVE_RULES.items():
        for filename in files:
            source = BASE_DIR / filename
            destination = BASE_DIR / target_dir / filename
            
            if source.exists():
                try:
                    shutil.move(str(source), str(destination))
                    print(f"✓ 移动: {filename} -> {target_dir}/")
                    moved_count += 1
                except Exception as e:
                    print(f"✗ 错误: 移动 {filename} 失败 - {e}")
            else:
                print(f"⊘ 跳过: {filename} (文件不存在)")
                skipped_count += 1
    
    return moved_count, skipped_count


def delete_files():
    """删除不需要的文件"""
    deleted_count = 0
    
    for filename in DELETE_FILES:
        file_path = BASE_DIR / filename
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"✓ 删除: {filename}")
                deleted_count += 1
            except Exception as e:
                print(f"✗ 错误: 删除 {filename} 失败 - {e}")
        else:
            print(f"⊘ 跳过: {filename} (文件不存在)")
    
    return deleted_count


def create_readme_files():
    """在新目录中创建 README 说明文件"""
    readmes = {
        "tests/legacy/README.md": """# Legacy Tests

这个目录包含旧的测试文件,这些测试是在项目早期创建的。

## 注意事项
- 这些测试可能已经过时
- 建议使用 `tests/unit/` 和 `tests/integration/` 中的新测试
- 保留这些文件仅供参考
""",
        "archive/deprecated/README.md": """# Deprecated Modules

这个目录包含已废弃的模块入口文件。

## 说明
- 这些文件已被 FastAPI 模块化结构取代
- 保留仅供历史参考
- 不应在新代码中使用
""",
        "scripts/maintenance/README.md": """# Maintenance Scripts

维护和管理脚本。

## 脚本说明
- `manual_sync.py`: 手动数据库同步
- `sync_db_files.py`: 数据库文件同步
- `check_config.py`: 配置检查
""",
        "scripts/utilities/README.md": """# Utility Scripts

工具脚本集合。

## 脚本说明
- `inspect_biliup.py`: Biliup 检查工具
- `read_biliup_source.py`: Biliup 源码读取
""",
    }
    
    for path, content in readmes.items():
        readme_path = BASE_DIR / path
        readme_path.parent.mkdir(parents=True, exist_ok=True)
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ 创建: {path}")


def main():
    print("=" * 60)
    print("项目文件组织工具")
    print("=" * 60)
    print()
    
    print("步骤 1: 创建目标目录...")
    create_directories()
    print()
    
    print("步骤 2: 移动文件...")
    moved, skipped = move_files()
    print()
    
    print("步骤 3: 删除不需要的文件...")
    deleted = delete_files()
    print()
    
    print("步骤 4: 创建 README 文件...")
    create_readme_files()
    print()
    
    print("=" * 60)
    print("完成!")
    print(f"移动文件: {moved} 个")
    print(f"跳过文件: {skipped} 个")
    print(f"删除文件: {deleted} 个")
    print("=" * 60)


if __name__ == "__main__":
    # 确认操作
    print("此脚本将重新组织项目文件结构。")
    print("建议先备份重要文件!")
    print()
    response = input("是否继续? (yes/no): ")
    
    if response.lower() in ['yes', 'y']:
        main()
    else:
        print("操作已取消。")
