# AGENT.md

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
