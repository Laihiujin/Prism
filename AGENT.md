# AGENT.md

## Repo Hygiene

- GitHub only carries source code, docs, sanitized examples, and build scripts.
- Never commit or push real account data, cookies, browser profiles, fingerprints, proxy/IP pool data, logs, local databases, or other runtime artifacts.
- Do not include raw account identifiers, cookie values, proxy IPs, or local-only paths in commit messages, PR descriptions, screenshots, or copied debug output.

## Local-Only Data

The following are local runtime data and must stay out of GitHub:

- `.env`
- `syn_backend/cookiesFile/`
- `config/cookiesFile/`
- `syn_backend/browser_profiles/`
- `config/browser_profiles/`
- `syn_backend/fingerprints/`
- `syn_backend/data/ip_pool*.json`
- `syn_backend/data/account_stats*.json`
- `syn_backend/data/campaigns.json`
- `syn_backend/data/published_works.json`
- `syn_backend/logs/`
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
