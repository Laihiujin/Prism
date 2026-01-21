"""
矩阵发布系统 - 灵活测试版本
即使没有真实素材也能演示功能
"""
import requests
import json

BASE_URL = "http://localhost:7000"

def test_matrix_demo():
    """演示矩阵发布系统（使用模拟素材ID）"""
    print("=" * 70)
    print("矩阵发布系统 - 功能演示")
    print("=" * 70)
    print()
    
    # 1. 获取账号
    print("【Step 1】获取系统账号...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/accounts/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            accounts = data.get('items', data.get('data', []))
            print(f"✓ 获取到 {len(accounts)} 个账号")
            
            # 按平台分组
            platform_accounts = {}
            for acc in accounts:
                platform = acc.get('platform')
                if platform and acc.get('status') == 'valid':
                    if platform not in platform_accounts:
                        platform_accounts[platform] = []
                    platform_accounts[platform].append(acc.get('account_id') or acc.get('id'))
            
            print(f"\n账号分布:")
            for platform, accs in platform_accounts.items():
                print(f"  {platform:12} : {len(accs)} 个账号")
            
            if not platform_accounts:
                print("\n⚠ 没有可用账号")
                return False
            
        else:
            print(f"✗ 获取账号失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ 获取账号异常: {e}")
        return False
    
    # 2. 获取或模拟素材
    print(f"\n【Step 2】获取系统素材...")
    try:
        response = requests.get(f"{BASE_URL}/api/v1/files/", timeout=10)
        material_ids = []
        
        if response.status_code == 200:
            data = response.json()
            materials = data.get('data', {}).get('data', [])
            # 只获取pending状态的素材
            pending_materials = [m for m in materials if m.get('status') == 'pending']
            
            if pending_materials:
                material_ids = [str(m['id']) for m in pending_materials[:5]]
                print(f"✓ 获取到 {len(pending_materials)} 个待发布素材，使用前{len(material_ids)}个")
                for i, m in enumerate(pending_materials[:5], 1):
                    print(f"  {i}. {m.get('filename', 'Unknown')} (ID: {m['id']})")
            else:
                print(f"⚠ 没有待发布素材，使用模拟ID演示")
                # 使用模拟素材ID
                material_ids = ["demo_video_1", "demo_video_2", "demo_video_3"]
                print(f"  模拟素材: {', '.join(material_ids)}")
    except Exception as e:
        print(f"⚠ 获取素材异常，使用模拟ID: {e}")
        material_ids = ["demo_video_1", "demo_video_2", "demo_video_3"]
    
    # 3. 生成矩阵任务
    print(f"\n【Step 3】生成矩阵任务...")
    
    # 选择测试平台（最多3个）
    test_platforms = list(platform_accounts.keys())[:3]
    print(f"测试平台: {', '.join(test_platforms)}")
    
    # 构建payload
    payload = {
        "platforms": test_platforms,
        "accounts": {p: platform_accounts[p][:3] for p in test_platforms},
        "materials": material_ids,
        "title": "矩阵发布演示",
        "description": "#自动化 #矩阵发布 #测试",
        "topics": ["自动化", "测试"]
    }
    
    print(f"\n任务配置:")
    print(f"  平台数: {len(test_platforms)}")
    print(f"  账号数: {sum(len(v) for v in payload['accounts'].values())}")
    print(f"  素材数: {len(material_ids)}")
    print(f"\n发送请求到: {BASE_URL}/api/v1/matrix/generate_tasks")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/matrix/generate_tasks",
            json=payload,
            timeout=15
        )
        
        print(f"响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✓ API响应成功")
            print(f"响应数据: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}...")
            
            if result.get('success'):
                task_count = result['data']['count']
                batch_id = result['data']['batch_id']
                
                print(f"\n✅ 成功生成 {task_count} 个矩阵任务")
                print(f"   批次ID: {batch_id}")
                
                # 显示任务分配
                tasks = result['data']['tasks']
                print(f"\n📋 任务分配详情:")
                print("-" * 70)
                for i, task in enumerate(tasks, 1):
                    print(f"{i:2}. {task['platform']:12} | {task['account_id'][:25]:25} | 素材 {task['material_id']}")
                print("-" * 70)
                
                # 查看统计
                print(f"\n【Step 4】查看任务统计...")
                stats_resp = requests.get(f"{BASE_URL}/api/v1/matrix/stats")
                if stats_resp.status_code == 200:
                    stats = stats_resp.json()['data']
                    print(f"  📊 任务状态分布:")
                    print(f"     待执行: {stats['pending']}")
                    print(f"     重试中: {stats['retry']}")
                    print(f"     执行中: {stats['running']}")
                    print(f"     已完成: {stats['finished']}")
                    print(f"     失败:   {stats['failed']}")
                
                # 演示任务调度
                print(f"\n【Step 5】演示任务调度...")
                next_resp = requests.get(f"{BASE_URL}/api/v1/matrix/tasks/next")
                if next_resp.status_code == 200:
                    next_task = next_resp.json().get('task')
                    if next_task:
                        print(f"  🎯 下一个待执行任务:")
                        print(f"     任务ID: {next_task['task_id']}")
                        print(f"     平台:   {next_task['platform']}")
                        print(f"     账号:   {next_task['account_id'][:30]}")
                        print(f"     素材:   {next_task['material_id']}")
                        print(f"     状态:   {next_task['status']}")
                
                print(f"\n" + "=" * 70)
                print("✅ 矩阵发布系统测试成功！")
                print("=" * 70)
                print(f"\n💡 后续操作:")
                print(f"   1. 启动执行器: python -m syn_backend.matrix_executor")
                print(f"   2. 手动弹出任务: POST {BASE_URL}/api/v1/matrix/tasks/pop")
                print(f"   3. 查看任务列表: GET  {BASE_URL}/api/v1/matrix/tasks/list")
                
                return True
            else:
                print(f"\n✗ API返回失败")
                print(f"   响应: {result}")
                return False
        else:
            print(f"\n✗ 生成任务失败")
            print(f"   状态码: {response.status_code}")
            print(f"   响应: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        # 清理旧任务
        print("清理测试任务...")
        try:
            r = requests.post(f"{BASE_URL}/api/v1/matrix/tasks/reset", timeout=10)
            if r.status_code == 200:
                print("✓ 任务池已清空\n")
        except:
            print("⚠ 清理失败（可能matrix路由未加载）\n")
        
        # 运行测试
        success = test_matrix_demo()
        
        if not success:
            print("\n" + "=" * 70)
            print("❌ 测试失败")
            print("=" * 70)
            print("\n可能的原因:")
            print("  1. 后端未启动或端口不正确")
            print("  2. matrix路由未注册（需要重启后端）")
            print("  3. 网络连接问题")
        
    except KeyboardInterrupt:
        print("\n\n测试被中断")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()
