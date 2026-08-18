"""
Video analytics collection script.
Recommended cron: 0 2 * * * cd /path/to/syn_backend && python scripts/collect_analytics.py
"""
import asyncio
import os
import sys

sys_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from myUtils.video_collector import collector


async def main():
    print("=" * 60)
    print("[Collector] Start scheduled collection")
    print("=" * 60)

    try:
        results = await collector.collect_all_accounts()

        print("\n" + "=" * 60)
        print("[Collector] Report")
        print("=" * 60)
        print(f"Total accounts: {results['total']}")
        print(f"Success: {results['success']}")
        print(f"Failed: {results['failed']}")

        print("\nDetails:")
        for detail in results["details"]:
            status = "OK" if detail["success"] else "FAIL"
            count = detail.get("count", 0)
            error = detail.get("error", "")

            if detail["success"]:
                print(f"{status} {detail['account']} ({detail['platform']}): collected {count} videos")
            else:
                print(f"{status} {detail['account']} ({detail['platform']}): {error}")

        print("\nCollection finished")

    except Exception as e:
        print(f"Collection failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
