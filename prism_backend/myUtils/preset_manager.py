import sqlite3
import json
import warnings
from pathlib import Path
from datetime import datetime

from sqlalchemy import text

from fastapi_app.db.runtime import mysql_enabled, sa_connection
from fastapi_app.cache.redis_client import get_redis

# 数据库路径配置
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "db" / "database.db"

class PresetManager:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH

    def _ensure_sqlite_preset_schema(self, conn) -> None:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(publish_presets)")
        columns = {row[1] for row in cursor.fetchall()}
        altered = False

        if "tags" not in columns:
            cursor.execute("ALTER TABLE publish_presets ADD COLUMN tags TEXT")
            altered = True
        if "usage_count" not in columns:
            cursor.execute("ALTER TABLE publish_presets ADD COLUMN usage_count INTEGER DEFAULT 0")
            altered = True

        if altered:
            conn.commit()

    def create_preset(self, data):
        """创建发布预设 (计划)"""
        try:
            if mysql_enabled():
                with sa_connection() as conn:
                    label = data.get('name') or data.get('label', '未命名计划')
                    platform = json.dumps(data.get('platforms', []), ensure_ascii=False)
                    accounts = json.dumps(data.get('accounts', []), ensure_ascii=False)
                    material_ids = json.dumps(data.get('materialIds', []), ensure_ascii=False)
                    title = data.get('default_title') or data.get('title', '')
                    description = data.get('description', '')
                    tags_raw = data.get('default_tags') or data.get('tags', [])
                    if isinstance(tags_raw, list):
                        tags = json.dumps(tags_raw, ensure_ascii=False)
                    else:
                        tags_list = [t.strip() for t in str(tags_raw).split(',') if t.strip()]
                        tags = json.dumps(tags_list, ensure_ascii=False)

                    schedule_enabled = 1 if data.get('scheduleEnabled') else 0
                    videos_per_day = data.get('videosPerDay', 1)
                    schedule_date = data.get('scheduleDate', '')
                    time_point = data.get('timePoint', '10:00')

                    res = conn.execute(
                        text(
                            """
                            INSERT INTO publish_presets
                            (label, platform, accounts, material_ids, title, description, tags,
                             schedule_enabled, videos_per_day, schedule_date, time_point)
                            VALUES (:label, :platform, :accounts, :material_ids, :title, :description, :tags,
                                    :schedule_enabled, :videos_per_day, :schedule_date, :time_point)
                            """
                        ),
                        {
                            "label": label,
                            "platform": platform,
                            "accounts": accounts,
                            "material_ids": material_ids,
                            "title": title,
                            "description": description,
                            "tags": tags,
                            "schedule_enabled": schedule_enabled,
                            "videos_per_day": videos_per_day,
                            "schedule_date": schedule_date,
                            "time_point": time_point,
                        },
                    )
                    preset_id = getattr(res, "lastrowid", None)
                    r = get_redis()
                    if r is not None:
                        try:
                            r.delete("publish:presets:v1")
                        except Exception:
                            pass
                    return {"success": True, "id": preset_id}

            warnings.warn("SQLite preset_manager path is deprecated; migrate to MySQL via DATABASE_URL", DeprecationWarning)
            with sqlite3.connect(self.db_path) as conn:
                self._ensure_sqlite_preset_schema(conn)
                cursor = conn.cursor()
                
                # 提取字段 (前端 name -> 数据库 label)
                label = data.get('name') or data.get('label', '未命名计划')
                platform = json.dumps(data.get('platforms', []))
                accounts = json.dumps(data.get('accounts', []))
                material_ids = json.dumps(data.get('materialIds', []))
                # 前端 default_title -> 数据库 title
                title = data.get('default_title') or data.get('title', '')
                description = data.get('description', '')
                # 前端 default_tags -> 数据库 tags
                tags_raw = data.get('default_tags') or data.get('tags', [])
                if isinstance(tags_raw, list):
                    tags = json.dumps(tags_raw, ensure_ascii=False)
                else:
                    # 如果是逗号分隔字符串，转为列表再存
                    tags_list = [t.strip() for t in str(tags_raw).split(',') if t.strip()]
                    tags = json.dumps(tags_list, ensure_ascii=False)

                schedule_enabled = 1 if data.get('scheduleEnabled') else 0
                videos_per_day = data.get('videosPerDay', 1)
                schedule_date = data.get('scheduleDate', '')
                time_point = data.get('timePoint', '10:00')
                
                cursor.execute("""
                    INSERT INTO publish_presets 
                    (label, platform, accounts, material_ids, title, description, tags,
                     schedule_enabled, videos_per_day, schedule_date, time_point)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (label, platform, accounts, material_ids, title, description, tags,
                      schedule_enabled, videos_per_day, schedule_date, time_point))
                
                preset_id = cursor.lastrowid
                conn.commit()
                r = get_redis()
                if r is not None:
                    try:
                        r.delete("publish:presets:v1")
                    except Exception:
                        pass
                return {"success": True, "id": preset_id}
        except Exception as e:
            print(f"Error creating preset: {e}")
            return {"success": False, "error": str(e)}

    def get_all_presets(self):
        """获取所有预设"""
        try:
            r = get_redis()
            if r is not None:
                cached = r.get("publish:presets:v1")
                if cached:
                    try:
                        return json.loads(cached)
                    except Exception:
                        pass

            if mysql_enabled():
                with sa_connection() as conn:
                    rows = conn.execute(text("SELECT * FROM publish_presets ORDER BY created_at DESC")).mappings().all()
            else:
                warnings.warn("SQLite preset_manager path is deprecated; migrate to MySQL via DATABASE_URL", DeprecationWarning)
                with sqlite3.connect(self.db_path) as conn:
                    self._ensure_sqlite_preset_schema(conn)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM publish_presets ORDER BY created_at DESC")
                    rows = cursor.fetchall()
                
                presets = []
                for row in rows:
                    d = dict(row)
                    # Map database fields back to frontend expected fields
                    d['name'] = d['label']
                    d['default_title'] = d['title']
                    
                    # Parse JSON fields
                    try: d['platform'] = json.loads(d['platform']) 
                    except: d['platform'] = []
                    # Frontend expects 'platforms'
                    d['platforms'] = d['platform']
                    
                    try: d['accounts'] = json.loads(d['accounts'])
                    except: d['accounts'] = []
                    try: d['material_ids'] = json.loads(d['material_ids'])
                    except: d['material_ids'] = []
                    
                    try: 
                        d['tags'] = json.loads(d['tags']) if d['tags'] else []
                    except: 
                        d['tags'] = []
                    # Frontend expects 'default_tags' as string for display/edit usually, or list
                    # Let's provide both or stick to what frontend uses. 
                    # Frontend uses default_tags string in input, but we store list.
                    # Let's return list in default_tags for now, frontend might need adjustment if it expects string
                    d['default_tags'] = ",".join(d['tags']) if isinstance(d['tags'], list) else str(d['tags'])

                    presets.append(d)
                    
                if r is not None:
                    try:
                        r.setex("publish:presets:v1", 10, json.dumps(presets, ensure_ascii=False))
                    except Exception:
                        pass
                return presets
        except Exception as e:
            print(f"Error getting presets: {e}")
            return []

    def delete_preset(self, preset_id):
        """删除预设"""
        try:
            if mysql_enabled():
                with sa_connection() as conn:
                    conn.execute(text("DELETE FROM publish_presets WHERE id = :id"), {"id": preset_id})
                r = get_redis()
                if r is not None:
                    try:
                        r.delete("publish:presets:v1")
                    except Exception:
                        pass
                return {"success": True}

            warnings.warn("SQLite preset_manager path is deprecated; migrate to MySQL via DATABASE_URL", DeprecationWarning)
            with sqlite3.connect(self.db_path) as conn:
                self._ensure_sqlite_preset_schema(conn)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM publish_presets WHERE id = ?", (preset_id,))
                conn.commit()
            r = get_redis()
            if r is not None:
                try:
                    r.delete("publish:presets:v1")
                except Exception:
                    pass
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_preset(self, preset_id, data):
        """更新预设"""
        try:
            if mysql_enabled():
                fields = []
                values = {"id": preset_id}

                if 'name' in data:
                    fields.append("label = :label"); values["label"] = data['name']
                elif 'label' in data:
                    fields.append("label = :label"); values["label"] = data['label']

                if 'platforms' in data:
                    fields.append("platform = :platform"); values["platform"] = json.dumps(data['platforms'], ensure_ascii=False)
                if 'accounts' in data:
                    fields.append("accounts = :accounts"); values["accounts"] = json.dumps(data['accounts'], ensure_ascii=False)
                if 'materialIds' in data:
                    fields.append("material_ids = :material_ids"); values["material_ids"] = json.dumps(data['materialIds'], ensure_ascii=False)

                if 'default_title' in data:
                    fields.append("title = :title"); values["title"] = data['default_title']
                elif 'title' in data:
                    fields.append("title = :title"); values["title"] = data['title']

                if 'description' in data:
                    fields.append("description = :description"); values["description"] = data['description']

                if 'default_tags' in data:
                    tags_raw = data['default_tags']
                    if isinstance(tags_raw, list):
                        tags_json = json.dumps(tags_raw, ensure_ascii=False)
                    else:
                        tags_list = [t.strip() for t in str(tags_raw).split(',') if t.strip()]
                        tags_json = json.dumps(tags_list, ensure_ascii=False)
                    fields.append("tags = :tags"); values["tags"] = tags_json

                if 'scheduleEnabled' in data:
                    fields.append("schedule_enabled = :schedule_enabled"); values["schedule_enabled"] = 1 if data['scheduleEnabled'] else 0
                if 'videosPerDay' in data:
                    fields.append("videos_per_day = :videos_per_day"); values["videos_per_day"] = data['videosPerDay']
                if 'scheduleDate' in data:
                    fields.append("schedule_date = :schedule_date"); values["schedule_date"] = data['scheduleDate']
                if 'timePoint' in data:
                    fields.append("time_point = :time_point"); values["time_point"] = data['timePoint']

                if not fields:
                    return {"success": True}

                sql = "UPDATE publish_presets SET " + ", ".join(fields) + ", updated_at = CURRENT_TIMESTAMP WHERE id = :id"
                with sa_connection() as conn:
                    conn.execute(text(sql), values)
                r = get_redis()
                if r is not None:
                    try:
                        r.delete("publish:presets:v1")
                    except Exception:
                        pass
                return {"success": True}

            warnings.warn("SQLite preset_manager path is deprecated; migrate to MySQL via DATABASE_URL", DeprecationWarning)
            with sqlite3.connect(self.db_path) as conn:
                self._ensure_sqlite_preset_schema(conn)
                cursor = conn.cursor()
                
                # 构建更新语句
                fields = []
                values = []
                
                # Map frontend fields to DB columns
                if 'name' in data: fields.append("label = ?"); values.append(data['name'])
                elif 'label' in data: fields.append("label = ?"); values.append(data['label'])
                
                if 'platforms' in data: fields.append("platform = ?"); values.append(json.dumps(data['platforms']))
                if 'accounts' in data: fields.append("accounts = ?"); values.append(json.dumps(data['accounts']))
                if 'materialIds' in data: fields.append("material_ids = ?"); values.append(json.dumps(data['materialIds']))
                
                if 'default_title' in data: fields.append("title = ?"); values.append(data['default_title'])
                elif 'title' in data: fields.append("title = ?"); values.append(data['title'])
                
                if 'description' in data: fields.append("description = ?"); values.append(data['description'])
                
                if 'default_tags' in data:
                    tags_raw = data['default_tags']
                    if isinstance(tags_raw, list):
                        tags_json = json.dumps(tags_raw, ensure_ascii=False)
                    else:
                        tags_list = [t.strip() for t in str(tags_raw).split(',') if t.strip()]
                        tags_json = json.dumps(tags_list, ensure_ascii=False)
                    fields.append("tags = ?"); values.append(tags_json)
                
                if 'scheduleEnabled' in data: fields.append("schedule_enabled = ?"); values.append(1 if data['scheduleEnabled'] else 0)
                if 'videosPerDay' in data: fields.append("videos_per_day = ?"); values.append(data['videosPerDay'])
                if 'scheduleDate' in data: fields.append("schedule_date = ?"); values.append(data['scheduleDate'])
                if 'timePoint' in data: fields.append("time_point = ?"); values.append(data['timePoint'])
                
                fields.append("updated_at = CURRENT_TIMESTAMP")
                
                if not fields:
                    return {"success": True} # Nothing to update
                
                sql = f"UPDATE publish_presets SET {', '.join(fields)} WHERE id = ?"
                values.append(preset_id)
                
                cursor.execute(sql, values)
                conn.commit()
                r = get_redis()
                if r is not None:
                    try:
                        r.delete("publish:presets:v1")
                    except Exception:
                        pass
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def increment_usage(self, preset_id):
        """增加预设使用次数"""
        try:
            if mysql_enabled():
                with sa_connection() as conn:
                    conn.execute(text("UPDATE publish_presets SET usage_count = usage_count + 1 WHERE id = :id"), {"id": preset_id})
                r = get_redis()
                if r is not None:
                    try:
                        r.delete("publish:presets:v1")
                    except Exception:
                        pass
                return {"success": True}

            warnings.warn("SQLite preset_manager path is deprecated; migrate to MySQL via DATABASE_URL", DeprecationWarning)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE publish_presets 
                    SET usage_count = usage_count + 1 
                    WHERE id = ?
                """, (preset_id,))
                conn.commit()
            r = get_redis()
            if r is not None:
                try:
                    r.delete("publish:presets:v1")
                except Exception:
                    pass
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

preset_manager = PresetManager()
