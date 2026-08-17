"""Project-level publishing skills consumed by Hermes Agent.

These are instructions and stable CLI contracts, not a second automation engine.
Hermes must call the Prism CLI or backend APIs and keep every platform-specific
field intact.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PublishingSkill:
    name: str
    platforms: tuple[str, ...]
    commands: tuple[str, ...]
    notes: str


PUBLISHING_SKILLS = (
    PublishingSkill(
        name="prism-video-publish",
        platforms=("douyin", "kuaishou", "xiaohongshu", "bilibili", "channels", "baijiahao", "tiktok", "youtube"),
        commands=("login", "check", "upload-video"),
        notes="Use the exact platform command and only its documented flags. Never invent or forward unsupported metadata.",
    ),
    PublishingSkill(
        name="prism-image-post-publish",
        platforms=("douyin", "kuaishou", "xiaohongshu"),
        commands=("upload-note",),
        notes="Image posts require --images and --title; use --note or --notef. Scheduling is platform-native.",
    ),
    PublishingSkill(
        name="prism-agent-bootstrap",
        platforms=("bilibili", "douyin", "kuaishou", "xiaohongshu"),
        commands=("prism --help", "prism <platform> --help", "prism <platform> check --account <name>"),
        notes="Read docs/agent-bootstrap.md before installation, login, or a first real publication.",
    ),
)


def render_publishing_skills() -> str:
    lines = [
        "Prism publishing skills:",
        "- Read docs/agent-bootstrap.md before first-run setup.",
        "- Use the project CLI executable: prism. Do not use upstream sau or historical examples.",
        "- A publish task must preserve the exact command contract for its target platform.",
        "- For login QR images, display the generated image to the user instead of only returning a path.",
        "- Bilibili QR login must run in the user's local interactive terminal.",
    ]
    for skill in PUBLISHING_SKILLS:
        lines.append(
            f"- {skill.name}: platforms={', '.join(skill.platforms)}; "
            f"commands={', '.join(skill.commands)}. {skill.notes}"
        )
    return "\n".join(lines)

