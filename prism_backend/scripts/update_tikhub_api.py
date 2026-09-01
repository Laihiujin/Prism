#!/usr/bin/env python3
"""
TikHub API 端点自动更新工具（自我迭代）

从 TikHub 官网 OpenAPI 规范（https://api.tikhub.io/openapi.json）抓取当前全部接口，
按“语义键”匹配出本项目使用的端点（快手/小红书/视频号/健康检查/用户信息等），
把最新路径与方法写入 `myUtils/tikhub_endpoints.json`。

当 TikHub 官方升级接口（例如 v1 -> v2 -> v3 -> v5/v6）后，重新运行本工具即可自动适配，
无需手改 tikhub_client.py。

用法：
    python scripts/update_tikhub_api.py                 # 默认 https://api.tikhub.io
    python scripts/update_tikhub_api.py --base-url https://api.tikhub.io
    python scripts/update_tikhub_api.py --dry-run       # 只打印将要写入的内容，不落盘
    python scripts/update_tikhub_api.py --json          # 输出 JSON（供脚本调用）

说明：
- 每个语义键的匹配规则见 ENDPOINT_RULES：按关键词过滤候选路径，
  再按“版本号降序 + 方法偏好 + 关键词命中数”排序，取最优。
- 参数映射：语义参数名（如 user_id / cursor）会按别名表匹配到 OpenAPI 中
  实际使用的参数名（如 userId / last_cursor），保证请求参数名始终正确。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

DEFAULT_BASE_URL = "https://api.tikhub.io"
SPEC_PATH = "/openapi.json"

# 本项目需要使用的语义端点
# key: {
#   "match": [[组1替代项...], [组2替代项...], ...]   # 每组至少命中一项（AND 组间，OR 组内）
#   "exclude": [...],
#   "method": "GET|POST",
#   "params": {语义参数: [别名...]},
# }
ENDPOINT_RULES: Dict[str, Dict[str, Any]] = {
    "kuaishou_user_posts": {
        "match": [["kuaishou"], ["fetch_user_post"]],
        "exclude": ["comment", "info", "hot", "live", "collect", "detail"],
        "method": "GET",
        "params": {"user_id": ["user_id", "userId"], "pcursor": ["pcursor", "cursor", "next_cursor"]},
    },
    "kuaishou_user_info": {
        "match": [["kuaishou"], ["fetch_user_info"]],
        "exclude": [],
        "method": "GET",
        "params": {"user_id": ["user_id", "userId"]},
    },
    "kuaishou_one_video": {
        "match": [["kuaishou"], ["fetch_one_video"]],
        "exclude": ["by_url", "comment", "sub_comment"],
        "method": "GET",
        "params": {"share_text": ["share_text", "shareText", "photo_id"]},
    },
    "kuaishou_one_video_by_url": {
        "match": [["kuaishou"], ["fetch_one_video_by_url"]],
        "exclude": [],
        "method": "GET",
        "params": {"url": ["url"]},
    },
    "kuaishou_hot_list": {
        "match": [["kuaishou"], ["fetch_kuaishou_hot_list"]],
        "exclude": [],
        "method": "GET",
        "params": {},
    },
    "xhs_user_notes": {
        "match": [["xiaohongshu"], ["fetch_home_notes", "get_user_posted_notes", "fetch_user_posted_notes", "fetch_user_notes", "get_blogger_notes"]],
        "exclude": ["info", "detail", "comment", "search", "faved", "topic", "product", "rate", "components", "tag"],
        "method": "GET",
        "params": {"user_id": ["user_id", "userId"], "cursor": ["cursor", "last_cursor", "lastCursor"]},
    },
    "xhs_user_info": {
        "match": [["xiaohongshu"], ["fetch_user_info", "get_user_info"]],
        "exclude": ["notes", "faved"],
        "method": "GET",
        "params": {"user_id": ["user_id", "userId"]},
    },
    "xhs_note_id_and_xsec_token": {
        "match": [["xiaohongshu"], ["get_note_id_and_xsec_token"]],
        "exclude": [],
        "method": "GET",
        "params": {"url": ["url"]},
    },
    "channels_user_videos": {
        "match": [["wechat_channels"], ["fetch_user_videos", "fetch_home_page", "fetch_home"]],
        "exclude": ["detail", "comment", "info", "search", "collection"],
        "method": "POST",
        "params": {"username": ["username", "user_name"], "last_buffer": ["last_buffer", "lastBuffer"]},
    },
    "channels_channel_info": {
        "match": [["wechat_channels"], ["fetch_channel_info"]],
        "exclude": [],
        "method": "POST",
        "params": {"username": ["username", "user_name"]},
    },
    "channels_video_detail": {
        "match": [["wechat_channels"], ["fetch_video_detail"]],
        "exclude": [],
        "method": "POST",
        "params": {"object_id": ["object_id", "id"], "export_id": ["export_id", "exportId"]},
    },
    "health_check": {
        "match": [["health"], ["check"]],
        "exclude": ["deep"],
        "method": "GET",
        "params": {},
    },
    "tikhub_user_info": {
        "match": [["tikhub", "user"], ["get_user_info"]],
        "exclude": [],
        "method": "GET",
        "params": {},
    },
}

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "myUtils" / "tikhub_endpoints.json"


def _norm_path(path: str) -> str:
    return path.rstrip("/").lower()


def _version_of(path: str) -> int:
    """从路径中提取 API 版本号：v6 > v5 > v3 > v2 > v1 > 0。

    注意先去掉 /api/v1 前缀，避免把 api/v1 误判为 v1；
    例如 /api/v1/kuaishou/app/v5/fetch_user_post -> 5。
    """
    p = path.lower()
    # 去掉全局 /api/vN 前缀（N 可为任意数字，通常为 1）
    p = re.sub(r"^/api/v\d+", "", p)
    match = re.search(r"/v(\d+)/", p)
    return int(match.group(1)) if match else 0


def _method_rank(method: str, preferred: str) -> int:
    return 0 if method.upper() == preferred.upper() else 1


def _find_param_name(spec_params: List[str], aliases: List[str]) -> Optional[str]:
    """在 OpenAPI 参数名列表中，按别名表找实际参数名"""
    lowered = [p.lower() for p in spec_params]
    for alias in aliases:
        alias_l = alias.lower()
        for idx, name in enumerate(lowered):
            if name == alias_l:
                return spec_params[idx]
    for alias in aliases:
        alias_l = alias.lower()
        for idx, name in enumerate(lowered):
            if alias_l in name or name in alias_l:
                return spec_params[idx]
    return None


def _match_groups(path: str, groups: List[List[str]]) -> Tuple[bool, int]:
    """每组至少命中一项（AND 组间，OR 组内），返回 (是否匹配, 命中数)"""
    hits = 0
    path_l = path.lower()
    for group in groups:
        group_hit = False
        for kw in group:
            if kw.lower() in path_l:
                hits += 1
                group_hit = True
        if not group_hit:
            return False, hits
    return True, hits


def _collect_candidates(
    spec: Dict[str, Any],
    rule: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """从 OpenAPI paths 中按规则收集候选端点"""
    groups = rule["match"]
    excludes = rule["exclude"]
    candidates: List[Dict[str, Any]] = []

    for path, methods in (spec.get("paths") or {}).items():
        path_l = path.lower()
        matched, score = _match_groups(path_l, groups)
        if not matched:
            continue
        if any(ex.lower() in path_l for ex in excludes):
            continue
        for method, op in methods.items():
            if not isinstance(op, dict):
                continue
            if method.lower() not in ("get", "post", "put", "delete"):
                continue

            # 收集参数：query/path 参数 + body 字段
            spec_params: List[str] = []
            for pr in op.get("parameters") or []:
                name = pr.get("name")
                if name:
                    spec_params.append(str(name))
            rb = op.get("requestBody") or {}
            for content in (rb.get("content") or {}).values():
                schema = content.get("schema") or {}
                props = schema.get("properties") or {}
                for pname in props:
                    spec_params.append(str(pname))

            candidates.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "spec_params": spec_params,
                    "version": _version_of(path),
                    "score": score,
                }
            )
    return candidates


def _best_candidate(
    candidates: List[Dict[str, Any]],
    rule: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """按 方法偏好 > 版本号 > 关键词命中 排序取最优"""
    if not candidates:
        return None
    preferred = rule["method"]
    candidates.sort(
        key=lambda c: (
            _method_rank(c["method"], preferred),
            -c["version"],
            -c["score"],
        )
    )
    return candidates[0]


def build_endpoints(spec: Dict[str, Any], base_url: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """根据 OpenAPI spec 生成端点配置。返回 (配置, 匹配报告)"""
    endpoints: Dict[str, Any] = {}
    report: List[Dict[str, Any]] = []

    for key, rule in ENDPOINT_RULES.items():
        candidates = _collect_candidates(spec, rule)
        best = _best_candidate(candidates, rule)
        if not best:
            report.append({"key": key, "status": "missing", "path": None})
            continue

        param_map: Dict[str, str] = {}
        for semantic, aliases in rule["params"].items():
            actual = _find_param_name(best["spec_params"], aliases)
            if actual:
                param_map[semantic] = actual
            else:
                # 参数不存在时，若该参数可选则忽略；否则仍按语义名透传
                param_map[semantic] = semantic

        endpoints[key] = {
            "path": best["path"],
            "method": best["method"],
            "params": param_map,
        }
        report.append({"key": key, "status": "ok", "path": best["path"], "method": best["method"]})

    config = {
        "meta": {
            "base_url": base_url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "spec_paths": len(spec.get("paths") or {}),
        },
        "endpoints": endpoints,
    }
    return config, report


def fetch_spec(base_url: str, timeout: int = 60) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}{SPEC_PATH}"
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description="TikHub API 端点自动更新工具")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="TikHub 官网地址")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    parser.add_argument("--json", dest="as_json", action="store_true", help="输出 JSON")
    parser.add_argument("--timeout", type=int, default=60, help="抓取超时（秒）")
    args = parser.parse_args()

    try:
        spec = fetch_spec(args.base_url, args.timeout)
    except Exception as exc:  # noqa: BLE001
        print(f"[update_tikhub_api] 抓取 OpenAPI 失败: {exc}", file=sys.stderr)
        return 1

    config, report = build_endpoints(spec, args.base_url)

    if args.as_json:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    # 打印报告
    ok = [r for r in report if r["status"] == "ok"]
    missing = [r for r in report if r["status"] == "missing"]
    print(f"[update_tikhub_api] OpenAPI 路径总数: {config['meta']['spec_paths']}")
    for r in ok:
        print(f"  OK   {r['key']:26s} {r['method']:4s} {r['path']}")
    for r in missing:
        print(f"  MISS {r['key']:26s} （未找到匹配端点，将回退到代码内置默认值）")

    if args.dry_run:
        print("[update_tikhub_api] dry-run，未写入文件")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[update_tikhub_api] 已写入 {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
