"""Project-level publishing skills consumed by Hermes Agent.

Publishing is split into one skill per platform (prism-publish-<platform>), so
editing one platform never touches another. Each platform's capability is also a
first-class tool registered in ``fastapi_app.services.tool_catalog`` (see the
``publish_tools`` package), which auto-exposes it as MCP tools, API endpoints,
and CLI subcommands.

These entries are guidance + the stable CLI/API/MCP contract, not a second
automation engine: Hermes must call the Prism CLI, backend APIs, or the MCP tool
catalog and keep every platform-specific field intact.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublishingSkill:
    name: str
    description: str


# 每平台发布 skill：改一个平台不影响其他平台。每平台的能力都以独立工具暴露
# （publish_video_to_<platform> / publish_note_to_<platform> / login_to_<platform> /
# check_account_<platform>），也走 `prism <platform> ...` CLI 与后端 API。
_PLATFORMS = (
    ("douyin", "抖音", True),
    ("kuaishou", "快手", True),
    ("xiaohongshu", "小红书", True),
    ("bilibili", "B站", False),
    ("channels", "视频号", False),
    ("baijiahao", "百家号", False),
    ("tiktok", "TikTok", False),
    ("youtube", "YouTube", False),
)

PUBLISHING_SKILLS = tuple(
    PublishingSkill(
        name=f"prism-publish-{platform}",
        description=(
            f"{display}发布：{ '视频+图文/笔记' if note else '视频'}；"
            f"工具 publish_video_to_{platform}"
            + (f" / publish_note_to_{platform}" if note else "")
            + f" / login_to_{platform} / check_account_{platform}（MCP + API + CLI）"
        ),
    )
    for platform, display, note in _PLATFORMS
)


def render_publishing_skills() -> str:
    lines = [
        "Prism publishing skills (one per platform):",
        "- Read docs/agent-bootstrap.md before first-run setup.",
        "- Use the project CLI executable: prism. Do not use upstream sau or historical examples.",
        "- A publish task must preserve the exact command contract for its target platform.",
        "- For login QR images, display the generated image to the user instead of only returning a path.",
        "- Bilibili QR login must run in the user's local interactive terminal.",
    ]
    for skill in PUBLISHING_SKILLS:
        lines.append(f"- {skill.name}: {skill.description}")
    lines.append("- 也可用后端批量发布 API: POST /api/v1/publish/batch（统一标题/描述/话题/每平台专属配置）。")
    return "\n".join(lines)
