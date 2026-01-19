"""
使用真实账号和素材测试矩阵发布系统
"""
import requests
import json
import time

BASE_URL = "http://localhost:7000"

def get_accounts():
    """获取当前系统的账号列表"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/accounts/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            # 适配实际API返回格式: {'success': True, 'items': [...]}
            if isinstance(data, dict):
                accounts = data.get('items', data.get('data', []))
            else:
                accounts = data
            print(f"✓ 获取到 {len(accounts)} 个账号")
            return accounts
        else:
            print(f"✗ 获取账号失败: {response.status_code}")
            return []
    except Exception as e:
        print(f"✗ 获取账号异常: {e}")
        return []


def get_materials():
    """获取当前系统的素材列表"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/files/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            # 处理嵌套的data结构
            if isinstance(data, dict):
                materials = data.get('data', {}).get('data', [])
            else:
                materials = data
            # 只获取pending状态的素材
            pending_materials = [m for m in materials if m.get('status') == 'pending']
            print(f"✓ 获取到 {len(pending_materials)} 个待发布素材")
            return pending_materials
        else:
            print(f"✗ 获取素材失败: {response.status_code}")
            return []
    except Exception as e:
        print(f"✗ 获取素材异常: {e}")
        return []


def group_accounts_by_platform(accounts):
    """按平台分组账号"""
    platform_map = {
        'xiaohongshu': [],
        'douyin': [],
        'kuaishou': [],
        'channels': [],
        'bilibili': []
    }
    
    for account in accounts:
        platform = account.get('platform')
        # 适配实际API：status是'valid'而不是'正常'，使用account_id而不是id
        status = account.get('status')
        account_id = account.get('account_id') or account.get('id')
        
        if platform in platform_map and status == 'valid' and account_id:
            platform_map[platform].append(account_id)
    
    # 过滤掉空平台
    return {k: v for k, v in platform_map.items() if v}


def test_matrix_with_real_data():
    """使用真实数据测试矩阵发布"""
    print("=" * 70)
    print("矩阵发布系统 - 真实数据测试")
    print("=" * 70)
    print()
    
    # 1. 获取账号数据
    print("【Step 1】获取系统账号...")
    accounts = get_accounts()
    if not accounts:
        print("⚠ 系统中没有可用账号，无法测试")
        return
    
    # 按平台分组
    platform_accounts = group_accounts_by_platform(accounts)
    print(f"\n账号分布:")
    for platform, accs in platform_accounts.items():
        print(f"  {platform:12} : {len(accs)} 个账号")
    print()
    
    # 2. 获取素材数据
    print("【Step 2】获取系统素材...")
    materials = get_materials()
    if not materials:
        print("⚠ 系统中没有待发布素材，无法测试")
        return
    
    material_ids = [str(m['id']) for m in materials[:10]]  # 最多取10个素材
    print(f"\n素材列表 (前10个):")
    for i, m in enumerate(materials[:10], 1):
        print(f"  {i}. {m.get('filename', 'Unknown')} (ID: {m['id']})")
    print()
    
    # 3. 选择测试平台（有账号的平台）
    available_platforms = list(platform_accounts.keys())
    if not available_platforms:
        print("⚠ 没有状态正常的账号，无法测试")
        return
    
    print("【Step 3】生成矩阵任务...")
    test_platforms = available_platforms[:3]  # 最多选3个平台
    print(f"测试平台: {', '.join(test_platforms)}")
    
    # 4. 生成矩阵任务
    payload = {
        "platforms": test_platforms,
        "accounts": {p: platform_accounts[p][:3] for p in test_platforms},  # 每个平台最多3个账号
        "materials": material_ids[:5],  # 最多5个素材
        "title": "矩阵发布测试 - 真实数据",
        "description": "#测试 #矩阵发布 #自动化",
        "topics": ["测试", "自动化"]
    }
    
    print(f"\n任务配置:")
    print(f"  平台数: {len(test_platforms)}")
    print(f"  账号数: {sum(len(v) for v in payload['accounts'].values())}")
    print(f"  素材数: {len(material_ids[:5])}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/matrix/generate_tasks",
            json=payload,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            task_count = result['data']['count']
            batch_id = result['data']['batch_id']
            
            print(f"\n✓ 成功生成 {task_count} 个矩阵任务")
            print(f"  批次ID: {batch_id}")
            
            # 显示任务分配详情
            tasks = result['data']['tasks']
            print(f"\n任务分配详情:")
            for task in tasks:
                material_name = next((m['filename'] for m in materials if str(m['id']) == str(task['material_id'])), task['material_id'])
                account_obj = next((a for a in accounts if a.get('account_id') == task['account_id'] or a.get('id') == task['account_id']), None)
                account_name = account_obj.get('note') or account_obj.get('name') if account_obj else task['account_id']
                print(f"  {task['platform']:12} | {account_name[:20]:20} | {material_name[:30]}")
            
            # 5. 查看统计
            print(f"\n【Step 4】查看任务统计...")
            stats_response = requests.get(f"{BASE_URL}/api/v1/matrix/stats")
            if stats_response.status_code == 200:
                stats = stats_response.json()['data']
                print(f"  待执行: {stats['pending']}")
                print(f"  重试:   {stats['retry']}")
                print(f"  执行中: {stats['running']}")
                print(f"  已完成: {stats['finished']}")
                print(f"  失败:   {stats['failed']}")
            
            # 6. 演示获取任务
            print(f"\n【Step 5】演示任务调度...")
            next_task_response = requests.get(f"{BASE_URL}/api/v1/matrix/tasks/next")
            if next_task_response.status_code == 200:
                next_task = next_task_response.json().get('task')
                if next_task:
                    print(f"  下一个待执行任务:")
                    print(f"    平台: {next_task['platform']}")
                    print(f"    账号: {next_task['account_id']}")
                    print(f"    素材: {next_task['material_id']}")
            
            print(f"\n✅ 矩阵发布系统测试成功！")
            print(f"\n提示:")
            print(f"  - 任务已生成，可以启动执行器自动发布")
            print(f"  - 执行器启动命令: python -m syn_backend.matrix_executor")
            print(f"  - 或手动调用: POST {BASE_URL}/api/v1/matrix/tasks/pop")
            
            return True
            
        else:
            print(f"\n✗ 生成任务失败: {response.status_code}")
            print(f"  响应: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def cleanup_tasks():
    """清理测试任务"""
    print("\n清理测试任务...")
    try:
        response = requests.post(f"{BASE_URL}/api/v1/matrix/tasks/reset", timeout=10)
        if response.status_code == 200:
            print("✓ 任务池已清空")
        else:
            print(f"✗ 清理失败: {response.status_code}")
    except Exception as e:
        print(f"✗ 清理异常: {e}")


if __name__ == "__main__":
    try:
        # 先清理旧任务
        cleanup_tasks()
        print()
        
        # 运行测试
        success = test_matrix_with_real_data()
        
        print()
        print("=" * 70)
        if success:
            print("测试完成！任务已生成，可以开始发布。")
        else:
            print("测试失败，请检查日志。")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n测试被中断")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
