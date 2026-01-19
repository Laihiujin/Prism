"""
前后端路由问题完整修复方案

问题诊断：
1. 前端调用 /api/plans，后端只有 /api/v1/campaigns 和 /api/campaigns
2. 前端调用 /api/v1/ai/model-configs，后端路由存在但不可访问
3. 仪表盘和素材库数据未同步

解决方案：
1. 添加路由别名
2. 确保所有路由正确注册
3. 重启后端服务
"""

import requests
import json

BASE_URL = "http://localhost:7000"

# 测试所有关键路由
tests = {
    "仪表盘": ("GET", f"{BASE_URL}/api/dashboard"),
    "素材列表": ("GET", f"{BASE_URL}/api/materials"),
    "AI模型配置": ("GET", f"{BASE_URL}/api/v1/ai/model-configs"),
    "计划列表": ("GET", f"{BASE_URL}/api/plans"),
    "创建计划": ("POST", f"{BASE_URL}/api/plans", {
        "name": "测试计划",
        "platform": "douyin",
        "goal_type": "other"
    }),
    "派发任务": ("GET", f"{BASE_URL}/api/tasks/distribution"),
}

print("=" * 80)
print("路由测试报告")
print("=" * 80)

results = {}
for name, (method, url, *data) in tests.items():
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        else:
            response = requests.post(url, json=data[0] if data else None, timeout=5)
        
        success = response.status_code in [200, 201]
        results[name] = {
            "status": response.status_code,
            "success": success,
            "error": None if success else response.text[:200]
        }
        
        status_icon = "✅" if success else "❌"
        print(f"\n{status_icon} {name}")
        print(f"   URL: {url}")
        print(f"   状态码: {response.status_code}")
        if not success:
            print(f"   错误: {response.text[:200]}")
            
    except Exception as e:
        results[name] = {"status": "ERROR", "success": False, "error": str(e)}
        print(f"\n❌ {name}")
        print(f"   错误: {e}")

print("\n" + "=" * 80)
print("总结")
print("=" * 80)

failed = [name for name, result in results.items() if not result["success"]]
if failed:
    print(f"\n失败的路由 ({len(failed)}):")
    for name in failed:
        print(f"  - {name}")
    print("\n需要修复的问题:")
    print("  1. 确保后端已重启")
    print("  2. 检查路由别名是否正确添加")
    print("  3. 验证数据库连接")
else:
    print("\n✅ 所有路由测试通过！")

# 保存结果
with open("route_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("\n详细结果已保存到: route_test_results.json")
