# AGENT.md

## AI Agent 上下文

- 项目布局与调用指南（目录结构、全部后端 API 路由、`prism` CLI 用法、Hermes MCP 工具清单、服务端口）维护在唯一源文件：`docs/hermes-skills/prism-project-layout/SKILL.md`。
- 内置 HermesAgent 每次会话默认预加载该技能（`--skills prism-project-layout`，见 `prism_backend/fastapi_app/agent/hermes_agent.py` 的 `DEFAULT_PRELOAD_SKILL`），把它作为整个会话的活跃指引。
- 更新方式：只编辑 `docs/hermes-skills/prism-project-layout/SKILL.md`；Hermes 会话准备时由 `hermes_config.py::sync_prism_project_skill()` 自动同步到 `tools/hermes-home/skills/software-development/prism-project-layout/` 与 `runtime-data/app/hermes-home/skills/software-development/prism-project-layout/`（后两者在 `.gitignore` 内，不入库）。
- 其他 AI（Claude Code、Codex 等）如需相同布局上下文，直接读上述 `docs/` 源文件即可。

## Repo Hygiene

- GitHub only carries source code, docs, sanitized examples, and build scripts.
- Never commit or push real account data, cookies, browser profiles, fingerprints, proxy/IP pool data, logs, local databases, or other runtime artifacts.
- Do not include raw account identifiers, cookie values, proxy IPs, or local-only paths in commit messages, PR descriptions, screenshots, or copied debug output.

## Interface Border Rule

- The interface must not use a border that is pure white at 100% opacity (e.g. `border-white`).
- Border / divider colors must use the themed 17% border token via `border-border` (resolves to `hsl(0 0% 17%)`), never a fully opaque white.
- The same applies to hover states (`hover:border-border`) and dashed / translucent variants — keep them at the 17% theme token instead of pure white.

## Local-Only Data

The following are local runtime data and must stay out of GitHub:

- `.env`
- `prism_backend/cookiesFile/`
- `config/cookiesFile/`
- `prism_backend/browser_profiles/`
- `config/browser_profiles/`
- `prism_backend/fingerprints/`
- `prism_backend/data/ip_pool*.json`
- `prism_backend/data/account_stats*.json`
- `prism_backend/data/campaigns.json`
- `prism_backend/data/published_works.json`
- `prism_backend/logs/`
- `logs/`
- `tmp-runtime-data/`
- `data/analytics/`
- `data/crawler_output/`
- `data/videos/`
- `*.db`
- `*.sqlite*`
- `dump.rdb`

## Push Rules

- Before commit or push, run `git status --short`.
- If a runtime or sensitive file appears in Git tracking, remove it from the index with `git rm --cached <path>` and add or fix the ignore rule.
- If an example file is required for documentation or onboarding, create a sanitized template such as `*.example.*` instead of pushing real data.
