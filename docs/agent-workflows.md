# Agent 工作流接口

项目新能力统一登记在 `fastapi_app/services/agent_workflow_tools.py`。
同一工具同时出现在 MCP、CLI、`/api/v1/tool-catalog` 与 Hermes 能力清单中。
工具调用连接正在运行的后端，因此封面任务和人工验证状态与网页一致。

## CLI

```sh
python prism_cli.py tool list
python prism_cli.py tool invoke generate_cover --json '{"file_id":3,"platform_name":"抖音","aspect_ratio":"3:4","prompt":"现代电影风格"}'
python prism_cli.py tool invoke get_cover_job --json '{"job_id":"生成返回的job_id"}'
python prism_cli.py tool invoke list_publish_verifications
python prism_cli.py tool invoke resend_publish_verification --json '{"account_id":"待验证事件中的account_id"}'
python prism_cli.py tool invoke submit_publish_verification --json-file -
```

最后一个命令从标准输入读取 JSON，格式为 `{"account_id":"...","code":"用户提供的验证码"}`。
也可以用 `--json-file parameters.json`。不要将验证码写进命令行历史。
失败返回非零退出码和 `ok:false`。`tool list` 包含完整 inputSchema。
可用 `PRISM_BACKEND_URL` 指定运行中的后端地址；默认读取项目运行配置。

## MCP

启动 `python prism_cli.py mcp`，使用 stdio。
`tools/list` 返回同样的工具及参数，`tools/call` 使用工具名和 arguments。
失败通过 `isError:true` 返回。

## 工具

| 工作流 | 工具 |
| --- | --- |
| 封面 | generate_cover、get_cover_job、list_material_covers、select_material_cover、adapt_material_cover |
| 发布人工验证 | list_publish_verifications、submit_publish_verification、resend_publish_verification |
| 登录 | start_login_qrcode、get_login_status、start_login_sms、login_verification_action |
| 远程登录画面 | get_login_browser_frame、login_browser_pointer |
| 浏览器配置 | get_browser_runtime、get_platform_browser_preferences、set_platform_browser_preferences、get_browser_headless、set_browser_headless |

验证码必须由用户提供，安全挑战由用户完成。账号和任务标识使用返回的事件值。
扫码状态为 scanned 时等待用户确认；confirmed 表示账号同步完成。
封面生成返回 job_id 后轮询 get_cover_job，成功后可选用 list_material_covers/select_material_cover。

## 新功能要求

新增可调用业务能力时，必须登记共用工具目录和参数 schema，补充文档及发现/调用测试。
仅增加 HTTP 路由不代表完成 Agent 接入。
