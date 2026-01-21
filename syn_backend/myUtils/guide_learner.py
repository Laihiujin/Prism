"""
智能引导关键词学习系统
功能：
1. 自动检测页面上的可疑引导按钮
2. 记录未识别的按钮文字
3. 自动更新配置文件
"""
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Set

BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "config" / "guide_config.json"
LEARNING_LOG = BASE_DIR / "logs" / "guide_learning.json"

# 可疑按钮的特征
SUSPICIOUS_PATTERNS = [
    r".*知道.*",
    r".*了解.*",
    r".*学会.*",
    r".*体验.*",
    r".*跳过.*",
    r".*关闭.*",
    r".*确定.*",
    r".*好的.*",
    r".*下一步.*",
    r".*继续.*",
    r".*开始.*",
    r".*got\s*it.*",
    r".*next.*",
    r".*skip.*",
    r".*close.*",
    r".*ok.*",
    r".*confirm.*",
]

# 高亮按钮的CSS类名特征
HIGHLIGHT_CLASS_PATTERNS = [
    "primary", "confirm", "active", "highlight",
    "btn-primary", "btn-confirm", "ant-btn-primary",
    "el-button--primary", "weui-btn_primary"
]

class GuideKeywordLearner:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self.learning_log = LEARNING_LOG
        self.learning_log.parent.mkdir(parents=True, exist_ok=True)
        
        # 加载现有配置
        self.load_config()
        
        # 加载学习日志
        self.load_learning_log()
    
    def load_config(self):
        """加载配置文件"""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = {"guide_keywords": [], "close_selectors": []}
    
    def load_learning_log(self):
        """加载学习日志"""
        if self.learning_log.exists():
            with open(self.learning_log, 'r', encoding='utf-8') as f:
                self.log = json.load(f)
        else:
            self.log = {"discovered": {}, "auto_added": [], "last_update": None}
    
    def save_config(self):
        """保存配置文件"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
        print(f"✅ [Learner] 配置已更新: {self.config_file}")
    
    def save_learning_log(self):
        """保存学习日志"""
        self.log["last_update"] = datetime.now().isoformat()
        with open(self.learning_log, 'w', encoding='utf-8') as f:
            json.dump(self.log, f, ensure_ascii=False, indent=2)
    
    def is_suspicious_button(self, text: str, class_name: str = "") -> bool:
        """判断是否是可疑的引导按钮"""
        text_lower = text.lower().strip()
        
        # 检查文本模式
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        
        # 检查CSS类名
        if class_name:
            for pattern in HIGHLIGHT_CLASS_PATTERNS:
                if pattern in class_name.lower():
                    return True
        
        return False
    
    def record_discovery(self, text: str, platform: str, context: dict = None):
        """记录发现的新关键词"""
        if text in self.config["guide_keywords"]:
            return  # 已存在
        
        if text not in self.log["discovered"]:
            self.log["discovered"][text] = {
                "first_seen": datetime.now().isoformat(),
                "platforms": [],
                "count": 0,
                "context": []
            }
        
        # 更新统计
        self.log["discovered"][text]["count"] += 1
        if platform not in self.log["discovered"][text]["platforms"]:
            self.log["discovered"][text]["platforms"].append(platform)
        
        if context:
            self.log["discovered"][text]["context"].append({
                "time": datetime.now().isoformat(),
                "platform": platform,
                **context
            })
        
        self.save_learning_log()
        print(f"📝 [Learner] 发现新关键词: '{text}' (平台: {platform}, 出现次数: {self.log['discovered'][text]['count']})")
    
    def auto_add_keyword(self, text: str, threshold: int = 3):
        """自动添加高频关键词"""
        if text in self.config["guide_keywords"]:
            return False
        
        if text in self.log["discovered"]:
            count = self.log["discovered"][text]["count"]
            
            # 如果出现次数超过阈值，自动添加
            if count >= threshold:
                self.config["guide_keywords"].append(text)
                self.log["auto_added"].append({
                    "keyword": text,
                    "added_at": datetime.now().isoformat(),
                    "count": count,
                    "platforms": self.log["discovered"][text]["platforms"]
                })
                
                self.save_config()
                self.save_learning_log()
                
                print(f"✨ [Learner] 自动添加关键词: '{text}' (出现 {count} 次)")
                return True
        
        return False
    
    def get_suggestions(self, min_count: int = 2) -> List[dict]:
        """获取建议添加的关键词"""
        suggestions = []
        
        for text, info in self.log["discovered"].items():
            if text not in self.config["guide_keywords"] and info["count"] >= min_count:
                suggestions.append({
                    "keyword": text,
                    "count": info["count"],
                    "platforms": info["platforms"],
                    "first_seen": info["first_seen"]
                })
        
        # 按出现次数排序
        suggestions.sort(key=lambda x: x["count"], reverse=True)
        return suggestions
    
    def batch_add_keywords(self, keywords: List[str]):
        """批量添加关键词"""
        added = []
        for keyword in keywords:
            if keyword not in self.config["guide_keywords"]:
                self.config["guide_keywords"].append(keyword)
                added.append(keyword)
        
        if added:
            self.save_config()
            print(f"✅ [Learner] 批量添加了 {len(added)} 个关键词")
        
        return added

# 全局实例
learner = GuideKeywordLearner()

if __name__ == "__main__":
    print("="*50)
    print("引导关键词学习系统")
    print("="*50)
    
    # 显示当前配置
    print(f"\n当前关键词数量: {len(learner.config['guide_keywords'])}")
    print(f"已发现但未添加: {len(learner.log['discovered'])}")
    
    # 显示建议
    suggestions = learner.get_suggestions(min_count=2)
    if suggestions:
        print(f"\n📊 建议添加的关键词 (出现≥2次):")
        for s in suggestions[:10]:  # 只显示前10个
            print(f"  - '{s['keyword']}' (出现 {s['count']} 次, 平台: {', '.join(s['platforms'])})")
    
    # 自动添加高频关键词
    print(f"\n🤖 检查是否有可自动添加的关键词...")
    for text in list(learner.log["discovered"].keys()):
        learner.auto_add_keyword(text, threshold=3)
