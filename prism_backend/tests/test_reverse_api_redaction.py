from prism_backend.reverse_api.models import CapturedExchange
from prism_backend.reverse_api.redaction import sanitize_exchange


def test_sanitize_exchange_removes_replayable_secrets():
    captured = CapturedExchange(
        platform="example",
        operation="publish",
        method="POST",
        url="https://creator.example.test/publish?csrf_token=abc&draft=1",
        request_headers={"Cookie": "sid=secret", "Content-Type": "application/json"},
        request_shape={"title": "demo", "device_id": "device-secret", "nested": {"token": "secret"}},
        response_headers={"Set-Cookie": "sid=new-secret"},
        response_shape={"user_id": "42", "status": "accepted"},
    )

    sanitized = sanitize_exchange(captured)
    rendered = repr(sanitized)

    assert "sid=secret" not in rendered
    assert "device-secret" not in rendered
    assert "new-secret" not in rendered
    assert "csrf_token=abc" not in rendered
    assert sanitized.request_shape["title"] == "demo"
    assert sanitized.response_shape["status"] == "accepted"


def test_fragment_is_dropped_from_capture_url():
    captured = CapturedExchange(
        platform="example", operation="status", method="GET",
        url="https://creator.example.test/status?id=public#private-fragment",
    )
    assert "private-fragment" not in sanitize_exchange(captured).url
