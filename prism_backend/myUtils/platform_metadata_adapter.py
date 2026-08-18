"""
平台特定元数据适配器 - Python版本
用于后端根据不同平台格式化元数据
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class PlatformLayout(Enum):
    """平台布局类型"""
    SEPARATE = "separate"  # 分离字段 (B站)
    TITLE_DESCRIPTION = "title_description"  # 标题+描述 (抖音、小红书)
    COMBINED = "combined"  # 合并字段 (快手)
    TITLE_COMBINED = "title_combined"  # 描述合并 (视频号)


@dataclass
class PlatformFieldConfig:
    """平台字段配置"""
    name: str
    code: int
    layout: PlatformLayout
    title_enabled: bool = False
    title_max_length: Optional[int] = None
    description_enabled: bool = False
    description_max_length: Optional[int] = None
    description_supports_hashtags: bool = False
    tags_enabled: bool = False
    tags_max_count: Optional[int] = None
    combined_enabled: bool = False


# 平台配置字典
PLATFORM_CONFIGS: Dict[int, PlatformFieldConfig] = {
    # 抖音：标题 + 简介（简介支持话题标签）
    3: PlatformFieldConfig(
        name="抖音",
        code=3,
        layout=PlatformLayout.TITLE_DESCRIPTION,
        title_enabled=True,
        title_max_length=30,
        description_enabled=True,
        description_max_length=2000,
        description_supports_hashtags=True,
        tags_enabled=False
    ),

    # 快手：单一输入框（包含标题+描述+标签）
    4: PlatformFieldConfig(
        name="快手",
        code=4,
        layout=PlatformLayout.COMBINED,
        combined_enabled=True
    ),

    # 小红书：标题 + 描述（描述支持换行和话题）
    1: PlatformFieldConfig(
        name="小红书",
        code=1,
        layout=PlatformLayout.TITLE_DESCRIPTION,
        title_enabled=True,
        title_max_length=20,
        description_enabled=True,
        description_max_length=1000,
        description_supports_hashtags=True,
        tags_enabled=False
    ),

    # B站：标题 + 简介 + 独立标签
    5: PlatformFieldConfig(
        name="B站",
        code=5,
        layout=PlatformLayout.SEPARATE,
        title_enabled=True,
        title_max_length=80,
        description_enabled=True,
        description_max_length=2000,
        description_supports_hashtags=False,
        tags_enabled=True,
        tags_max_count=12
    ),

    # 视频号：单一描述框（描述+标签）
    2: PlatformFieldConfig(
        name="视频号",
        code=2,
        layout=PlatformLayout.TITLE_COMBINED,
        description_enabled=True,
        description_supports_hashtags=True
    )
}


class PlatformMetadataAdapter:
    """平台元数据适配器"""

    @staticmethod
    def format(
        platform_code: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        格式化元数据为平台特定格式

        Args:
            platform_code: 平台代码
            title: 标题
            description: 描述
            tags: 标签列表

        Returns:
            格式化后的元数据字典
        """
        config = PLATFORM_CONFIGS.get(platform_code)
        if not config:
            # 未知平台，返回原始数据
            return {
                "title": title or "",
                "description": description or "",
                "tags": tags or []
            }

        title = title or ""
        description = description or ""
        tags = tags or []

        if config.layout == PlatformLayout.SEPARATE:
            # B站：分离的标题、描述、标签
            return {
                "title": PlatformMetadataAdapter._truncate(title, config.title_max_length),
                "description": description,
                "tags": tags[:config.tags_max_count] if config.tags_max_count else tags
            }

        elif config.layout == PlatformLayout.TITLE_DESCRIPTION:
            # 抖音：话题在 UI 中单独输入，避免把 tags 拼进 description 造成重复
            if platform_code == 3:
                return {
                    "title": PlatformMetadataAdapter._truncate(title, config.title_max_length),
                    "description": description.strip(),
                }

            # 小红书：标题 + 描述（描述中包含话题）
            desc_with_tags = PlatformMetadataAdapter._merge_description_and_tags(description, tags)
            return {
                "title": PlatformMetadataAdapter._truncate(title, config.title_max_length),
                "description": desc_with_tags,
            }

        elif config.layout == PlatformLayout.COMBINED:
            # 快手：全部合并到一个字段
            combined = PlatformMetadataAdapter._combine_all(title, description, tags)
            return {
                "description": combined  # 使用description字段传递合并内容
            }

        elif config.layout == PlatformLayout.TITLE_COMBINED:
            # 视频号：描述+标签合并（无独立标题）
            desc_with_tags = PlatformMetadataAdapter._merge_description_and_tags(
                description, tags
            )
            return {
                "description": desc_with_tags
            }

        # 默认返回原始数据
        return {
            "title": title,
            "description": description,
            "tags": tags
        }

    @staticmethod
    def _merge_description_and_tags(description: str, tags: List[str]) -> str:
        """合并描述和标签"""
        result = description.strip()

        if tags:
            # 添加 # 符号
            hashtags_text = ' '.join([
                tag if tag.startswith('#') else f'#{tag}'
                for tag in tags
            ])

            if not result:
                result = hashtags_text
            else:
                # 检查是否已包含这些标签
                if hashtags_text not in result:
                    result = f"{result}\n\n{hashtags_text}"

        return result

    @staticmethod
    def _combine_all(title: str, description: str, tags: List[str]) -> str:
        """合并标题、描述和标签为单一字段（快手用）"""
        parts = []

        if title and title.strip():
            parts.append(title.strip())

        if description and description.strip():
            parts.append(description.strip())

        if tags:
            hashtags_text = ' '.join([
                tag if tag.startswith('#') else f'#{tag}'
                for tag in tags
            ])
            parts.append(hashtags_text)

        return '\n\n'.join(parts)

    @staticmethod
    def _truncate(text: str, max_length: Optional[int]) -> str:
        """截断文本到指定长度"""
        if not max_length or len(text) <= max_length:
            return text
        return text[:max_length]


def format_metadata_for_platform(
    platform_code: int,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    便捷函数：格式化元数据字典

    Args:
        platform_code: 平台代码
        metadata: 包含 title, description, topics 的字典

    Returns:
        格式化后的元数据
    """
    return PlatformMetadataAdapter.format(
        platform_code=platform_code,
        title=metadata.get('title'),
        description=metadata.get('description'),
        tags=metadata.get('topics') or metadata.get('tags')
    )


# 使用示例
if __name__ == "__main__":
    # 测试数据
    test_metadata = {
        "title": "精彩瞬间｜这才是生活该有的样子",
        "description": "分享日常生活的美好瞬间",
        "tags": ["生活记录", "vlog", "日常分享"]
    }

    print("=" * 60)
    print("原始元数据:")
    print(test_metadata)
    print("\n" + "=" * 60)

    # 测试各平台
    platforms = [
        (3, "抖音"),
        (4, "快手"),
        (1, "小红书"),
        (5, "B站"),
        (2, "视频号")
    ]

    for code, name in platforms:
        formatted = format_metadata_for_platform(code, test_metadata)
        print(f"\n{name} (代码: {code}):")
        print("-" * 60)
        for key, value in formatted.items():
            if isinstance(value, list):
                print(f"  {key}: {value}")
            else:
                print(f"  {key}:")
                for line in str(value).split('\n'):
                    print(f"    {line}")
        print()
