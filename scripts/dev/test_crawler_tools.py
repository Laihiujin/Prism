"""
测试抖音视频数据抓取工具
Test Douyin Video Crawler Tools

对比测试：
1. 新工具：ExternalVideoCrawlerTool (混合爬虫，直接调用)
2. 旧工具：DouyinFetchVideoDetailTool (HTTP API 调用)
"""
import asyncio
import httpx
import sys
import os

# 测试链接
TEST_URLS = [
    "https://www.douyin.com/jingxuan?modal_id=7588371813466677413",
    "https://v.douyin.com/tucQaaVfhHE/",
]

API_BASE_URL = "http://localhost:7000/api/v1"


async def test_new_crawler_tool():
    """测试新工具：混合爬虫（直接调用内部模块）"""
    print("=" * 80)
    print("测试 1: 新工具 - 混合爬虫 (ExternalVideoCrawlerTool)")
    print("=" * 80)
    print("调用方式: POST /api/v1/crawler/fetch_video")
    print()

    async with httpx.AsyncClient(timeout=60.0) as client:
        for idx, url in enumerate(TEST_URLS, 1):
            print(f"\n[测试 {idx}] URL: {url}")
            print("-" * 80)

            try:
                response = await client.post(
                    f"{API_BASE_URL}/crawler/fetch_video",
                    json={"url": url, "minimal": False}
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success"):
                    print("✅ 抓取成功!")
                    data = result.get("data", {})
                    platform = result.get("platform", "unknown")

                    print(f"平台: {platform.upper()}")
                    print(f"视频ID: {data.get('aweme_id', 'N/A')}")
                    print(f"标题: {data.get('desc', 'N/A')[:60]}...")

                    author = data.get('author', {})
                    print(f"作者: {author.get('nickname', 'N/A')}")

                    stats = data.get('statistics', {})
                    print(f"点赞: {stats.get('digg_count', 0):,}")
                    print(f"评论: {stats.get('comment_count', 0):,}")
                    print(f"分享: {stats.get('share_count', 0):,}")
                    print(f"收藏: {stats.get('collect_count', 0):,}")

                    # 视频链接
                    video = data.get('video', {})
                    if video:
                        play_addr = video.get('play_addr', {})
                        url_list = play_addr.get('url_list', [])
                        if url_list:
                            print(f"视频链接: {url_list[0][:80]}...")
                else:
                    print(f"❌ 抓取失败: {result.get('error')}")

            except httpx.HTTPStatusError as e:
                print(f"❌ HTTP 错误: {e.response.status_code}")
                print(f"   响应: {e.response.text[:200]}")
            except Exception as e:
                print(f"❌ 请求失败: {e}")


async def test_old_api_tool():
    """测试旧工具：HTTP API 调用 douyin_tiktok_api"""
    print("\n\n")
    print("=" * 80)
    print("测试 2: 旧工具 - HTTP API (DouyinFetchVideoDetailTool)")
    print("=" * 80)
    print("调用方式: GET /api/v1/douyin-tiktok/api/douyin/web/fetch_one_video")
    print()

    # 需要先提取视频ID
    sys.path.insert(0, 'syn_backend/douyin_tiktok_api')
    from crawlers.douyin.web.web_crawler import DouyinWebCrawler

    douyin_crawler = DouyinWebCrawler()

    async with httpx.AsyncClient(timeout=60.0) as client:
        for idx, url in enumerate(TEST_URLS, 1):
            print(f"\n[测试 {idx}] URL: {url}")
            print("-" * 80)

            try:
                # 步骤 1: 提取视频ID
                print("步骤 1: 提取视频 ID...")
                aweme_id = await douyin_crawler.get_aweme_id(url)
                print(f"✅ 视频ID: {aweme_id}")

                # 步骤 2: 通过 HTTP API 获取视频详情
                print("\n步骤 2: 调用 HTTP API 获取详情...")
                response = await client.get(
                    f"{API_BASE_URL}/douyin-tiktok/api/douyin/web/fetch_one_video",
                    params={"aweme_id": aweme_id}
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 200:
                    print("✅ 抓取成功!")
                    data = result.get("data", {}).get("aweme_detail", {})

                    print(f"视频ID: {data.get('aweme_id', 'N/A')}")
                    print(f"标题: {data.get('desc', 'N/A')[:60]}...")

                    author = data.get('author', {})
                    print(f"作者: {author.get('nickname', 'N/A')}")

                    stats = data.get('statistics', {})
                    print(f"点赞: {stats.get('digg_count', 0):,}")
                    print(f"评论: {stats.get('comment_count', 0):,}")
                    print(f"分享: {stats.get('share_count', 0):,}")
                    print(f"收藏: {stats.get('collect_count', 0):,}")

                    # 视频链接
                    video = data.get('video', {})
                    if video:
                        play_addr = video.get('play_addr', {})
                        url_list = play_addr.get('url_list', [])
                        if url_list:
                            print(f"视频链接: {url_list[0][:80]}...")
                else:
                    print(f"❌ API 返回错误: {result.get('message', '未知错误')}")

            except httpx.HTTPStatusError as e:
                print(f"❌ HTTP 错误: {e.response.status_code}")
                print(f"   响应: {e.response.text[:200]}")
            except Exception as e:
                print(f"❌ 请求失败: {e}")
                import traceback
                traceback.print_exc()


async def test_direct_crawler():
    """测试直接调用爬虫（不通过 API）"""
    print("\n\n")
    print("=" * 80)
    print("测试 3: 直接调用爬虫（内部模块，不通过 API）")
    print("=" * 80)
    print()

    sys.path.insert(0, 'syn_backend/douyin_tiktok_api')
    from crawlers.hybrid.hybrid_crawler import HybridCrawler

    hybrid_crawler = HybridCrawler()

    for idx, url in enumerate(TEST_URLS, 1):
        print(f"\n[测试 {idx}] URL: {url}")
        print("-" * 80)

        try:
            data = await hybrid_crawler.hybrid_parsing_single_video(url=url, minimal=False)

            print("✅ 抓取成功!")
            print(f"视频ID: {data.get('aweme_id', 'N/A')}")
            print(f"标题: {data.get('desc', 'N/A')[:60]}...")

            author = data.get('author', {})
            print(f"作者: {author.get('nickname', 'N/A')}")

            stats = data.get('statistics', {})
            print(f"点赞: {stats.get('digg_count', 0):,}")
            print(f"评论: {stats.get('comment_count', 0):,}")
            print(f"分享: {stats.get('share_count', 0):,}")
            print(f"收藏: {stats.get('collect_count', 0):,}")

        except Exception as e:
            print(f"❌ 抓取失败: {e}")
            import traceback
            traceback.print_exc()


async def main():
    print("\n")
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "抖音视频数据抓取工具对比测试" + " " * 27 + "║")
    print("╚" + "═" * 78 + "╝")
    print()

    # 运行所有测试
    await test_new_crawler_tool()
    await test_old_api_tool()
    await test_direct_crawler()

    print("\n\n")
    print("=" * 80)
    print("测试完成!")
    print("=" * 80)
    print()
    print("总结:")
    print("1. 新工具 (混合爬虫): 直接调用内部模块，速度快，无需 HTTP 调用")
    print("2. 旧工具 (HTTP API): 通过 HTTP 调用 douyin_tiktok_api，功能完整")
    print("3. 直接爬虫: 最原始的调用方式，最快，适合批量处理")
    print()


if __name__ == "__main__":
    asyncio.run(main())
