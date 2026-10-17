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
        "lossless_music": 1,
        "up_close_reply": True,
    })
    assert payload["no_reprint"] == 1
    assert payload["is_only_self"] == 1
    assert payload["lossless_music"] == 1
    assert payload["dolby"] == 0
    assert payload["up_close_reply"] is True
    assert payload["up_selection_reply"] is False

