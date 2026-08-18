import sqlite3
import time
from datetime import datetime
from pathlib import Path
import json

class TaskScheduler:
    """发布任务调度器 - 自动执行待发布任务"""
    
    def __init__(self, db_path='db/database.db'):
        self.db_path = db_path
        self.running = False
    
    def start(self):
        """启动调度器"""
        self.running = True
        print("📅 任务调度器已启动...")
        
        while self.running:
            try:
                self.check_and_execute_tasks()
                time.sleep(30)  # 每30秒检查一次
            except Exception as e:
                print(f"❌ 调度器错误: {e}")
                time.sleep(60)
    
    def stop(self):
        """停止调度器"""
        self.running = False
        print("🛑 任务调度器已停止")
    
    def check_and_execute_tasks(self):
        """检查并执行待发布的任务"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 查找待执行的任务
                # 条件: status = 'pending' 且 schedule_time <= now 且 publish_mode = 'auto'
                cursor.execute("""
                    SELECT * FROM publish_tasks 
                    WHERE status = 'pending' 
                    AND publish_mode = 'auto'
                    AND (schedule_time IS NULL OR schedule_time <= datetime('now', 'localtime'))
                    LIMIT 10
                """)
                
                tasks = cursor.fetchall()
                
                if tasks:
                    print(f"⏰ 发现 {len(tasks)} 个待执行任务")
                    
                    for task in tasks:
                        self.execute_task(dict(task))
                
        except Exception as e:
            print(f"检查任务时出错: {e}")
    
    def execute_task(self, task):
        """执行单个发布任务"""
        task_id = task['task_id']
        
        try:
            print(f"🚀 开始执行任务 #{task_id}: {task['platform']} - {task['account_id']}")
            
            # 更新状态为 publishing
            self.update_task_status(task_id, 'publishing')
            
            # TODO: 调用实际的发布函数
            # 根据平台调用不同的发布接口
            success = self.publish_to_platform(task)
            
            if success:
                # 发布成功
                self.update_task_status(
                    task_id, 
                    'success',
                    published_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
                print(f"✅ 任务 #{task_id} 发布成功")
            else:
                # 发布失败
                self.update_task_status(
                    task_id, 
                    'failed',
                    error_message="发布接口返回失败"
                )
                print(f"❌ 任务 #{task_id} 发布失败")
                
        except Exception as e:
            # 异常处理
            self.update_task_status(
                task_id,
                'failed',
                error_message=str(e)
            )
            print(f"❌ 任务 #{task_id} 执行异常: {e}")
    
    def publish_to_platform(self, task):
        """
        调用平台发布接口
        
        这里需要集成实际的发布函数:
        - post_video_DouYin (抖音)
        - post_video_ks (快手)
        - post_video_xhs (小红书)
        - post_video_bilibili (B站)
        - post_video_tencent (视频号)
        """
        platform = task['platform']
        material_id = task['material_id']
        account_id = task['account_id']
        title = task['title']
        
        # TODO: 实际调用发布函数
        # 示例:
        # if platform == 'douyin':
        #     from myUtils.postVideo import post_video_DouYin
        #     result = post_video_DouYin(cookie, video_path, title, tags)
        #     return result['success']
        
        # 当前仅模拟
        print(f"  📤 模拟发布: {platform} | 账号: {account_id} | 素材: {material_id}")
        return True  # 模拟成功
    
    def update_task_status(self, task_id, status, **kwargs):
        """更新任务状态"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 构建更新SQL
                fields = ["status = ?"]
                values = [status]
                
                if 'error_message' in kwargs:
                    fields.append("error_message = ?")
                    values.append(kwargs['error_message'])
                
                if 'published_at' in kwargs:
                    fields.append("published_at = ?")
                    values.append(kwargs['published_at'])
                
                fields.append("updated_at = CURRENT_TIMESTAMP")
                values.append(task_id)
                
                sql = f"UPDATE publish_tasks SET {', '.join(fields)} WHERE task_id = ?"
                cursor.execute(sql, values)
                conn.commit()
                
        except Exception as e:
            print(f"更新任务状态失败: {e}")
    
    def get_task_statistics(self):
        """获取任务统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        status,
                        COUNT(*) as count
                    FROM publish_tasks
                    GROUP BY status
                """)
                
                stats = {}
                for row in cursor.fetchall():
                    stats[row[0]] = row[1]
                
                return stats
        except Exception as e:
            print(f"获取统计信息失败: {e}")
            return {}

# 全局实例
task_scheduler = TaskScheduler()

if __name__ == "__main__":
    # 测试运行
    scheduler = TaskScheduler()
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.stop()
        print("\n程序已退出")
