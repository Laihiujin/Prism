"""
测试抖音 API 抓取视频数据
Test Douyin API video data fetching
"""
import sys
import asyncio
sys.path.append('syn_backend/douyin_tiktok_api')

from crawlers.douyin.web.web_crawler import DouyinWebCrawler
from crawlers.hybrid.hybrid_crawler import HybridCrawler

async def test_douyin_api():
    """测试抖音 API 抓取功能"""

    # 用户提供的链接
    url = "https://v.douyin.com/wuH9DyoAYbE/"

    print("=" * 60)
    print("测试抖音 API 数据抓取")
    print("=" * 60)
    print(f"\n测试链接: {url}\n")

    # 方法 1: 使用混合爬虫（推荐，最简单）
    print("\n[方法 1] 使用混合爬虫解析...")
    print("-" * 60)
    try:
        hybrid_crawler = HybridCrawler()
        data = await hybrid_crawler.hybrid_parsing_single_video(url=url, minimal=False)

        print("[SUCCESS] Video data fetched successfully!")
        print(f"\nVideo Title: {data.get('desc', 'N/A')}")
        print(f"Author: {data.get('author', {}).get('nickname', 'N/A')}")
        print(f"Likes: {data.get('statistics', {}).get('digg_count', 'N/A')}")
        print(f"Comments: {data.get('statistics', {}).get('comment_count', 'N/A')}")
        print(f"Shares: {data.get('statistics', {}).get('share_count', 'N/A')}")
        print(f"Views: {data.get('statistics', {}).get('play_count', 'N/A')}")
        print(f"\nData Structure:")
        print(f"Keys: {list(data.keys())}")

        # Save data to file
        import json
        with open('douyin_video_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n[SUCCESS] Full data saved to: douyin_video_data.json")

    except Exception as e:
        print(f"[ERROR] Hybrid crawler failed: {e}")
        import traceback
        traceback.print_exc()

    # 方法 2: 使用抖音专用爬虫
    print("\n\n[方法 2] 使用抖音专用爬虫...")
    print("-" * 60)
    try:
        douyin_crawler = DouyinWebCrawler()

        # Step 1: Extract video ID
        print("Step 1: Extract video ID...")
        aweme_id = await douyin_crawler.get_aweme_id(url)
        print(f"[SUCCESS] Video ID: {aweme_id}")

        # Step 2: Get video detailed data
        print("\nStep 2: Get video detailed data...")
        video_data = await douyin_crawler.fetch_one_video(aweme_id)
        print("[SUCCESS] Video detailed data fetched!")

        # Save data
        import json
        with open('douyin_video_data_detailed.json', 'w', encoding='utf-8') as f:
            json.dump(video_data, f, ensure_ascii=False, indent=2)
        print(f"[SUCCESS] Detailed data saved to: douyin_video_data_detailed.json")

    except Exception as e:
        print(f"[ERROR] Douyin crawler failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_douyin_api())
