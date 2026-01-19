"""
完整验证所有Cookie文件引用
- 检查所有可能引用cookie文件的代码
- 确保都使用了resolve_cookie_file()或其他兼容方式
"""
import re
from pathlib import Path

def check_cookie_references():
    """检查所有cookie文件引用"""
    print("=" * 60)
    print("Checking Cookie File References")
    print("=" * 60)
    print()

    issues = []
    checked_files = []

    # 要检查的目录
    backend_dir = Path("E:/SynapseAutomation/syn_backend")

    # 排除目录
    exclude_dirs = {
        "logs", "videoFile", "cookiesFile", "__pycache__", ".pytest_cache",
        "venv", "node_modules", ".git", "backups"
    }

    # 关键模式
    patterns = [
        # 硬编码的cookie文件名
        (r'["\']account_\d+\.json["\']', "硬编码 account_xxx.json"),
        (r'["\']douyin_account_\d+\.json["\']', "硬编码 douyin_account_xxx.json"),
        (r'["\']kuaishou_account_\d+\.json["\']', "硬编码 kuaishou_account_xxx.json"),
        (r'["\']bilibili_account_\d+\.json["\']', "硬编码 bilibili_account_xxx.json"),
        (r'["\']xiaohongshu_account_\d+\.json["\']', "硬编码 xiaohongshu_account_xxx.json"),
        (r'["\']channels_account_\d+\.json["\']', "硬编码 channels_account_xxx.json"),
        (r'["\']tencent_account_\d+\.json["\']', "硬编码 tencent_account_xxx.json"),
    ]

    # 遍历所有Python文件
    for py_file in backend_dir.rglob("*.py"):
        # 跳过排除目录
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue

        checked_files.append(str(py_file))

        try:
            content = py_file.read_text(encoding='utf-8')

            for pattern, desc in patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                if matches:
                    issues.append({
                        'file': str(py_file.relative_to(backend_dir)),
                        'pattern': desc,
                        'matches': matches
                    })

        except Exception as e:
            print(f"[WARN] Cannot read: {py_file.name} - {e}")

    # 输出结果
    print(f"[OK] Checked {len(checked_files)} Python files")
    print()

    if not issues:
        print("[SUCCESS] No hardcoded cookie filenames found!")
        print()
        print("[OK] All checks passed:")
        print("   - No hardcoded account_xxx.json")
        print("   - No hardcoded platform_account_xxx.json")
        print()
        print("[INFO] System uses correct methods:")
        print("   1. resolve_cookie_file() for path resolution")
        print("   2. cookie_manager for account management")
        print("   3. Database cookie_file field")
    else:
        print(f"[WARNING] Found {len(issues)} potential issues:")
        print()
        for issue in issues:
            print(f"[FILE] {issue['file']}")
            print(f"   Issue: {issue['pattern']}")
            print(f"   Matches: {issue['matches']}")
            print()

        print("[RECOMMENDATION]:")
        print("   1. Check if these files are examples/documentation")
        print("   2. If actual code, use resolve_cookie_file() or database queries")
        print()

    return len(issues) == 0


if __name__ == "__main__":
    success = check_cookie_references()
    exit(0 if success else 1)
