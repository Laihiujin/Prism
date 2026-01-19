"""
为现有Cookie文件补充user_info字段
直接更新所有平台的cookie文件
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "syn_backend"))
from myUtils.cookie_manager import cookie_manager

print("="*70)
print("开始更新现有Cookie文件的user_info字段")
print("="*70)

# 获取所有账号
all_accounts = cookie_manager.list_flat_accounts()

stats = {
    'total': len(all_accounts),
    'updated': 0,
    'no_file': 0,
    'failed': 0
}

for i, account in enumerate(all_accounts, 1):
    account_id = account['account_id']
    platform = account['platform']
    name = account['name']
    cookie_file = account.get('cookie_file')

    print(f"\n[{i}/{stats['total']}] {platform:12s} | {name}")

    if not cookie_file:
        print("  -> 跳过: 无Cookie文件")
        stats['no_file'] += 1
        continue

    cookie_path = Path(__file__).parent.parent.parent / 'syn_backend' / 'cookiesFile' / cookie_file
    if not cookie_path.exists():
        # 尝试config目录
        cookie_path = Path(__file__).parent.parent.parent / 'config' / 'cookiesFile' / cookie_file
        if not cookie_path.exists():
            print(f"  -> 跳过: 文件不存在")
            stats['no_file'] += 1
            continue

    try:
        # 读取cookie文件
        with open(cookie_path, 'r', encoding='utf-8') as f:
            cookie_data = json.load(f)

        # 检查是否已经有user_info字段
        if 'user_info' in cookie_data and cookie_data['user_info'].get('user_id'):
            print(f"  -> 已有user_info: {cookie_data['user_info']}")
            continue

        # 提取user_info
        user_info = {
            'user_id': None,
            'name': None,
            'avatar': None
        }

        # 1. 从cookie字段中提取user_id
        user_id = cookie_manager._extract_user_id_from_cookie(platform, cookie_data)
        if user_id:
            user_info['user_id'] = user_id
            print(f"  [ID] {user_id}")

        # 2. 小红书特殊处理: 从localStorage提取完整信息
        if platform == 'xiaohongshu' and 'origins' in cookie_data:
            for origin in cookie_data.get('origins', []):
                for item in origin.get('localStorage', []):
                    if item.get('name') == 'USER_INFO_FOR_BIZ':
                        try:
                            user_info_str = item.get('value', '')
                            user_data = json.loads(user_info_str)
                            user_info['user_id'] = user_data.get('redId')
                            user_info['name'] = user_data.get('userName')
                            user_info['avatar'] = user_data.get('userAvatar')
                            print(f"  [Name] {user_info['name']}")
                            print(f"  [Avatar] {user_info['avatar'][:60] if user_info['avatar'] else 'N/A'}...")
                            break
                        except Exception as e:
                            print(f"  警告: 解析USER_INFO_FOR_BIZ失败: {e}")

        # 3. 如果提取到了user_id，添加user_info字段
        if user_info['user_id']:
            cookie_data['user_info'] = user_info

            # 保存更新后的cookie文件
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2)

            print(f"  -> OK 已更新user_info字段")
            stats['updated'] += 1

            # 同时更新数据库
            updates = {'user_id': user_info['user_id']}
            if user_info['name']:
                updates['name'] = user_info['name']
            if user_info['avatar']:
                updates['avatar'] = user_info['avatar']

            cookie_manager.update_account(account_id, **updates)
            print(f"  -> OK 数据库已同步")
        else:
            print(f"  -> 跳过: 无法提取user_id")
            stats['failed'] += 1

    except Exception as e:
        print(f"  -> ERROR: {e}")
        stats['failed'] += 1

# 打印统计
print("\n" + "="*70)
print("更新完成")
print("="*70)
print(f"总数:   {stats['total']}")
print(f"已更新: {stats['updated']}")
print(f"无文件: {stats['no_file']}")
print(f"失败:   {stats['failed']}")
print("="*70)
