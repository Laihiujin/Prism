"""Global batch interval slots, independent of task dispatch."""
import random


def build_interval_offsets(assignments, mode, interval_seconds, random_offset=0, rng=None):
    if mode not in ("account_first", "video_first"):
        raise ValueError("无效的间隔方式")
    interval = int(interval_seconds)
    if interval <= 0:
        raise ValueError("开启间隔发布时，间隔必须大于0秒")
    rng = rng or random
    slots = sorted({(a.file_index, a.account_index if mode == "account_first" else 0) for a in assignments})
    offsets = {}
    elapsed = 0
    jitter = min(max(int(random_offset or 0), 0), interval - 1)
    for index, slot in enumerate(slots):
        if index:
            elapsed += interval + (rng.randint(-jitter, jitter) if jitter else 0)
        offsets[slot] = elapsed
    return {(a.file_index, a.account_index): offsets[(a.file_index, a.account_index if mode == "account_first" else 0)] for a in assignments}
