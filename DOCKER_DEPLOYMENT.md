# Docker Deployment

This repo now ships with a root-level Docker deployment that matches the current project structure:

- `redis`: Redis queue backend
- `app`: FastAPI backend + Playwright worker + Celery worker in one container
- `frontend`: Next.js standalone frontend
- `HermesAgent`: dashboard + WebUI exposed from the `app` container

## One-click startup on Windows

Run:

```bat
docker-deploy.bat
```

What it does:

- builds and starts the Docker services
- creates the persistent runtime folders under `runtime-data`
- waits for `3000`, `7000`, `9119`, and `9131` to become reachable
- prints the current `docker compose ps` status

After startup:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:7000`
- API docs: `http://localhost:7000/api/docs`
- Hermes Dashboard: `http://localhost:9119`
- Hermes WebUI: `http://localhost:9131`

Stop the stack with:

```bat
docker-stop.bat
```

## Direct Docker Compose usage

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f app
docker compose down
```

If you also want the Windows desktop shell to attach to the Docker stack, launch it separately after the stack is healthy:

```bat
launch-electron-desktop.bat
```

## Data persistence

Container runtime data is persisted under:

- `runtime-data/app`
- `runtime-data/app/hermes-home`
- `runtime-data/redis`

That keeps SQLite files, uploads, cookies, Redis append-only data, and logs outside the images.

## Why the backend and Playwright worker share one container

The current backend still contains several internal calls to `127.0.0.1:7001`. Keeping the backend and Playwright worker in the same container preserves the existing runtime contract and avoids risky behavior changes during deployment work.

## Why Electron stays optional on the host

Electron is the desktop shell. Running it inside a Linux Docker container would not produce a practical Windows desktop experience. This deployment therefore lets Docker own the backend, worker, queue, Hermes runtime, and web frontend stack, while the Windows desktop shell can attach separately when needed.
