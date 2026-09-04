<div align="center">

# Prism

**Multi-account, multi-platform automated matrix distribution for MCNs and short-video creators**\
**Built-in Agentic Development Runtime — multi-AI-agent cooperative Computer Use with self-iteration and closed-loop refinement**\
**Async high-concurrency task scheduling with distributed account locks: per-account mutual exclusion / multi-account parallelism**

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![Celery](https://img.shields.io/badge/Celery-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Patchright](https://img.shields.io/badge/Patchright-2E3440?style=flat-square)](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python)
[![Persona Studio](https://img.shields.io/badge/Persona%20Studio-7C3AED?style=flat-square)](https://github.com/TechQaiser/persona-studio)
[![HermesAgent](https://img.shields.io/badge/HermesAgent-111827?style=flat-square)](https://github.com/NousResearch/hermes-agent)

[![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=flat-square)](https://www.apache.org/licenses/LICENSE-2.0)
[![Python](https://img.shields.io/badge/python-3.11-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Node](https://img.shields.io/badge/node-%3E%3D18-339933?style=flat-square&logo=nodedotjs&logoColor=white)](https://nodejs.org/)

**English** | **[简体中文](README.md)**

</div>

---

## Keywords / 关键词（便于搜索）

**English**: Douyin uploader, Xiaohongshu publishing, Kuaishou, WeChat Channels, Bilibili, TikTok automation, YouTube uploader, matrix publishing, multi-account content distribution, cross-platform publishing, scheduled publishing, browser fingerprint isolation, proxy pool, Patchright, Playwright, AI agent, MCP server

**中文**: 抖音自动发布、小红书发布助手、快手、视频号、B站、TikTok 自动化、YouTube 上传、短视频矩阵发布、多账号内容分发、跨平台发布、定时发布、自媒体矩阵、账号身份隔离、浏览器指纹、代理池、AI 智能体、MCP

---

## 🟟 Product Demo / 产品演示视频

**Real Interaction Walkthrough / 真实交互 Walkthrough**

![walkthrough](docs/demos/prism_wrap.gif)

**14-Screen Feature Tour / 14 页功能巡览**

![tour](docs/demos/prism_hyperframes_demo.gif)

---

[Quick Start](#quick-start) · [Architecture](#architecture) · [CLI](#cli) · [API](#api) · [Project Layout](#project-layout) · [Contributing](#contributing) — [简体中文版 ↓](README.md)

## What is Prism

Prism is a **front-end/back-end separated** self-hosted system for operating many creator accounts across many platforms (Douyin, Kuaishou, Xiaohongshu, Video Channels, Bilibili, TikTok, YouTube) without the accounts colliding with each other. Its core runs on **Celery + Redis** for asynchronous high-concurrency task processing, with **per-account Redis distributed locks** (`SET NX` + heartbeat renewal) ensuring only one active Browser Runtime per account at a time instead of racing each other.

It is not a video editor and it does not generate footage. It sits downstream of content production and owns four things:

- **Account identity isolation** — each account gets its own browser fingerprint, persistent session, and sticky outbound proxy, so ten accounts on one machine don't look like one operator to the platform.
- **Scheduling and execution** — material → matrix task → queued, concurrent, retryable execution across accounts and platforms.
- **Observability** — per-account runtime state, task logs, and failure alerts.
- **Recovery** — pulling post-publish metrics back in for a feedback loop.

Prism doesn't touch upstream content production (editing or footage generation), but you can wire it in through the built-in **Hermes**: integrate open-source projects into the component and plugin libraries (including skill libraries), so upstream capabilities plug in as components and complete the pipeline.

If you're evaluating this repo, the two things worth understanding first are the [identity/execution pipeline](#account-execution-pipeline) below and the fact that the AI layer (`HermesAgent`) is optional tooling on top, not a dependency of the publishing path.

## Feature overview

| Area | What's implemented |
|---|---|
| Account management | QR login (Douyin/Kuaishou/Xiaohongshu/Video Channels/Bilibili), local-browser login for TikTok/YouTube, Chrome-profile import, session-drop detection |
| Identity layer | Coherent fingerprint generation (OS/UA/GPU/timezone/locale consistency) via Persona Studio integration, with automatic fallback to isolated Patchright profiles if Persona isn't installed |
| Networking | Self-built Proxy Manager (health checks, sticky binding, pooled auto-assignment) + optional per-country mihomo gateway (SG/JP/US/DE/TW/HK) |
| Scheduling | Matrix task generation across N accounts × M platforms × K materials, Celery/Redis queue, scheduled publish, failure retry, per-account distributed execution lock (Redis) |
| Monitoring | Task queue dashboard, execution logs, account environment view (`browser × proxy × runtime` in one call) |
| Recovery | Post-publish metrics pull for Douyin/Bilibili (local), TikTok/YouTube (via TikHub API), with automatic account-profile enrichment (avatar/display name backfill) |
| AI orchestration | Embedded agent (HermesAgent) for natural-language publish requests, title/tag generation, and a skill/tool marketplace (`/tools`) with one-click install |
| Interfaces | Web console (Next.js), Electron desktop client, `prism` CLI, and a stdio MCP server for external AI agents |

## Architecture

### Account execution pipeline

Every automated browser action — login, publish, or metrics pull — goes through the same fixed chain:

```text
Account
  │
  ▼
Persona Profile          (fingerprint + persistent cookies/localStorage/IndexedDB)
  │
  ▼
Sticky Proxy             (Proxy Manager binding, optionally region-pinned via mihomo)
  │
  ▼
Patchright (CDP)         (anti-detection browser driver, connect_over_cdp)
  │
  ▼
Platform Adapter         (login / publish / scrape logic per platform)
```

Ownership is split cleanly between two systems rather than one monolith:

| Layer | Owner |
|---|---|
| Accounts, platforms, tasks, Celery, Redis | Prism |
| Proxy registry, health checks, sticky binding | Prism (`services/ip_pool_service.py`) |
| Per-country proxy gateway (ports 7771–7776) | mihomo, via Persona Studio's proxy tooling |
| Browser fingerprint / profile persistence | Persona Studio (optional; MIT-licensed, vendored as a submodule) |
| Browser execution | Prism, via Patchright `connect_over_cdp` |

If Persona Studio isn't installed, the identity layer degrades gracefully to a per-account isolated Patchright `persistent_context` under `data/browser_profiles/<account>/` — publishing still works, you just lose cross-session fingerprint coherence.

### System components

```text
prism_frontend/     Next.js console — plans, matrix tasks, dashboards, /tools, /cms
prism_backend/      FastAPI app — REST API, matrix scheduler, AI services, adapters
  ├── fastapi_app/    API routers, services, SQLAlchemy models, Celery tasks
  ├── platforms/      Per-platform adapters (login/publish/scrape)
  ├── automation_worker/  Standalone execution worker
  ├── ai_service/     LLM-backed title/tag generation, function calling
  └── douyin_tiktok_api/  Vendored parsing/data API (Douyin_TikTok_Download_API)
desktop-electron/    Desktop shell wrapping the web console
scripts/             Launchers, deployment, maintenance, ip pool tooling
tools/               Self-hosted components: hermes-agent, persona-studio, proxy gateway
```

### Process topology (self-hosted deployment)

| Process | Role | Default address |
|---|---|---|
| `prism-backend` | FastAPI API + matrix scheduler | `:7000` |
| `prism-worker` | Automation worker (browser execution) | `:7001` |
| `prism-celery` | Celery task queue consumer | via Redis |
| `prism-frontend` | Next.js console | `:3000` |
| `persona-api` | Persona Studio identity service (optional) | `:8787` |
| `persona-proxy` | mihomo per-country gateway (optional) | `:7771`–`:7776` |
| HermesAgent | Embedded AI agent dashboard/webui | `:9119` / `:9131` |

All processes are supervised via PM2 (macOS) or a bundled Supervisor (Windows), so a missing process fails loudly instead of degrading silently — a partial stack (e.g. backend up, worker down) will serve the console but silently drop task execution, so the launch scripts start the full set together.

## Quick start

Requirements: **Python 3.11, Node 18+, Redis** (required). A browser (Chromium/Firefox) is used for account login and automation and is prepared automatically on first run.

### ① Install system dependencies

- **Python 3.11**
  - macOS: `brew install python@3.11`
  - Ubuntu: `sudo apt install python3.11`
  - Windows: install from python.org and check *Add to PATH*
- **Node 18+**: from nodejs.org or `brew install node`
- **Redis** (required — Prism's Celery queue and per-account distributed locks depend on it)
  - macOS: `brew install redis && redis-server --daemonize yes`
  - Ubuntu: `sudo apt install redis-server` (then `redis-server --daemonize yes`)
  - Windows: download the `Redis-x64-*.zip` from [tporadowski/redis](https://github.com/tporadowski/redis/releases) and add it to PATH

### ② One-command environment bootstrap (cross-platform)

```bash
git clone https://github.com/Laihiujin/Prism.git
cd Prism
python3 bootstrap.py            # creates prismenv + pip deps + frontend deps + .env + checks Redis
```

`bootstrap.py` is the single "recipe" entry point — it is idempotent and safe to re-run:

| Command | Effect |
|---|---|
| `python3 bootstrap.py` | full bootstrap |
| `python3 bootstrap.py --dev` | also install development/test deps |
| `python3 bootstrap.py --no-browsers` | skip browser install (large on first run) |
| `python3 bootstrap.py --check` | check only, change nothing |

### ③ Start everything

```bash
# macOS / Linux (bootstraps the env, then lets PM2 manage every process)
./start-mac.sh

# Windows
start.bat

# Start only (skips bootstrap; must have run bootstrap.py first): macOS uses PM2
./start-pm2.sh
```

This brings up Redis → Celery worker → automation worker → FastAPI backend → frontend, in that order. Console at `http://localhost:3000`, API docs at `http://localhost:7000/api/docs`.

> **Process supervision**: on macOS/Linux/Windows all processes are managed by **PM2** (`start-pm2.sh` (macOS/Linux) / `start-pm2.bat` (Windows) + `ecosystem.config.js` — Redis, backend, worker, Celery, frontend, Persona, Hermes). `start-mac.sh` only prepares the environment (idempotently), then hands off to PM2.

> **About the virtual env**: the repo uses a single virtual env named `prismenv` (the launcher scripts, desktop packaging and Hermes runtime all refer to it). `python3 bootstrap.py` already includes creating `prismenv`; the equivalent manual commands are
> ```bash
> python3.11 -m venv prismenv
> prismenv/bin/python -m pip install -r requirements.txt   # Windows: prismenv\Scripts\python.exe
> cd prism_frontend && npm install && cd ..
> cp env.example .env
> ```

## Build the Electron desktop client locally (optional)

`desktop-electron/` is a desktop shell wrapping the web console. When packaging it bundles `prismenv`, `prism_backend`, `tools/hermes-agent`, `tools/hermes-webui`, `config`, plus `prism_frontend/.next/standalone`, `prism_frontend/.next/static` and `prism_frontend/public`. So you **must build the Next.js frontend first (`standalone` output)**, or `electron-builder` will fail on the missing resources.

### 0. Prerequisites (same as the web build — do it once)

```bash
python3 bootstrap.py        # creates prismenv + backend/frontend deps + .env
```

### 1. Build the frontend first (Next.js standalone output)

```bash
cd prism_frontend
npm install
npm run build               # produces .next/standalone, .next/static, public
```

Keep `output: "standalone"` in `prism_frontend/next.config.ts` — the packaging pipeline relies on it.

### 2. Package

#### macOS

```bash
cd desktop-electron
npm install                 # installs electron / electron-builder (postinstall runs install-app-deps)

npm run pack                # electron-builder --dir → dist-build/<arch>/Prism.app
# or full installers (dmg / zip for x64 + arm64):
npx electron-builder --mac
```

- Output lands in `desktop-electron/dist-build/`.
- **macOS needs a system Redis**: the mac bundle does not ship Redis binaries, so start Redis first:
  ```bash
  brew install redis && redis-server --daemonize yes
  ```
- The `mac` config sets `hardenedRuntime: false` and `gatekeeperAssess: false` — no code signing or notarization, fine for local use; add signing/notarization before public distribution.

#### Windows

```bat
cd prism_frontend
npm install
npm run build

cd ..\desktop-electron
npm install
npm run build               :: NSIS installer → dist-build\Prism-<version>-setup.exe
npm run build:dir           :: unpacked dir only → dist-build\win-unpacked\ (handy for local testing)
```

- One-click Windows packaging script (builds the frontend + backend service exes + supervisor + Inno/NSIS installer):
  ```bat
  scripts\packaging\build-package.bat
  ```
- Windows packaging prerequisites:
  - `desktop-electron\resources\redis\`: put `redis-server.exe`, `redis-cli.exe` and `redis.windows*.conf` in it (download from [tporadowski/redis](https://github.com/tporadowski/redis/releases), or run `scripts\packaging\prepare-supervisor-build.bat` to stage them).
  - Chromium: `scripts\launchers\setup_browser.bat`.
  - supervisor.exe: produced by `scripts\packaging\build-supervisor.bat` (PyInstaller).
  - Requires `prismenv\Scripts\python.exe` and `prismenv\_python\python.exe` (already created by `bootstrap.py`).

### 3. Local integration (run the Electron shell without packaging)

```bash
# Start the external stack first, then point Electron at it:
#   macOS:  ./start-mac.sh      Windows: start.bat
cd desktop-electron
npm run start               # electron . — connects to the already-running backend/frontend
```

> On Windows you can also use `launch-electron-desktop.bat` from the repo root; on macOS use `npm run dev` if you want Electron to bring up the services and frontend itself (it sets `PRISM_START_SERVICES=1`, `PRISM_START_FRONTEND=1`).

## CLI

The `prism` CLI shares adapters, account storage, and the Patchright runtime with the web console and desktop app — a task started from one surface is visible from the others.

```bash
pip install -e .

prism douyin login --account creator
prism douyin check --account creator
prism douyin upload-video \
  --account creator \
  --file ./video.mp4 \
  --title "Example title" \
  --description "Example description" \
  --tags "Prism,automation"

# scheduled publish (local time)
prism xiaohongshu upload-video --account creator --file ./video.mp4 \
  --title "Example" --schedule "2026-08-18 20:30"

# accounts without native QR login (real browser login required once)
prism tiktok login --account creator
prism youtube login --account creator

prism accounts            # list all accounts (JSON)
prism history             # publish history (JSON)
prism mcp                 # start Prism as an MCP stdio server for external agents
```

## API

REST API is versioned under `/api/v1`, grouped by domain (`accounts`, `matrix`, `publish`, `persona`, `persona_proxy`, `ip_pool`, `analytics`, `tools`, `agent`, …). Interactive docs are auto-generated at `/api/docs` (Swagger) and `/api/redoc`.

Generate a matrix publishing task:

```http
POST /api/v1/matrix/generate_tasks
Content-Type: application/json

{
  "platforms": ["xiaohongshu", "douyin"],
  "accounts": {
    "xiaohongshu": ["account_id_1", "account_id_2"],
    "douyin": ["account_id_3"]
  },
  "materials": ["material_id_1", "material_id_2"],
  "title": "xxxxx",
  "topics": ["#xxx", "#xxx"]
}
```

Bind an account to a proxy region:

```http
GET  /api/v1/accounts/{account_id}/persona-proxy
PUT  /api/v1/accounts/{account_id}/persona-proxy
```

Full per-account environment snapshot (browser backend + proxy + runtime status in one call):

```http
GET /api/v1/accounts/{account_id}/environment
```

## Project layout

```text
prism_backend/fastapi_app/
  api/v1/         30+ domain routers (accounts, matrix, publish, persona, ip_pool, tikhub, ...)
  services/       business logic — matrix_scheduler, ip_pool_service, runtime_lock_service, persona_client, ...
  models/         SQLAlchemy models
  tasks/          Celery task definitions
  agent/          HermesAgent integration + MCP tool bridging
prism_backend/platforms/     Per-platform login/publish/scrape adapters
prism_frontend/src/app/       Next.js routes — dashboard, matrix, accounts, ip-pool, persona, tools, cms
desktop-electron/            Electron wrapper + installer build
scripts/                     launchers/, deploy/, maintenance/, ip_pool/, hermes/
```

## Configuration

Two files matter for a working install:

- **`.env`** — ports, Redis URL, browser paths, frontend↔backend URLs, `PLAYWRIGHT_HEADLESS`, `PRISM_BROWSER_BACKEND_DEFAULT` (`patchright` / `persona`), `PRISM_DOUYIN_LOGIN_MODE` (`browser` / `http`).
- **`prism_backend/config/llm_config.toml`** — LLM provider/model/API key/base URL for HermesAgent and AI title/tag generation.

## Attribution

Prism composes rather than reimplements in a few key places. Each is a distinct upstream project under its own license (see [`NOTICE.txt`](./NOTICE.txt)):

| Component | Upstream | License |
|---|---|---|
| CLI/publish adapter baseline | [social-auto-upload](https://github.com/dreammis/social-auto-upload) | MIT |
| Douyin/TikTok parsing & data API | [Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) | Apache-2.0 |
| Local AI agent runtime | [HermesAgent](https://github.com/nousresearch/hermes-agent) | MIT |
| Browser identity/fingerprint layer | [Persona Studio](https://github.com/TechQaiser/persona-studio) | MIT |

Prism's own code is Apache-2.0; vendored MIT components retain their original license and required notices.

## Known limitations

Being direct about the current state rather than glossing over it:

- **Default storage is SQLite** — fine for a single-node self-hosted deployment; if you're pushing real concurrent write load through Celery at scale, plan a migration to a server-grade database.
- **Schema changes ship as ad-hoc scripts**, not a migration framework — review `prism_backend/db/` before altering table structure in a shared environment.
- **CORS defaults to `allow_origins=["*"]`** in `fastapi_app/main.py` — tighten this before exposing the API beyond localhost.

## Compliance

Use it only with **authorized / self-owned accounts**, and follow each platform's terms of service.

- Never commit cookies, login state, browser profiles, device fingerprints, proxy credentials, or API keys to the repo (see [`AGENT.md`](./AGENT.md) and [`.gitignore`](./.gitignore)).

This project is **for testing, academic research, and technical exchange only**. Do not use it for any malicious purpose that violates laws, regulations, or platform terms of service. Any consequences of misuse are the user's responsibility.

## Contributing

Issues and PRs welcome. See [`AGENT.md`](./AGENT.md) for repo hygiene rules (no committing cookies, browser profiles, fingerprints, or proxy data) if you're working with AI coding assistants against this repo.

## License

Apache License 2.0 — see [`LICENSE`](./LICENSE). Vendored MIT/Apache-2.0 components retain their original licenses and attribution per [`NOTICE.txt`](./NOTICE.txt).

## Community

Prism is discussed and promoted as an open-source project in the [LINUX DO](https://linux.do/) community.

Thanks to the LINUX DO community for providing developers with a platform for technical discussion, collaboration, and open-source sharing.

## [BuymeaCoffee](https://buymeacoffee.com/laihiujin3)

| | | |
|-|-|-|
| ![1d1114b7-9c71-4c18-91df-0a462bed5405](https://github.com/user-attachments/assets/f0c38071-f69a-4262-a339-182c090d4c41) | ![dac9dc35-e027-42e8-b6aa-81f3211906da](https://github.com/user-attachments/assets/761ae5f1-8350-49d6-bba6-de2f01f1b73e) | <img width="1284" height="2289" alt="prism" src="https://github.com/user-attachments/assets/b7932618-3945-4b5a-b689-9fce7f626e51" /> |

<div align="right">

[⬆ Back to top](#prism) · [简体中文版 ↓](README.md)

</div>
