# TikHub API 端点自更新工具

`prism_backend/scripts/update_tikhub_api.py` 会从 TikHub 官网的 OpenAPI 规范
（`https://api.tikhub.io/openapi.json`）抓取当前全部接口，按「语义键」匹配出本项目
使用的端点（快手 / 小红书 / 视频号 / 健康检查 / 用户信息等），并把最新路径与方法写入
`prism_backend/myUtils/tikhub_endpoints.json`。

当 TikHub 官方升级接口（例如 v1 -> v2 -> v3 -> v5/v6）后，**重新运行本工具即可自动适配**，
无需手改 `tikhub_client.py`。

## 用法

```bash
# 默认 https://api.tikhub.io
python prism_backend/scripts/update_tikhub_api.py

# 指定官网地址
python prism_backend/scripts/update_tikhub_api.py --base-url https://api.tikhub.io

# 只打印匹配结果，不写文件
python prism_backend/scripts/update_tikhub_api.py --dry-run

# 输出 JSON（供脚本/CI 调用）
python prism_backend/scripts/update_tikhub_api.py --json
```

## 工作原理

1. 抓取官网 `openapi.json`（V5.3.2 等版本号见 spec 的 info.version）。
2. 对每个语义键（如 `kuaishou_user_posts`、`xhs_user_notes`、`channels_user_videos`）：
   - 按关键词分组匹配候选路径（组内 OR、组间 AND）；
   - 排除无关端点（如 comment / search / detail 等）；
   - 按 **方法偏好 > 版本号（v6 > v5 > v3 > v2 > v1）> 关键词命中数** 排序取最优。
3. 将 OpenAPI 中实际的参数名（如 `userId` / `last_cursor`）映射到客户端的语义参数
   （如 `user_id` / `cursor`），写入 JSON 配置。
4. `myUtils/tikhub_client.py` 启动时读取该 JSON；配置缺失或语义键未命中时，
   自动回退到代码内置的默认端点。

## 匹配规则

规则集中在 `update_tikhub_api.py` 顶部的 `ENDPOINT_RULES`：

```python
"xhs_user_notes": {
    "match": [["xiaohongshu"], ["fetch_home_notes", "get_user_posted_notes", ...]],
    "exclude": ["info", "detail", "comment", ...],
    "method": "GET",
    "params": {"user_id": ["user_id", "userId"], "cursor": ["cursor", "last_cursor", "lastCursor"]},
},
```

- `match`：每组至少命中一项（组间 AND，组内 OR）。
- `exclude`：命中即排除。
- `method`：首选方法（实际以 OpenAPI 中存在的为准）。
- `params`：语义参数 -> 官方参数别名表。

新增一个端点时，在 `ENDPOINT_RULES` 里加一条规则即可。

## 常见输出

```
OK   kuaishou_user_posts        GET  /api/v1/kuaishou/app/fetch_user_post_v2
OK   xhs_user_notes             GET  /api/v1/xiaohongshu/app_v2/get_user_posted_notes
OK   channels_user_videos       POST /api/v1/wechat_channels/v2/fetch_user_videos
MISS xhs_note_id_and_xsec_token （未找到匹配端点，将回退到代码内置默认值）
```

`MISS` 表示官网已移除该端点（或改名），客户端会回退到内置默认路径，
通常意味着该功能已不可用，需要人工确认是否更新规则。

## 与采集管道的关系

- `tikhub_client.py` 的所有请求都走 `_request(语义键, 参数)`，
  路径/方法/参数名全部来自生成的 `tikhub_endpoints.json`。
- 快手 / 小红书 / 视频号采集：TikHub 优先，失败（403/402/异常）自动回退
  到 Cookie / Playwright 浏览器采集（免费），并写回 analytics 库。
- 免费可用的 TikHub 端点（如快手热榜 `kuaishou_hot_list`）无需充值即可使用；
  付费端点充值后自动生效，无需改代码。
