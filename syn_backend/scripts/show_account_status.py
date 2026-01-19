import sys
import io
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from myUtils.cookie_manager import cookie_manager

accounts = cookie_manager.list_flat_accounts()

print('\n' + '='*80)
print('📊 当前所有账号状态')
print('='*80 + '\n')

for i, acc in enumerate(accounts, 1):
    status_icon = {
        'valid': '✅',
        'expired': '❌',
        'file_missing': '📁',
        'unchecked': '❓'
    }.get(acc['status'], '⚠️')

    print(f"{i}. {status_icon} [{acc['status']:12s}] {acc.get('name', 'N/A'):25s}")
    print(f"   平台: {acc.get('platform', 'N/A'):12s} | UserID: {acc.get('user_id', 'N/A')}")
    print(f"   Cookie文件: {acc.get('cookie_file', 'N/A')}")
    print()

# 统计
status_count = {}
for acc in accounts:
    status = acc['status']
    status_count[status] = status_count.get(status, 0) + 1

print('='*80)
print('📈 统计汇总')
print('='*80)
for status, count in sorted(status_count.items()):
    status_icon = {
        'valid': '✅',
        'expired': '❌',
        'file_missing': '📁',
        'unchecked': '❓'
    }.get(status, '⚠️')
    print(f"{status_icon} {status}: {count} 个")
