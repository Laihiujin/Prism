"""
混合爬虫 API 测试脚本
Test script for Hybrid Crawler API
"""
import asyncio
import httpx
import json

API_BASE_URL = "http://localhost:7000/api/v1"


async def test_external_video_crawler():
    """测试外部视频链接抓取"""
    print("=" * 60)
    print("测试 1: 外部视频链接抓取（混合爬虫）")
    print("=" * 60)

    # 测试链接
    test_urls = [
        "https://v.douyin.com/wuH9DyoAYbE/",  # 抖音
        # "https://www.tiktok.com/@user/video/xxx",  # TikTok
        # "https://b23.tv/xxx",  # Bilibili
    ]

    async with httpx.AsyncClient(timeout=60.0) as client:
        for url in test_urls:
            print(f"\n正在抓取: {url}")
            try:
                response = await client.post(
                    f"{API_BASE_URL}/crawler/fetch_video",
                    json={"url": url, "minimal": False}
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    print(f"✅ 抓取成功！")
                    print(f"平台: {result.get('platform')}")
                    data = result.get("data", {})

                    # 显示关键信息
                    if result.get('platform') in ['douyin', 'tiktok']:
                        print(f"标题: {data.get('desc', 'N/A')[:50]}...")
                        print(f"作者: {data.get('author', {}).get('nickname', 'N/A')}")
                        stats = data.get('statistics', {})
                        print(f"点赞: {stats.get('digg_count', 0):,}")
                        print(f"评论: {stats.get('comment_count', 0):,}")
                    elif result.get('platform') == 'bilibili':
                        print(f"标题: {data.get('title', 'N/A')[:50]}...")
                        print(f"UP主: {data.get('owner', {}).get('name', 'N/A')}")
                        stat = data.get('stat', {})
                        print(f"播放: {stat.get('view', 0):,}")
                        print(f"点赞: {stat.get('like', 0):,}")
                else:
                    print(f"❌ 抓取失败: {result.get('error')}")

            except Exception as e:
                print(f"❌ 请求失败: {e}")


async def test_account_video_crawler():
    """测试项目内账号视频列表抓取"""
    print("\n\n" + "=" * 60)
    print("测试 2: 项目内账号视频列表抓取（专用爬虫）")
    print("=" * 60)

    # 测试配置
    test_accounts = [
        {
            "platform": "douyin",
            "user_id": "MS4wLjABAAAA5kTggi1oS7T33oIQGSqQdN7eYOXSWjJBGSqY6aU5GdM",  # 龙之谷：怀旧
            "max_cursor": 0,
            "count": 5
        },
        # {
        #     "platform": "bilibili",
        #     "user_id": "123456",  # 替换为实际的 B站 mid
        #     "max_cursor": 0,
        #     "count": 5
        # }
    ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        for account in test_accounts:
            print(f"\n正在抓取账号: {account['platform']} - {account['user_id']}")
            try:
                response = await client.post(
                    f"{API_BASE_URL}/crawler/fetch_account_videos",
                    json=account
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    print(f"✅ 抓取成功！")
                    data = result.get("data", {})

                    # 显示视频列表
                    if account['platform'] == 'douyin':
                        aweme_list = data.get('aweme_list', [])
                        print(f"视频数量: {len(aweme_list)}")
                        for i, video in enumerate(aweme_list[:3], 1):
                            desc = video.get('desc', 'N/A')[:40]
                            stats = video.get('statistics', {})
                            print(f"  {i}. {desc}...")
                            print(f"     点赞: {stats.get('digg_count', 0):,}")
                    elif account['platform'] == 'bilibili':
                        vlist = data.get('list', {}).get('vlist', [])
                        print(f"视频数量: {len(vlist)}")
                        for i, video in enumerate(vlist[:3], 1):
                            title = video.get('title', 'N/A')[:40]
                            play = video.get('play', 0)
                            print(f"  {i}. {title}...")
                            print(f"     播放: {play:,}")
                else:
                    print(f"❌ 抓取失败: {result.get('error')}")

            except Exception as e:
                print(f"❌ 请求失败: {e}")


async def test_supported_platforms():
    """测试获取支持的平台列表"""
    print("\n\n" + "=" * 60)
    print("测试 3: 获取支持的平台列表")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{API_BASE_URL}/crawler/supported_platforms"
            )
            response.raise_for_status()
            result = response.json()

            platforms = result.get("platforms", [])
            print(f"\n支持的平台数量: {len(platforms)}\n")

            for platform in platforms:
                print(f"平台: {platform['display_name']} ({platform['name']})")
                print(f"  URL 关键字: {', '.join(platform['url_keywords'])}")
                print(f"  示例链接: {platform['example_url']}")
                print(f"  外部链接支持: {'✅' if platform['supports_external'] else '❌'}")
                print(f"  项目内账号支持: {'✅' if platform['supports_account'] else '❌'}")
                print()

        except Exception as e:
            print(f"❌ 请求失败: {e}")


async def main():
    """主函数"""
    print("\n混合爬虫 API 测试\n")
    print("确保后端服务已启动: http://localhost:7000\n")

    # 运行测试
    await test_external_video_crawler()
    await test_account_video_crawler()
    await test_supported_platforms()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
