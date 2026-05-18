"""
快速测试 - FastAPI 投放计划模块第1天组件

只测试基本功能，不包含耗时测试
"""

import asyncio
import pytest
from pathlib import Path
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from syn_backend.fastapi_app.core.async_task_pool import AsyncTaskPool
from syn_backend.fastapi_app.core.rate_limiter import RateLimiter
from syn_backend.fastapi_app.api.v1.campaigns.schemas import (
    PlanCreate,
    PackageCreate,
    TimeStrategy,
    TimeStrategyMode,
    DispatchMode
)


async def test_async_task_pool():
    """测试异步任务池"""
    print("\n测试1: AsyncTaskPool 基本功能")
    print("="*50)

    pool = AsyncTaskPool(max_workers=2)

    async def sample_task(name: str, duration: float):
        await asyncio.sleep(duration)
        return f"Result from {name}"

    # 提交任务
    task_id = await pool.submit_task(
        task_id="test_task",
        coro=sample_task("Task-1", 0.5),
        priority=5
    )

    print(f"已提交任务: {task_id}")

    # 等待完成
    await pool.wait_all(timeout=2)

    # 检查结果
    status = await pool.get_task_status(task_id)
    print(f"任务状态: {status['status']}")
    print(f"任务结果: {status['result']}")

    assert status['status'] == 'completed'
    print("✅ AsyncTaskPool测试通过!\n")


async def test_rate_limiter():
    """测试限流器"""
    print("测试2: RateLimiter 基本功能")
    print("="*50)

    limiter = RateLimiter()

    # 测试获取许可
    success = await limiter.acquire("douyin", timeout=1)
    print(f"获得许可: {success}")

    # 检查状态
    status = await limiter.get_platform_status("douyin")
    print(f"平台状态: {status}")

    assert success == True
    print("✅ RateLimiter测试通过!\n")


def test_schemas():
    """测试Pydantic模型"""
    print("测试3: Pydantic Schemas")
    print("="*50)

    # 测试时间策略
    time_strategy = TimeStrategy(
        mode=TimeStrategyMode.ONCE,
        date="2025-11-28",
        time_points=["10:00", "14:00"]
    )
    print(f"✓ TimeStrategy: {time_strategy.mode}")

    # 测试计划创建
    plan = PlanCreate(
        name="测试计划",
        platforms=["douyin", "kuaishou"],
        start_date="2025-11-28",
        end_date="2025-12-05"
    )
    print(f"✓ PlanCreate: {plan.name}")

    # 测试任务包创建
    package = PackageCreate(
        plan_id=1,
        name="测试任务包",
        platform="douyin",
        account_ids=["account_1"],
        material_ids=["video_1"],
        dispatch_mode=DispatchMode.RANDOM,
        time_strategy=time_strategy
    )
    print(f"✓ PackageCreate: {package.name}")

    print("✅ Schemas测试通过!\n")


def test_schema_validation():
    """测试数据验证"""
    print("测试4: Schema 数据验证")
    print("="*50)

    # 测试无效日期
    try:
        TimeStrategy(
            mode=TimeStrategyMode.ONCE,
            date="2025/11/28",  # 错误格式
            time_points=["10:00"]
        )
        assert False, "应该抛出验证错误"
    except ValueError:
        print("✓ 正确捕获无效日期格式")

    # 测试无效时间
    try:
        TimeStrategy(
            mode=TimeStrategyMode.ONCE,
            date="2025-11-28",
            time_points=["25:00"]  # 错误时间
        )
        assert False, "应该抛出验证错误"
    except ValueError:
        print("✓ 正确捕获无效时间格式")

    print("✅ 数据验证测试通过!\n")


async def run_async_tests():
    """运行异步测试"""
    await test_async_task_pool()
    await test_rate_limiter()


def main():
    """主函数"""
    print("\n" + "="*70)
    print("FastAPI 投放计划模块 - 第1天快速测试")
    print("="*70 + "\n")

    # 同步测试
    test_schemas()
    test_schema_validation()

    # 异步测试
    asyncio.run(run_async_tests())

    print("="*70)
    print("🎉 第1天所有快速测试通过!")
    print("="*70)
    print("\n完成的组件:")
    print("  ✅ AsyncTaskPool - 异步任务池")
    print("  ✅ RateLimiter - 速率限制器")
    print("  ✅ Pydantic Schemas - 数据模型")
    print("  ✅ Dependencies - 依赖注入")
    print("\n✨ 第1天任务完成!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
