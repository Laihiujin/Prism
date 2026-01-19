"""
矩阵发布系统测试脚本
测试完整的任务生成、调度和执行流程
"""
import requests
import time
from typing import List, Dict

# API Base URL
BASE_URL = "http://localhost:8860/api/v1/matrix"


def test_generate_tasks():
    """测试生成矩阵任务"""
    print("=" * 60)
    print("测试1: 生成矩阵任务")
    print("=" * 60)
    
    payload = {
        "platforms": ["douyin", "kuaishou", "xiaohongshu"],
        "accounts": {
            "douyin": ["dy_account_1", "dy_account_2", "dy_account_3"],
            "kuaishou": ["ks_account_1", "ks_account_2"],
            "xiaohongshu": ["xhs_account_1", "xhs_account_2", "xhs_account_3"]
        },
        "materials": ["101", "102", "103"],
        "title": "测试标题",
        "description": "#测试 #矩阵发布",
        "topics": ["测试", "自动化"]
    }
    
    response = requests.post(f"{BASE_URL}/generate_tasks", json=payload)
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ 成功生成 {data['data']['count']} 个任务")
        print(f"  批次ID: {data['data']['batch_id']}")
        
        # 显示任务分配
        tasks = data['data']['tasks']
        print("\n任务分配明细:")
        for task in tasks:
            print(f"  {task['platform']:12} | {task['account_id']:15} | 素材 {task['material_id']}")
        
        return data['data']['batch_id']
    else:
        print(f"✗ 生成失败: {response.text}")
        return None


def test_get_statistics():
    """测试获取统计信息"""
    print("\n" + "=" * 60)
    print("测试2: 获取统计信息")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/stats")
    
    if response.status_code == 200:
        stats = response.json()['data']
        print("当前任务统计:")
        print(f"  待执行 (pending): {stats['pending']}")
        print(f"  重试中 (retry):   {stats['retry']}")
        print(f"  执行中 (running): {stats['running']}")
        print(f"  已完成 (finished): {stats['finished']}")
        print(f"  失败   (failed):   {stats['failed']}")
        print(f"  总计:              {stats['total']}")
        return stats
    else:
        print(f"✗ 获取失败: {response.text}")
        return None


def test_pop_task():
    """测试弹出任务"""
    print("\n" + "=" * 60)
    print("测试3: 弹出下一个任务")
    print("=" * 60)
    
    response = requests.post(f"{BASE_URL}/tasks/pop")
    
    if response.status_code == 200:
        data = response.json()
        task = data.get('task')
        
        if task:
            print("✓ 成功弹出任务:")
            print(f"  任务ID:   {task['task_id']}")
            print(f"  平台:     {task['platform']}")
            print(f"  账号:     {task['account_id']}")
            print(f"  素材:     {task['material_id']}")
            print(f"  状态:     {task['status']}")
            return task
        else:
            print("□ 没有待执行任务")
            return None
    else:
        print(f"✗ 弹出失败: {response.text}")
        return None


def test_report_result(task_id: str, status: str = "success"):
    """测试上报任务结果"""
    print("\n" + "=" * 60)
    print(f"测试4: 上报任务结果 ({status})")
    print("=" * 60)
    
    payload = {
        "task_id": task_id,
        "status": status,
        "message": f"模拟{status}"
    }
    
    response = requests.post(f"{BASE_URL}/tasks/report", json=payload)
    
    if response.status_code == 200:
        print(f"✓ 成功上报: {status}")
        return True
    else:
        print(f"✗ 上报失败: {response.text}")
        return False


def test_list_tasks():
    """测试列出所有任务"""
    print("\n" + "=" * 60)
    print("测试5: 列出所有任务")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/tasks/list")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ 任务总数: {data['total']}")
        print(f"  待执行: {len(data['pending'])} 个")
        print(f"  重试:   {len(data['retry'])} 个")
        print(f"  执行中: {len(data['running'])} 个")
        print(f"  已完成: {len(data['finished'])} 个")
        print(f"  失败:   {len(data['failed'])} 个")
        return data
    else:
        print(f"✗ 获取失败: {response.text}")
        return None


def test_execute_all_tasks():
    """测试执行所有任务"""
    print("\n" + "=" * 60)
    print("测试6: 模拟执行所有任务")
    print("=" * 60)
    
    completed = 0
    while True:
        # 弹出任务
        task = test_pop_task()
        
        if not task:
            break
        
        # 模拟执行
        print(f"\n  → 模拟执行任务...")
        time.sleep(1)
        
        # 随机成功/失败/重试
        import random
        status_choice = random.choices(
            ["success", "fail", "need_verification"],
            weights=[0.7, 0.2, 0.1]
        )[0]
        
        # 上报结果
        test_report_result(task['task_id'], status_choice)
        completed += 1
        
        print("\n" + "-" * 60)
    
    print(f"\n总计处理 {completed} 个任务")


def test_reset():
    """测试重置任务池"""
    print("\n" + "=" * 60)
    print("测试7: 重置任务池")
    print("=" * 60)
    
    response = requests.post(f"{BASE_URL}/tasks/reset")
    
    if response.status_code == 200:
        print("✓ 任务池已重置")
        return True
    else:
        print(f"✗ 重置失败: {response.text}")
        return False


def main():
    """主测试流程"""
    print("\n" + "=" * 60)
    print("矩阵发布系统 - 完整测试")
    print("=" * 60)
    
    try:
        # 1. 重置任务池
        test_reset()
        
        # 2. 生成任务
        batch_id = test_generate_tasks()
        
        if not batch_id:
            print("\n✗ 测试失败：无法生成任务")
            return
        
        # 3. 查看统计
        test_get_statistics()
        
        # 4. 列出任务
        test_list_tasks()
        
        # 5. 执行所有任务
        test_execute_all_tasks()
        
        # 6. 最终统计
        test_get_statistics()
        test_list_tasks()
        
        print("\n" + "=" * 60)
        print("✓ 所有测试完成")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n测试被中断")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
