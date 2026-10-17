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
    })
    assert payload["no_reprint"] == 1
    assert payload["is_only_self"] == 1
    assert payload["lossless_music"] == 1
    assert payload["dolby"] == 0


def test_app_only_switches_build_an_app_cli_command(tmp_path):
    import json
    import pytest
    from uploader.bilibili_uploader.app_submit import app_cookie_file, build_upload_command, needs_app_submit

    account = tmp_path / "bilibili_1.json"
    account.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="biliup -u"):
        app_cookie_file(account)
    (tmp_path / "bilibili_1.biliup.json").write_text(json.dumps({"token_info": {"access_token": "t"}}), encoding="utf-8")
    app_file = app_cookie_file(account)

    extra = {"copyright": 1, "is_only_self": 1, "up_close_reply": True, "up_close_danmu": True}
    assert needs_app_submit(extra) and not needs_app_submit({"is_only_self": 1})
    uploader = BilibiliUploader({}, Path("video.mp4"), "title", "desc", 160, ["a", "b"], None, extra=extra)
    command = build_upload_command(app_file, [Path("video.mp4")], uploader.data)
    assert command[:5] == ["-u", str(app_file), "upload", "--submit", "app"]
    assert "--up-close-reply" in command and "--up-close-danmu" in command
    assert "--up-selection-reply" not in command
    assert command[command.index("--is-only-self") + 1] == "1"
    assert command[command.index("--tag") + 1] == "a,b"
