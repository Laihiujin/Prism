from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProtocolProbe:
    platform: str
    creator_hosts: tuple[str, ...]
    operations: tuple[str, ...] = ("session_check", "upload_init", "upload_part", "publish", "status")


PROBES = {
    "douyin": ProtocolProbe("douyin", ("creator.douyin.com",)),
    "xiaohongshu": ProtocolProbe("xiaohongshu", ("creator.xiaohongshu.com",)),
    "kuaishou": ProtocolProbe("kuaishou", ("cp.kuaishou.com",)),
    "channels": ProtocolProbe("channels", ("channels.weixin.qq.com",)),
    "bilibili": ProtocolProbe("bilibili", ("member.bilibili.com",)),
}
