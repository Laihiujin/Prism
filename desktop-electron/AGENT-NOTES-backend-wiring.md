# Desktop app backend/Redis wiring — investigation notes

FINAL: fresh `electron-builder --dir` rebuild successful. App relaunched and VERIFIED:
backend:9200 RUN (accounts 200), automation-worker:7003, celery-worker, hermes-dashboard:9119,
hermes-webui:9131 (gateway disabled expected), redis:6379 (system fallback), frontend :3001
(root + /api/tasks 200, proxies to 9200). Frontend log shows `Backend URL: http://127.0.0.1:9200`.
NOTE: the app's bundled frontend binds the first free port (3001) because an orphaned
`next-server` from a prior run held 3000; `getFrontendBaseUrl()` = getFrontendPort() so the
home tab loads the correct port. Kill orphaned next-server to keep 3000 canonical.

## Webview shell + Settings (done, in source)
- renderer.js `API_BASE` default `:7000/api/v1/system` -> `:9200/api/v1/system`; `hydrateSystemApiBase()`
  now derives from `getInfo().backendUrl` (was reading the never-returned `systemApiBaseUrl`).
  This makes every Settings button (restart/stop/clear-*/self-check/export-logs) hit the real backend.
- renderer.js: added loading spinner state (did-start-loading/did-stop-loading), `updateActiveLoadingState()`.
- renderer.js: browser-style shortcuts (Cmd/Ctrl+L/R/W/T, Tab, PageUp).
- index.html: `.webview-loading` spinner element+CSS; added "运行信息" settings section
  (backend url + live service status), refreshed on panel open via app.getInfo()/supervisor.getStatus().
- Supervisor `start_redis`: allow system redis fallback in packaged mode + probe non-.exe `redis-server`
  + the missing `import shutil` (NameError was crashing supervisor at start_redis -> "services unhealthy").

Goal objective: fix A (frontend→backend URL), B (Redis), then webview shell + settings.
Confirmed architecture: browsers/Tools under `runtime-data/components/browsers/<provider>/`,
runtime.json/active.json version+hot-switch, `prism_components/` placeholder only.

## Empirical facts (live packaged mac app at desktop-electron/dist-build/mac-arm64/Prism.app)

Ports in the live run (via `lsof` and supervisor `/api/status` on 127.0.0.1:7002):
- backend (FastAPI prism_backend) — RUNNING on **:7003** (dynamically assigned); `/api/v1/accounts`→200 `{"success":true,"total":0,"items":[]}`, `/api/v1/ping`→200.
- automation_worker → :7004; celery_worker → running.
- hermes_dashboard → :9119; hermes_webui → :9131; hermes_gateway → disabled (no messaging platforms configured).
- supervisor HTTP API → :7002 (only serves /api/status,/api/restart,/api/health,/api/diagnostics — NOT /api/accounts).
- prism-ser → :8080 (Go `./bin/prism-service`, NOT the FastAPI backend).
- deepseek-harness → :3080 (the live GUI). Prism frontend (Next standalone) → :3000.

## A) frontend 404 root cause
- Frontend logs `[/api/tasks] Backend URL: http://127.0.0.1:7002` and `Failed to load accounts from backend: Backend responded with 404`.
- :7002 is the SUPERVISOR API (api_server.py), not the backend. Real backend is :7003.
- Supervisor `api_server.py` does NOT proxy `/api/*` → frontend hitting :7002/api/* → 404.
- Frontend backend URL resolution:
  - `prism_frontend/src/lib/env.ts:18` — `backendBaseUrl = PRISM_INTERNAL_BACKEND_URL ?? NEXT_PUBLIC_BACKEND_URL ?? NEXT_PUBLIC_API_BASE ?? http://127.0.0.1:7000` (server-side /api proxy routes).
  - `prism_frontend/src/lib/runtime-backend.ts` — uses `electronAPI.app.getInfo().backendUrl`.
  - No `.env*` in prism_frontend (only `.env.local.example`), so no baked NEXT_PUBLIC_*.
- Electron main (`src/main/index.js`):
  - `getBackendBaseUrl()` (337) = normalize(PRISM_BACKEND_URL || NEXT_PUBLIC_PRISM_BACKEND_URL || NEXT_PUBLIC_BACKEND_URL); fallback port from `resolveBackendPort` (328) which prefers `this.backendPort`.
  - `app:getInfo` (2918) returns `backendUrl: this.getBackendBaseUrl()`, `backendPort: this.getBackendPort()`.
  - Supervisor state bootstrap (1443-1450): `this.supervisorApiPort = lastState.apiPort` (7002); `this.backendPort = servicePorts.backend`.
  - `/api/status` sync (1545-1547): `this.backendPort = nextBackendPort`.
  - Sets `process.env.NEXT_PUBLIC_BACKEND_URL = backendUrl` (1562, 1809-1812, 2609-2612, 2650-2653) at the moment of service/frontend launch.
  - `getBackendBaseUrl()` default when this.backendPort unset → 7000.
- CONCLUSION for A: the frontend is told the wrong backend port (:7002). It should be the supervisor's *discovered* backend port (:7003). Need to confirm why frontline got 7002 (likely env set to :7002 at launch before the true backend port was synced, or the state file's servicePorts.backend was unavailable/wrong at bootstrap). Fix = drive the frontend's backend URL from the supervisor's discovered backend port.

## B) Redis root cause
- supervisor.py `start_redis` (1503-1545):
  - `_resolve_managed_binary("redis","redis-server")` → resolves `runtime-data/components/redis/current.json` (None if absent).
  - Searches ONLY Windows `.exe`: `resources/prism_backend/Redis/redis-server.exe`, `resources/Redis`, `resources/redis`.
  - `if not redis_exe and not self.is_packaged:` → system `shutil.which("redis-server")` fallback (gated OUT when packaged).
  - `if not redis_exe:` → `logger.warning("Prism Redis Runtime 未安装；生产模式不会回退用户机器上的 Redis。")`.
- The mac bundle has NO redis binary → in packaged mode redis is never started → backend needs Redis → backend can't fully run.
- Backend config: `prism_backend/fastapi_app/core/config.py:99` `REDIS_URL = "redis://localhost:6379/0"`.
- Backend port/binding: `prism_backend/fastapi_app/run.py` uses `settings.HOST`/`settings.PORT`; `core/runtime.py get_backend_port()` reads `PRISM_BACKEND_PORT` || `PRISM_BACKEND_URL` port || `runtime-data/runtime.json backend_port` || 7000.
- FIX for B (user accepted "或正确回退"): allow packaged mode to fall back to system `redis-server` if no managed/bundled redis, so the mac app uses the user's installed redis. (Or bundle a darwin redis binary; none readily present.)

## Platform gating
- desktop-electron/package.json `win.extraResources` bundles `resources/redis/{redis-server.exe,...}`; `mac.extraResources` ONLY bundles `resources/supervisor/{supervisor.py,api_server.py}` — no redis, no chromium payload.
