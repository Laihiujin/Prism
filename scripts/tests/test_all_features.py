"""
快速功能测试脚本
测试所有新实现的功能
"""
import asyncio
import httpx
from loguru import logger

BASE_URL = "http://localhost:8000/api"


async def test_batch_verify():
    """测试批量验证"""
    logger.info("=" * 50)
    logger.info("测试1: 批量验证账号")
    logger.info("=" * 50)

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(f"{BASE_URL}/accounts/batch-verify")
            data = response.json()

            logger.info(f"状态码: {response.status_code}")
            logger.info(f"响应: {data}")

            if data.get("success"):
                logger.success("✅ 批量验证成功!")
                stats = data.get("data", {})
                logger.info(f"  - 总数: {stats.get('total')}")
                logger.info(f"  - 有效: {stats.get('valid')}")
                logger.info(f"  - 失效: {stats.get('expired')}")
                logger.info(f"  - 错误: {stats.get('error')}")
            else:
                logger.error("❌ 批量验证失败")

        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")


async def test_account_stats():
    """测试账号统计"""
    logger.info("=" * 50)
    logger.info("测试2: 获取账号统计")
    logger.info("=" * 50)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/accounts/stats")
            data = response.json()

            logger.info(f"状态码: {response.status_code}")
            logger.info(f"统计数据: {data}")

            logger.success("✅ 账号统计获取成功!")

        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")


async def test_data_crawler():
    """测试数据抓取"""
    logger.info("=" * 50)
    logger.info("测试3: 数据抓取功能")
    logger.info("=" * 50)

    # 先测试健康检查
    async with httpx.AsyncClient() as client:
        try:
            # 健康检查
            response = await client.get(f"{BASE_URL}/data/health")
            data = response.json()
            logger.info(f"数据模块状态: {data}")

            if data.get("status") == "success":
                logger.success("✅ 数据模块运行正常")
            else:
                logger.warning("⚠️ 数据模块状态异常")

            # 测试抖音热榜（不需要参数）
            logger.info("\n测试抖音热榜...")
            try:
                response = await client.get(f"{BASE_URL}/data/douyin/hot-search")
                if response.status_code == 200:
                    logger.success("✅ 抖音热榜接口正常")
                else:
                    logger.warning(f"⚠️ 抖音热榜返回: {response.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ 抖音热榜测试失败: {e}")

        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")


async def test_task_queue():
    """测试任务队列状态"""
    logger.info("=" * 50)
    logger.info("测试4: 任务队列状态")
    logger.info("=" * 50)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/tasks/status")
            data = response.json()

            logger.info(f"任务队列状态: {data}")
            logger.success("✅ 任务队列查询成功")

        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")


async def test_publish_status():
    """测试发布状态统计"""
    logger.info("=" * 50)
    logger.info("测试5: 发布状态统计")
    logger.info("=" * 50)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/data/publish-status")
            data = response.json()

            logger.info(f"发布统计: {data}")

            if data.get("status") == "success":
                stats = data.get("data", {})
                logger.info(f"  - 已发布: {stats.get('published')}")
                logger.info(f"  - 待发布: {stats.get('pending')}")
                logger.info(f"  - 失败: {stats.get('failed')}")
                logger.success("✅ 发布统计查询成功")
            else:
                logger.warning("⚠️ 发布统计查询异常")

        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")


async def main():
    """运行所有测试"""
    logger.info("\n")
    logger.info("🚀 开始运行功能测试...")
    logger.info("\n")

    # 运行所有测试
    await test_batch_verify()
    await asyncio.sleep(1)

    await test_account_stats()
    await asyncio.sleep(1)

    await test_data_crawler()
    await asyncio.sleep(1)

    await test_task_queue()
    await asyncio.sleep(1)

    await test_publish_status()

    logger.info("\n")
    logger.info("=" * 50)
    logger.info("🎉 所有测试完成!")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
