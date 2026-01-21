"""
Direct crawler test - no API calls
"""
import asyncio
import sys
sys.path.insert(0, 'syn_backend/douyin_tiktok_api')

from crawlers.hybrid.hybrid_crawler import HybridCrawler

async def test():
    urls = [
        "https://www.douyin.com/jingxuan?modal_id=7588371813466677413",
        "https://v.douyin.com/tucQaaVfhHE/",
    ]

    crawler = HybridCrawler()

    for idx, url in enumerate(urls, 1):
        print(f"\n[Test {idx}] URL: {url}")
        print("-" * 60)

        try:
            data = await crawler.hybrid_parsing_single_video(url=url, minimal=False)

            print("SUCCESS!")
            print(f"Video ID: {data.get('aweme_id', 'N/A')}")
            print(f"Title: {data.get('desc', 'N/A')[:60]}...")

            author = data.get('author', {})
            print(f"Author: {author.get('nickname', 'N/A')}")

            stats = data.get('statistics', {})
            print(f"Likes: {stats.get('digg_count', 0):,}")
            print(f"Comments: {stats.get('comment_count', 0):,}")
            print(f"Shares: {stats.get('share_count', 0):,}")
            print(f"Collects: {stats.get('collect_count', 0):,}")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

asyncio.run(test())
