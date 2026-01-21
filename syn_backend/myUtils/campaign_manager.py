import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
import random

from config.conf import BASE_DIR


class CampaignManager:
    """投放任务系统管理器"""

    def __init__(self, db_path=None):
        # 默认使用 BASE_DIR 下的 database.db，避免相对路径导致找不到表
        self.db_path = db_path or Path(BASE_DIR) / "db" / "database.db"
    
    # ========== Plan 管理 ==========
    
    def create_plan(self, data):
        """创建投放计划"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO plans (name, platforms, start_date, end_date, goal_type, remark, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('name'),
                    json.dumps(data.get('platforms', [])),
                    data.get('start_date'),
                    data.get('end_date'),
                    data.get('goal_type', 'other'),
                    data.get('remark', ''),
                    data.get('created_by', 'system')
                ))
                
                plan_id = cursor.lastrowid
                conn.commit()
                return {"success": True, "plan_id": plan_id}
        except Exception as e:
            print(f"Error creating plan: {e}")
            return {"success": False, "error": str(e)}
    
    def get_all_plans(self):
        """获取所有投放计划"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM plans ORDER BY created_at DESC")
                rows = cursor.fetchall()
                
                plans = []
                for row in rows:
                    plan = dict(row)
                    try:
                        plan['platforms'] = json.loads(plan['platforms'])
                    except:
                        plan['platforms'] = []
                    plans.append(plan)
                
                return plans
        except Exception as e:
            print(f"Error getting plans: {e}")
            return []
    
    def get_plan(self, plan_id):
        """获取单个计划"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,))
                row = cursor.fetchone()
                
                if row:
                    plan = dict(row)
                    try:
                        plan['platforms'] = json.loads(plan['platforms'])
                    except:
                        plan['platforms'] = []
                    return plan
                return None
        except Exception as e:
            print(f"Error getting plan: {e}")
            return None
    
    def update_plan(self, plan_id, data):
        """更新计划"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                fields = []
                values = []
                
                if 'name' in data:
                    fields.append("name = ?")
                    values.append(data['name'])
                if 'platforms' in data:
                    fields.append("platforms = ?")
                    values.append(json.dumps(data['platforms']))
                if 'start_date' in data:
                    fields.append("start_date = ?")
                    values.append(data['start_date'])
                if 'end_date' in data:
                    fields.append("end_date = ?")
                    values.append(data['end_date'])
                if 'status' in data:
                    fields.append("status = ?")
                    values.append(data['status'])
                if 'remark' in data:
                    fields.append("remark = ?")
                    values.append(data['remark'])
                
                fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(plan_id)
                
                sql = f"UPDATE plans SET {', '.join(fields)} WHERE plan_id = ?"
                cursor.execute(sql, values)
                conn.commit()
                
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ========== TaskPackage 管理 ==========
    
    def create_task_package(self, data):
        """创建任务包"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO task_packages 
                    (plan_id, name, platform, account_ids_scope, material_ids_scope, 
                     dispatch_mode, time_strategy, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get('plan_id'),
                    data.get('name'),
                    data.get('platform'),
                    json.dumps(data.get('account_ids', [])),
                    json.dumps(data.get('material_ids', [])),
                    data.get('dispatch_mode', 'random'),
                    json.dumps(data.get('time_strategy', {})),
                    data.get('created_by', 'system')
                ))
                
                package_id = cursor.lastrowid
                conn.commit()
                return {"success": True, "package_id": package_id}
        except Exception as e:
            print(f"Error creating task package: {e}")
            return {"success": False, "error": str(e)}
    
    def get_packages_by_plan(self, plan_id):
        """获取计划下的所有任务包"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM task_packages 
                    WHERE plan_id = ? 
                    ORDER BY created_at DESC
                """, (plan_id,))
                rows = cursor.fetchall()
                
                packages = []
                for row in rows:
                    pkg = dict(row)
                    try:
                        pkg['account_ids_scope'] = json.loads(pkg['account_ids_scope'])
                    except:
                        pkg['account_ids_scope'] = []
                    try:
                        pkg['material_ids_scope'] = json.loads(pkg['material_ids_scope'])
                    except:
                        pkg['material_ids_scope'] = []
                    try:
                        pkg['time_strategy'] = json.loads(pkg['time_strategy'])
                    except:
                        pkg['time_strategy'] = {}
                    packages.append(pkg)
                
                return packages
        except Exception as e:
            print(f"Error getting packages: {e}")
            return []
    
    # ========== PublishTask 生成 ==========
    
    def generate_tasks_from_package(self, package_id):
        """从任务包生成发布任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 获取任务包信息
                cursor.execute("SELECT * FROM task_packages WHERE package_id = ?", (package_id,))
                package = dict(cursor.fetchone())
                
                # 解析JSON
                account_ids = json.loads(package['account_ids_scope'])
                material_ids = json.loads(package['material_ids_scope'])
                time_strategy = json.loads(package['time_strategy'])
                
                # 生成任务
                tasks = self._generate_tasks(
                    package['plan_id'],
                    package_id,
                    package['platform'],
                    account_ids,
                    material_ids,
                    package['dispatch_mode'],
                    time_strategy
                )
                
                # 插入任务
                for task in tasks:
                    cursor.execute("""
                        INSERT INTO publish_tasks 
                        (plan_id, package_id, platform, account_id, material_id, 
                         title, schedule_time, publish_mode, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        task['plan_id'],
                        task['package_id'],
                        task['platform'],
                        task['account_id'],
                        task['material_id'],
                        task.get('title', ''),
                        task.get('schedule_time'),
                        task.get('publish_mode', 'auto'),
                        'pending'
                    ))
                
                # 更新任务包状态
                cursor.execute("""
                    UPDATE task_packages 
                    SET generated_task_count = ?, status = 'generated'
                    WHERE package_id = ?
                """, (len(tasks), package_id))
                
                conn.commit()
                return {"success": True, "task_count": len(tasks), "tasks": tasks}
                
        except Exception as e:
            print(f"Error generating tasks: {e}")
            return {"success": False, "error": str(e)}
    
    def publish_plan(self, plan_id):
        """发布计划：将状态设为running，并生成所有草稿任务包的任务"""
        try:
            # 1. 更新计划状态
            self.update_plan(plan_id, {'status': 'running'})
            
            # 2. 获取所有任务包
            packages = self.get_packages_by_plan(plan_id)
            
            generated_count = 0
            for pkg in packages:
                if pkg['status'] == 'draft':
                    res = self.generate_tasks_from_package(pkg['package_id'])
                    if res['success']:
                        generated_count += res['task_count']
            
            return {"success": True, "generated_tasks": generated_count}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _generate_tasks(self, plan_id, package_id, platform, account_ids, material_ids, dispatch_mode, time_strategy):
        """生成任务列表（核心逻辑）"""
        tasks = []
        
        mode = time_strategy.get('mode', 'once')
        
        # 解析时间点列表，支持单个 time_point 或 time_points 列表
        time_points = time_strategy.get('time_points', [])
        if not time_points and 'time_point' in time_strategy:
            time_points = [time_strategy['time_point']]
        if not time_points:
            time_points = ['10:00'] # 默认时间
            
        if mode == 'once':
            # 单日集中发布
            date = time_strategy.get('date', datetime.now().strftime('%Y-%m-%d'))
            
            # 扩展账号列表以匹配时间点数量（如果需要）
            # 这里简化逻辑：每个账号在每个时间点都可能发布，或者根据分配模式
            
            task_candidates = []
            for time_point in time_points:
                for account_id in account_ids:
                    task_candidates.append({
                        'account_id': account_id,
                        'schedule_time': f"{date} {time_point}"
                    })
            
            # 根据分配模式分配素材
            if dispatch_mode == 'random':
                for candidate in task_candidates:
                    material_id = random.choice(material_ids) if material_ids else None
                    tasks.append({
                        'plan_id': plan_id,
                        'package_id': package_id,
                        'platform': platform,
                        'account_id': candidate['account_id'],
                        'material_id': material_id,
                        'schedule_time': candidate['schedule_time'],
                        'publish_mode': 'auto'
                    })
            elif dispatch_mode == 'fixed':
                for i, candidate in enumerate(task_candidates):
                    material_id = material_ids[i % len(material_ids)] if material_ids else None
                    tasks.append({
                        'plan_id': plan_id,
                        'package_id': package_id,
                        'platform': platform,
                        'account_id': candidate['account_id'],
                        'material_id': material_id,
                        'schedule_time': candidate['schedule_time'],
                        'publish_mode': 'auto'
                    })
        
        elif mode == 'date_range':
            # 日期范围发布
            start_date = datetime.strptime(time_strategy.get('start_date'), '%Y-%m-%d')
            end_date = datetime.strptime(time_strategy.get('end_date'), '%Y-%m-%d')
            per_day = time_strategy.get('per_account_per_day', 1)
            
            current_date = start_date
            material_index = 0
            
            while current_date <= end_date:
                for account_id in account_ids:
                    # 每天生成 per_day 个任务
                    for i in range(per_day):
                        # 循环使用时间点
                        time_point = time_points[i % len(time_points)]
                        
                        if material_index < len(material_ids):
                            tasks.append({
                                'plan_id': plan_id,
                                'package_id': package_id,
                                'platform': platform,
                                'account_id': account_id,
                                'material_id': material_ids[material_index],
                                'schedule_time': f"{current_date.strftime('%Y-%m-%d')} {time_point}",
                                'publish_mode': 'auto'
                            })
                            material_index += 1
                current_date += timedelta(days=1)
        
        return tasks
    
    # ========== PublishTask 查询 ==========
    
    def get_tasks_by_package(self, package_id):
        """获取任务包下的所有任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM publish_tasks 
                    WHERE package_id = ? 
                    ORDER BY schedule_time
                """, (package_id,))
                rows = cursor.fetchall()
                
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error getting tasks: {e}")
            return []
    
    def get_all_tasks(self, filters=None):
        """获取所有任务（支持筛选）"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = "SELECT * FROM publish_tasks WHERE 1=1"
                params = []
                
                if filters:
                    if 'plan_id' in filters:
                        query += " AND plan_id = ?"
                        params.append(filters['plan_id'])
                    if 'status' in filters:
                        query += " AND status = ?"
                        params.append(filters['status'])
                    if 'platform' in filters:
                        query += " AND platform = ?"
                        params.append(filters['platform'])
                
                query += " ORDER BY created_at DESC LIMIT 200"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                return [dict(row) for row in rows]
        except Exception as e:
            print(f"Error getting tasks: {e}")
            return []

campaign_manager = CampaignManager()
