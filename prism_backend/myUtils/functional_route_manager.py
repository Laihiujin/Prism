import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
import os

BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / os.getenv("DB_PATH_REL", "db/database.db")

class FunctionalRouteManager:
    """管理和执行平台功能路由（抓取、关闭引导等）"""

    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def get_routes(self, platform: str, route_type: str) -> List[Dict[str, Any]]:
        """获取特定平台和类型的路由"""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM functional_routes WHERE platform = ? AND route_type = ?",
                    (platform, route_type)
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get routes: {e}")
            return []

    async def execute_close_guides(self, page, platform: str):
        """执行指定平台的关闭引导路由"""
        routes = self.get_routes(platform, "close_guide")
        for route in routes:
            try:
                logger.info(f"Executing close_guide route: {route['route_name']}")
                selectors = json.loads(route['selectors']) if route['selectors'] else {}
                
                # 如果有 JS 逻辑优先执行
                if route['js_logic']:
                    await page.evaluate(route['js_logic'])
                
                # 如果有选择器逻辑，依次尝试点击关闭
                for key, sel in selectors.items():
                    if "close" in key.lower() or "button" in key.lower():
                        if await page.query_selector(sel):
                            await page.click(sel)
                            logger.info(f"Clicked guide close button: {sel}")
                            await page.wait_for_timeout(500)
            except Exception as e:
                logger.warning(f"Failed to execute close_guide {route['route_name']}: {e}")

    async def run_scraper(self, page, platform: str, route_name: str) -> List[Dict[str, Any]]:
        """执行抓取路由"""
        routes = self.get_routes(platform, "scraper")
        route = next((r for r in routes if r['route_name'] == route_name), None)
        if not route:
            logger.warning(f"Scraper route {route_name} not found for {platform}")
            return []

        try:
            if route['js_logic']:
                return await page.evaluate(route['js_logic'])
            else:
                # 默认提取逻辑（基于选择器）
                # 这里可以扩展通用提取引擎
                return []
        except Exception as e:
            logger.error(f"Failed to run scraper {route_name}: {e}")
            return []

functional_route_manager = FunctionalRouteManager()
