from prism_backend.reverse_api.login.models import QrLoginState
from prism_backend.reverse_api.login.registry import LOGIN_PROTOCOLS


def test_target_creator_platforms_are_registered():
    assert set(LOGIN_PROTOCOLS) == {"douyin", "kuaishou", "xiaohongshu", "channels"}


def test_douyin_capture_contains_only_stable_protocol_metadata():
    protocol = LOGIN_PROTOCOLS["douyin"]
    rendered = repr(protocol)
    assert protocol.create_path == "/passport/web/get_qrcode/"
    assert protocol.poll_path == "/passport/web/check_qrconnect/"
    assert "msToken" not in rendered
    assert "sign=" not in rendered


def test_qr_state_machine_has_human_scan_transition():
    assert QrLoginState.WAITING.value == "waiting"
    assert QrLoginState.SCANNED.value == "scanned"
    assert QrLoginState.CONFIRMED.value == "confirmed"


def test_douyin_success_requires_route_and_creator_ui():
    from prism_backend.reverse_api.login.douyin import SUCCESS_EVIDENCE

    assert "/creator-micro/home" in SUCCESS_EVIDENCE["route_prefixes"]
    assert "作品发布" in SUCCESS_EVIDENCE["required_ui_any"]
    assert "扫码登录" in SUCCESS_EVIDENCE["forbidden_ui_any"]
    assert SUCCESS_EVIDENCE["verified"] is True
