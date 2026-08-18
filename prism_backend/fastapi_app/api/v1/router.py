"""
API v1 路由总入口
"""
from fastapi import APIRouter

# 导入各模块路由
from .accounts.router import router as accounts_router
from .campaigns.router import router as campaigns_router
from .auth.router import router as auth_router
from .files.router import router as files_router
from .analytics.router import router as analytics_router
from .scripts.router import router as scripts_router
from .publish.router import router as publish_router
from .tasks.router import router as tasks_router
from .tasks.distribution_alias import router as distribution_router
from .recovery.router import router as recovery_router
from .data.router import router as data_router
from .ai.router import router as ai_router
from .ai.threads_router import router as ai_threads_router
from .ai_prompts.router import router as ai_prompts_router  # AI配置管理
from .dashboard.router import router as dashboard_router
from .system.router import router as system_router
from .verification.router import router as verification_router
from .agent.router import router as agent_router
from .matrix.router import router as matrix_router
from .manual_tasks.router import router as manual_tasks_router
from .campaigns.plans_alias import router as plans_router
from .campaigns.task_packages import router as task_packages_router
from .ip_pool.router import router as ip_pool_router
from .concurrency.router import router as concurrency_router
from .cookies.router import router as cookies_router
from .creator.router import router as creator_router
from .mediacrawler.router import router as mediacrawler_router
from .crawler.router import router as crawler_router
from .tikhub.router import router as tikhub_router

# 导入平台路由
from .platforms.douyin.router import router as douyin_router
from .platforms.kuaishou.router import router as kuaishou_router
from .platforms.xiaohongshu.router import router as xiaohongshu_router
from .platforms.tencent.router import router as tencent_router
from .platforms.bilibili.router_biliup import router as bilibili_router  # 使用 biliup 版本
from .platforms.tasks.router import router as platform_tasks_router

# 创建API路由器
api_router = APIRouter()

# 注册子路由
api_router.include_router(accounts_router, prefix="/accounts", tags=["账号管理"])
api_router.include_router(campaigns_router, tags=["计划管理"])  # router 已自带 /campaigns 前缀
api_router.include_router(auth_router, tags=["认证登录"])  # router 已自带 /auth 前缀
api_router.include_router(files_router, tags=["文件管理"])  # router 已自带 /files 前缀
api_router.include_router(analytics_router)  # router 已自带 /analytics 前缀
api_router.include_router(scripts_router)  # router 已自带 /scripts 前缀
api_router.include_router(publish_router, tags=["视频发布"])  # router 已自带 /publish 前缀
api_router.include_router(tasks_router)  # router 已自带 /tasks 前缀
api_router.include_router(distribution_router)  # /tasks/distribution (当前实现为占位)
api_router.include_router(recovery_router)  # router 已自带 /recovery 前缀
api_router.include_router(data_router)  # router 已自带 /data 前缀
api_router.include_router(ai_router)  # router 已自带 /ai 前缀
api_router.include_router(ai_threads_router, prefix="/ai")  # 嵌套在 /ai/threads 下
api_router.include_router(ai_prompts_router, tags=["AI配置管理"])  # AI配置管理 /ai-prompts
api_router.include_router(dashboard_router)  # router 已自带 /dashboard 前缀
api_router.include_router(system_router)  # router 已自带 /system 前缀
api_router.include_router(verification_router)  # router 已自带 /verification 前缀
api_router.include_router(agent_router)  # router 已自带 /agent 前缀
api_router.include_router(matrix_router)  # router 已自带 /matrix 前缀
api_router.include_router(manual_tasks_router)  # router 已自带 /manual-tasks 前缀
api_router.include_router(plans_router)  # /plans (原 /api/plans 兼容入口升级为 v1)
api_router.include_router(task_packages_router)  # /task-packages (原 /api/task-packages 入口升级为 v1)
api_router.include_router(ip_pool_router)  # router 已自带 /ip-pool 前缀
api_router.include_router(concurrency_router)  # router 已自带 /concurrency 前缀
api_router.include_router(cookies_router)  # router 已自带 /cookies 前缀
api_router.include_router(creator_router)  # router 已自带 /creator 前缀
api_router.include_router(mediacrawler_router)  # /mediacrawler
api_router.include_router(crawler_router, prefix="/crawler", tags=["混合爬虫"])  # /crawler
api_router.include_router(tikhub_router)  # router 已自带 /tikhub 前缀

# 注册平台路由
api_router.include_router(douyin_router)  # router 已自带 /platforms/douyin 前缀
api_router.include_router(kuaishou_router)  # router 已自带 /platforms/kuaishou 前缀
api_router.include_router(xiaohongshu_router)  # router 已自带 /platforms/xiaohongshu 前缀
api_router.include_router(tencent_router)  # router 已自带 /platforms/tencent 前缀
api_router.include_router(bilibili_router)  # router 已自带 /platforms/bilibili 前缀
api_router.include_router(platform_tasks_router)  # router 已自带 /platforms/tasks 前缀


@api_router.get("/ping")
async def ping():
    """测试接口"""
    return {"message": "pong"}
