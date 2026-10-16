from dataclasses import asdict
from pathlib import Path

from uploader.bilibili_uploader.main import BilibiliUploader, STUDIO_FLAG_FIELDS


def _payload(extra=None):
    uploader = BilibiliUploader({}, Path("video.mp4"), "title", "desc", 160, ["a"], None, extra=extra)
    return asdict(uploader.data)


def test_studio_flags_default_off_in_submit_payload():
    payload = _payload()
    for name in STUDIO_FLAG_FIELDS:
        assert name in payload
        assert not payload[name]


def test_studio_flags_reach_submit_payload():
    payload = _payload({
        "copyright": 1,
        "no_reprint": 1,
        "is_only_self": "1",
        "up_close_danmu": True,
        "lossless_music": 1,
    })
    assert payload["no_reprint"] == 1
    assert payload["is_only_self"] == 1
    assert payload["up_close_danmu"] is True
    assert payload["lossless_music"] == 1
    assert payload["up_close_reply"] is False
