from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import CapturedExchange


SENSITIVE_HEADERS = {
    "authorization", "cookie", "set-cookie", "x-csrf-token", "x-xsrf-token",
    "x-token", "x-api-key", "proxy-authorization",
}
SENSITIVE_KEYS = re.compile(
    r"(^|_)(token|ticket|secret|password|passwd|cookie|session|csrf|xsrf|sign|signature|device_id|did|uid|user_id)(_|$)",
    re.IGNORECASE,
)


def _fingerprint(value: Any) -> str:
    digest = hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"<redacted:{digest}>"


def sanitize_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        result[str(key)] = _fingerprint(value) if str(key).lower() in SENSITIVE_HEADERS else str(value)
    return result


def sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _fingerprint(item) if SENSITIVE_KEYS.search(str(key)) else sanitize_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_value(item) for item in value)
    return value


def sanitize_url(url: str) -> str:
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query.append((key, _fingerprint(value) if SENSITIVE_KEYS.search(key) else value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def sanitize_exchange(exchange: CapturedExchange) -> CapturedExchange:
    return replace(
        exchange,
        url=sanitize_url(exchange.url),
        request_headers=sanitize_headers(exchange.request_headers),
        request_shape=sanitize_value(exchange.request_shape),
        response_headers=sanitize_headers(exchange.response_headers),
        response_shape=sanitize_value(exchange.response_shape),
    )
