import sqlite3
import json
import os

DB_PATH = 'e:/SynapseAutomation/syn_backend/db/database.db'

def seed_routes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 清空旧数据（仅用于开发测试）
    # cursor.execute("DELETE FROM functional_routes")
    
    routes = [
        ('douyin', 'close_guide', 'DY_GUIDE_CLOSE', '', 
         json.dumps({'close_btn': 'button:has-text("我知道了")', 'shepherd': '.shepherd-button'}), ''),
        
        ('kuaishou', 'close_guide', 'KS_GUIDE_CLOSE', '', 
         json.dumps({'popover_close': '.guide-popover .close', 'mask_close': '.ant-modal-close'}), ''),
        
        ('douyin', 'scraper', 'DY_VIDEO_LIST', 'https://creator.douyin.com/creator-micro/content/manage', '', 
         """() => {
            const videoCards = document.querySelectorAll('div[class*="video-card-"]');
            return Array.from(videoCards).map(card => {
                const text = card.innerText;
                const getStat = (label) => {
                    const regex = new RegExp(label + '\\s*([\\d\\w.]+)');
                    const match = text.match(regex);
                    return match ? match[1] : "0";
                };
                return {
                    title: card.querySelector('div[class*="info-title-text-"]')?.innerText.trim(),
                    play_count: getStat("播放"),
                    like_count: getStat("点赞"),
                    comment_count: getStat("评论"),
                    share_count: getStat("分享"),
                    publish_time: text.match(/\\d{4}年\\d{2}月\\d{2}日\\s*\\d{2}:\\d{2}/)?.[0]
                };
            });
         }"""),
        
        ('kuaishou', 'scraper', 'KS_VIDEO_LIST', 'https://cp.kuaishou.com/article/manage/video', '', 
         """() => {
            const items = document.querySelectorAll(".video-item");
            return Array.from(items).map(item => {
                const title = item.querySelector(".video-item__detail__row__title")?.innerText;
                const stats = Array.from(item.querySelectorAll(".video-item__detail__row__label")).map(l => l.innerText);
                return {
                    title: title,
                    play_count: stats[0] || "0",
                    like_count: stats[1] || "0",
                    comment_count: stats[2] || "0",
                    publish_time: item.querySelector(".video-item__detail__row__time")?.innerText
                };
            });
         }""")
    ]
    
    cursor.executemany(
        'INSERT INTO functional_routes (platform, route_type, route_name, url_pattern, selectors, js_logic) VALUES (?, ?, ?, ?, ?, ?)', 
        routes
    )
    conn.commit()
    conn.close()
    print("Routes seeded successfully")

if __name__ == "__main__":
    seed_routes()
