"""
诊断任务管理系统
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "syn_backend"))

import sqlite3
from datetime import datetime

print("=" * 80)
print("任务管理系统诊断报告")
print("=" * 80)
print()

# 1. 检查数据库文件
print("[1] 检查数据库文件")
print("-" * 80)
project_root = Path(__file__).parent.parent.parent
db_files = {
    "task_queue.db": project_root / "syn_backend/db/task_queue.db",
    "database.db": project_root / "syn_backend/db/database.db",
}

for name, path in db_files.items():
    if path.exists():
        size = path.stat().st_size
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        print(f"  [OK] {name:20} {size:>12,} bytes  (最后修改: {mtime})")
    else:
        print(f"  [NG] {name:20} 不存在")

print()

# 2. 检查 task_queue.db
print("[2] 检查 task_queue.db 任务记录")
print("-" * 80)
try:
    conn = sqlite3.connect("syn_backend/db/task_queue.db")

    # 任务队列
    count = conn.execute("SELECT COUNT(*) FROM task_queue").fetchone()[0]
    print(f"  task_queue 表:          {count} 条记录")

    if count > 0:
        # 按状态统计
        stats = conn.execute("""
            SELECT status, COUNT(*) as cnt
            FROM task_queue
            GROUP BY status
        """).fetchall()
        for status, cnt in stats:
            print(f"    - {status:10} {cnt:3} 条")

    # 人工任务
    manual_count = conn.execute("SELECT COUNT(*) FROM manual_tasks").fetchone()[0]
    print(f"  manual_tasks 表:        {manual_count} 条记录")

    if manual_count > 0:
        manual_stats = conn.execute("""
            SELECT status, COUNT(*) as cnt
            FROM manual_tasks
            GROUP BY status
        """).fetchall()
        for status, cnt in manual_stats:
            print(f"    - {status:10} {cnt:3} 条")

    conn.close()
except Exception as e:
    print(f"  [ERROR] {e}")

print()

# 3. 检查 database.db
print("[3] 检查 database.db 状态表")
print("-" * 80)
try:
    conn = sqlite3.connect("syn_backend/db/database.db")

    # Celery 任务状态
    count = conn.execute("SELECT COUNT(*) FROM celery_task_states").fetchone()[0]
    print(f"  celery_task_states 表:  {count} 条记录")

    # 发布任务
    try:
        pub_count = conn.execute("SELECT COUNT(*) FROM publish_tasks").fetchone()[0]
        print(f"  publish_tasks 表:       {pub_count} 条记录")
    except:
        print(f"  publish_tasks 表:       不存在")

    conn.close()
except Exception as e:
    print(f"  [ERROR] {e}")

print()

# 4. 测试后端API
print("[4] 测试后端 API 接口")
print("-" * 80)
try:
    import httpx

    backend_url = "http://localhost:7000"

    # 测试任务列表接口
    try:
        response = httpx.get(f"{backend_url}/api/v1/tasks/", timeout=5.0)
        print(f"  GET /api/v1/tasks/      状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            task_count = len(data.get("data", []))
            print(f"    - 返回任务数: {task_count}")
        elif response.status_code == 503:
            print(f"    - 错误: 任务队列服务未启用")
    except httpx.ConnectError:
        print(f"  ✗ 无法连接到后端服务 (是否未启动?)")
    except Exception as e:
        print(f"  ✗ 错误: {e}")

except ImportError:
    print(f"  ⚠ 未安装 httpx，跳过 API 测试")

print()
print("=" * 80)
print("诊断完成")
print("=" * 80)
