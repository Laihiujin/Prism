import sqlite3
from pathlib import Path

# 获取数据库路径
current_dir = Path(__file__).parent
DB_PATH = current_dir / "database.db"

def create_campaign_tables():
    """创建投放任务系统相关表"""
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # 1. Plan（投放计划）表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS plans (
            plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            platforms TEXT,  -- JSON数组，如 ["douyin", "kuaishou"]
            start_date TEXT,
            end_date TEXT,
            goal_type TEXT,  -- exposure/fans/conversion/other
            remark TEXT,
            status TEXT DEFAULT 'draft',  -- draft/running/finished/archived
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 2. TaskPackage（任务包/波次）表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS task_packages (
            package_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            platform TEXT NOT NULL,  -- douyin/kuaishou/redbook
            account_ids_scope TEXT,  -- JSON数组，账号ID列表
            material_ids_scope TEXT,  -- JSON数组，素材ID列表
            dispatch_mode TEXT DEFAULT 'random',  -- random/fixed/round_robin
            time_strategy TEXT,  -- JSON对象，时间策略配置
            generated_task_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'draft',  -- draft/scheduled/generated/locked
            created_by TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (plan_id) REFERENCES plans(plan_id)
        )
        ''')
        
        # 3. PublishTask（单条投放任务）表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS publish_tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER,
            package_id INTEGER,
            platform TEXT NOT NULL,
            account_id TEXT,  -- 内部账号或外部账号ID
            material_id TEXT,  -- 素材ID
            title TEXT,
            tags TEXT,  -- JSON数组
            cover TEXT,
            schedule_time DATETIME,
            publish_mode TEXT DEFAULT 'auto',  -- auto/manual_confirm/external_manual
            status TEXT DEFAULT 'pending',  -- pending/publishing/success/failed/cancelled
            external_user_id TEXT,
            external_account_id TEXT,
            result_metrics TEXT,  -- JSON对象，播放/点赞/评论等
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            published_at DATETIME,
            completed_at DATETIME,
            FOREIGN KEY (plan_id) REFERENCES plans(plan_id),
            FOREIGN KEY (package_id) REFERENCES task_packages(package_id)
        )
        ''')
        
        # 4. ExternalUser（外部协作用户）表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS external_users (
            external_user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            login_method TEXT,  -- phone/wechat/email
            phone TEXT,
            wechat_openid TEXT,
            email TEXT,
            nickname TEXT,
            avatar TEXT,
            status TEXT DEFAULT 'active',  -- active/disabled
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 5. ExternalAccount（外部协作账号）表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS external_accounts (
            ext_account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            external_user_id INTEGER NOT NULL,
            platform TEXT NOT NULL,  -- douyin/kuaishou等
            platform_uid TEXT,  -- 平台内唯一ID
            display_name TEXT,
            status TEXT DEFAULT 'active',  -- active/revoked
            access_token TEXT,  -- 加密存储
            refresh_token TEXT,
            expire_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (external_user_id) REFERENCES external_users(external_user_id)
        )
        ''')
        
        conn.commit()
        print(f"✅ 投放任务系统表创建成功 at {DB_PATH}")
        print("   - plans (投放计划)")
        print("   - task_packages (任务包)")
        print("   - publish_tasks (发布任务)")
        print("   - external_users (外部用户)")
        print("   - external_accounts (外部账号)")

if __name__ == "__main__":
    create_campaign_tables()
