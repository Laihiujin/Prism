import json
import sys
import os

# Set UTF-8 encoding for console output
if os.name == 'nt':  # Windows
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load data
with open('douyin_video_data.json', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 60)
print("Douyin Video Data Summary")
print("=" * 60)

print("\n=== Video Info ===")
print(f"Title: {data.get('desc', 'N/A')}")
print(f"Video ID: {data.get('aweme_id', 'N/A')}")
print(f"Duration: {data.get('duration', 'N/A')} ms")
print(f"Create Time: {data.get('create_time', 'N/A')}")

print("\n=== Statistics ===")
stats = data.get('statistics', {})
print(f"Likes: {stats.get('digg_count', 0)}")
print(f"Comments: {stats.get('comment_count', 0)}")
print(f"Shares: {stats.get('share_count', 0)}")
print(f"Downloads: {stats.get('download_count', 0)}")
print(f"Forwards: {stats.get('forward_count', 0)}")
print(f"Plays: {stats.get('play_count', 0)}")
print(f"Collects: {stats.get('collect_count', 0)}")

print("\n=== Author ===")
author = data.get('author', {})
print(f"Nickname: {author.get('nickname', 'N/A')}")
print(f"User ID: {author.get('uid', 'N/A')}")
print(f"Sec UID: {author.get('sec_uid', 'N/A')}")
print(f"Followers: {author.get('follower_count', 0)}")
print(f"Following: {author.get('following_count', 0)}")
print(f"Total Favorited: {author.get('total_favorited', 0)}")

print("\n=== Video URLs ===")
video_info = data.get('video', {})
if video_info:
    play_addr = video_info.get('play_addr', {})
    if play_addr.get('url_list'):
        print(f"Play URL: {play_addr['url_list'][0]}")

    cover = video_info.get('cover', {})
    if cover.get('url_list'):
        print(f"Cover URL: {cover['url_list'][0]}")

    dynamic_cover = video_info.get('dynamic_cover', {})
    if dynamic_cover.get('url_list'):
        print(f"Dynamic Cover: {dynamic_cover['url_list'][0]}")

    print(f"Video Width: {video_info.get('width', 'N/A')}")
    print(f"Video Height: {video_info.get('height', 'N/A')}")
    print(f"Video Ratio: {video_info.get('ratio', 'N/A')}")

print("\n=== Music ===")
music = data.get('music', {})
if music:
    print(f"Music Title: {music.get('title', 'N/A')}")
    print(f"Music Author: {music.get('author', 'N/A')}")
    print(f"Music ID: {music.get('id', 'N/A')}")
    play_url = music.get('play_url', {})
    if play_url.get('url_list'):
        print(f"Music URL: {play_url['url_list'][0]}")

print("\n=== Hashtags ===")
text_extra = data.get('text_extra', [])
if text_extra:
    hashtags = [item.get('hashtag_name', '') for item in text_extra if item.get('hashtag_name')]
    print(f"Hashtags: {', '.join(hashtags) if hashtags else 'None'}")

print("\n=== Available Data Keys ===")
print(f"Total keys: {len(data.keys())}")
print("Main keys:", ', '.join(list(data.keys())[:20]))

print("\n" + "=" * 60)
