# Prism Repo Layout And Cleanup

This repository mixes long-lived source trees, local runtimes, and generated build output. Do not bulk-move top-level folders unless the call sites are verified first.

## Stable top-level directories

- `prism_backend/`: FastAPI backend, workers, platform adapters, and Python services.
- `prism_frontend/`: React frontend source.
- `desktop-electron/`: Electron desktop shell and packaging project.
- `scripts/`: launch, packaging, maintenance, release, and Hermes helper scripts.
- `scripts/tests/`: manual and integration verification scripts moved out of the old top-level `Test/`.
- `config/`: checked-in config templates and local runtime config roots.
- `data/`: repo-local persistent data.
- `tools/`: vendored or locally managed tool integrations.
- `browsers/`: browser installers plus downloaded browser payloads used by local runtime and packaging.
- `build/`: packaging specs and intermediate build material. `build/supervisor.spec` is source-like; `build/supervisor/` is disposable cache.

## Root entrypoints

Prefer the repo-root wrappers for common local lifecycle commands:

- `start.bat`
- `stop.bat`

The old top-level `Test/` and `CleanTool/` folders have been folded into `scripts/`. Historical launchers are kept under `scripts/legacy/` instead of the repo root.

## Safe cleanup targets

These are disposable and should not stay in the repo root once they are no longer needed:

- `dist/`
- `logs/`
- `tmp/`
- `tmp-runtime-data/`
- `.tmp-channels-debug/`
- `.tmp-hibbiki/`
- `gcm-diagnose.log`
- `prism_backend/logs/`
- `prism_frontend/.next/`
- `prism_frontend/out/`
- `desktop-electron/dist-build/`
- `desktop-electron/out/`

## Optional heavy cleanup targets

Delete these only when you intentionally want to rebuild local dependencies:

- `node_modules/`
- `prism_frontend/node_modules/`
- `prismenv/`
- browser payload folders under `browsers/`
- `build/supervisor/`

## Recommended cleanup command

Dry run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\maintenance\cleanup_local_artifacts.ps1
```

Apply safe cleanup:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\maintenance\cleanup_local_artifacts.ps1 -Apply
```

Apply with optional heavier cleanup:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\maintenance\cleanup_local_artifacts.ps1 -Apply -IncludePackagingCache -IncludeBrowserDownloads
```
