import sqlite3
import os

DB_PATH = 'e:/SynapseAutomation/syn_backend/db/database.db'

def update_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check publish_tasks
    cursor.execute('PRAGMA table_info(publish_tasks)')
    cols = [row[1] for row in cursor.fetchall()]
    if 'video_id' not in cols:
        cursor.execute('ALTER TABLE publish_tasks ADD COLUMN video_id TEXT')
        print("Added video_id to publish_tasks")
    if 'completed_at' not in cols:
        cursor.execute('ALTER TABLE publish_tasks ADD COLUMN completed_at DATETIME')
        print("Added completed_at to publish_tasks")
    if 'completed_at' not in cols:
        cursor.execute('ALTER TABLE publish_tasks ADD COLUMN completed_at DATETIME')
        print("Added completed_at to publish_tasks")
    
    # Check status column in video_analytics (already ensured in VideoDataCollector.init_database but good to be sure)
    cursor.execute('PRAGMA table_info(video_analytics)')
    v_cols = [row[1] for row in cursor.fetchall()]
    if 'task_id' not in v_cols:
        cursor.execute('ALTER TABLE video_analytics ADD COLUMN task_id TEXT')
        print("Added task_id to video_analytics")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_schema()
