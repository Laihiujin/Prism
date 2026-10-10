"""Probe candidates independently while retaining HTTPS certificate verification."""
import time
import requests


def probe_upload_lines(session):
    response = session.get("https://member.bilibili.com/preupload?r=probe", timeout=10)
    response.raise_for_status()
    payload = response.json()
    method = "get" if payload.get("probe", {}).get("get") else "post"
    data = None if method == "get" else bytes(104857)
    candidates = []
    for line in payload.get("lines", []):
        if line.get("os") != "upos":
            continue
        url = line.get("probe_url", "")
        url = "https:" + url if url.startswith("//") else url
        if not url.startswith("https://"):
            continue
        started = time.perf_counter()
        try:
            result = session.request(method, url, data=data, timeout=10)
            if result.status_code == 200:
                candidates.append({**line, "cost": time.perf_counter() - started})
        except requests.RequestException:
            continue
    if not candidates:
        raise RuntimeError("B站上传线路均不可用，证书或网络检查失败，请稍后重试")
    return min(candidates, key=lambda line: line["cost"])
