"""
修复未入库的 Cookie 文件
扫描 cookiesFile 目录，将所有 cookie 文件添加到数据库
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "syn_backend"))

from myUtils.cookie_manager import cookie_manager
from loguru import logger

def identify_platform_from_filename(filename: str) -> str:
    """从文件名识别平台"""
    name_lower = filename.lower()
    if "bilibili" in name_lower:
        return "bilibili"
    if "kuaishou" in name_lower:
        return "kuaishou"
    if "douyin" in name_lower:
        return "douyin"
    if "xiaohongshu" in name_lower:
        return "xiaohongshu"
    if "tencent" in name_lower or "channels" in name_lower:
        return "channels"
    return "unknown"

def main():
    print("=" * 80)
    print("扫描并修复未入库的 Cookie 文件")
    print("=" * 80)

    cookie_dir = Path(__file__).parent.parent / "syn_backend" / "cookiesFile"

    if not cookie_dir.exists():
        print(f"[ERROR] Cookie 目录不存在: {cookie_dir}")
        return

    # 获取所有 cookie 文件
    cookie_files = list(cookie_dir.glob("*.json"))
    print(f"\n找到 {len(cookie_files)} 个 Cookie 文件")

    # 获取数据库中已有的账号
    db_accounts = cookie_manager.list_flat_accounts()
    db_files = {acc['cookie_file'] for acc in db_accounts}
    print(f"数据库中已有 {len(db_accounts)} 个账号")

    # 找出未入库的文件
    missing_files = []
    for file in cookie_files:
        if file.name not in db_files:
            missing_files.append(file)

    if not missing_files:
        print("\n[OK] 所有 Cookie 文件都已入库")
        return

    print(f"\n[!] 发现 {len(missing_files)} 个未入库的文件：")
    for file in missing_files:
        print(f"  - {file.name}")

    print("\n开始导入...")

    success_count = 0
    error_count = 0

    for file in missing_files:
        try:
            # 读取 cookie 数据
            with open(file, 'r', encoding='utf-8') as f:
                cookie_data = json.load(f)

            # 识别平台
            platform = identify_platform_from_filename(file.name)
            if platform == "unknown":
                print(f"  [SKIP] 跳过未知平台: {file.name}")
                continue

            # 提取账号ID（从文件名）
            account_id = file.stem  # 去掉 .json 后缀

            # 构建账号详情
            account_details = {
                'id': account_id,
                'name': account_id,  # 初始使用 account_id 作为名称
                'status': 'unchecked',  # 标记为未检查，后续可以验证
                'cookie': cookie_data,
                'note': '数据修复导入'
            }

            # 尝试添加账号
            print(f"  [+] 导入: {file.name} ({platform})", end=" ")
            cookie_manager.add_account(
                platform_name=platform,
                account_details=account_details
            )
            print("[OK]")
            success_count += 1

        except Exception as e:
            print(f"  [ERROR] 导入失败: {file.name} - {e}")
            error_count += 1
            logger.error(f"导入失败: {file.name} - {e}")

    print("\n" + "=" * 80)
    print(f"[DONE] 导入完成: 成功 {success_count} 个, 失败 {error_count} 个")
    print("=" * 80)

    # 显示最终统计
    db_accounts_after = cookie_manager.list_flat_accounts()
    print(f"\n最终数据库账号数: {len(db_accounts_after)} 个")

if __name__ == "__main__":
    main()
