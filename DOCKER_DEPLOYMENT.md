# Docker Deployment

This repo now ships with a root-level Docker deployment that matches the current project structure:

- `redis`: Redis queue backend
- `app`: FastAPI backend + Playwright worker + Celery worker in one container
- `frontend`: Next.js standalone frontend
- `Electron desktop`: launched on the Windows host and connected to the Docker stack

## One-click startup on Windows

Run:

```bat
docker-deploy.bat
```

What it does:

- builds and starts the Docker services
- waits for `3000` and `7000` to become healthy
- launches the Electron desktop client

After startup:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:7000`
- API docs: `http://localhost:7000/api/docs`
- Electron desktop: starts automatically

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

## Data persistence

Container runtime data is persisted under:

- `runtime-data/app`
- `runtime-data/redis`

That keeps SQLite files, uploads, cookies, Redis append-only data, and logs outside the images.

## Why the backend and Playwright worker share one container

The current backend still contains several internal calls to `127.0.0.1:7001`. Keeping the backend and Playwright worker in the same container preserves the existing runtime contract and avoids risky behavior changes during deployment work.

## Why Electron runs on the host

Electron is the desktop shell. Running it inside a Linux Docker container would not produce a practical Windows desktop experience. The complete deployment therefore keeps the UI shell on the host and lets Docker own the backend, worker, queue, and web frontend stack.
