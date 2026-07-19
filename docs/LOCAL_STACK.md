# Local stack (Docker-free) — Redis, MinIO, dramatiq worker

Docker Desktop was unavailable on this machine (stuck behind a self-update GUI
approval), so the queue + object-storage dependencies were brought up natively
via Homebrew instead. This documents what was installed and how to
start/stop/verify it. **No new project dependency was added** — `redis` and
`minio` are host-level services, not Python packages; `pyproject.toml` is
unchanged.

## What's installed

| Service | Install | Port | Managed by |
|---|---|---|---|
| Redis | `brew install redis` | `:6379` | `brew services` (LaunchAgent, same as `postgresql@16`) |
| MinIO | `brew install minio/stable/minio minio/stable/mc` | `:9000` (API), `:9001` (console) | custom LaunchAgent (`~/Library/LaunchAgents/homebrew.mxcl.minio.plist`) — the `minio` brew formula ships no service block, so `brew services` can't manage it |
| dramatiq worker | already a project dependency (`dramatiq[redis]`) | — | run manually per dev session (matches how the API is started via `uv run uvicorn ...`) |

## Credentials / config

MinIO is provisioned with root credentials that **match the backend's existing
defaults** in `backend/src/entropia/config/settings.py` — no `.env` changes
needed:

- `OBJECT_STORAGE_ACCESS_KEY` default `entropia` → `MINIO_ROOT_USER=entropia`
- `OBJECT_STORAGE_SECRET_KEY` default `entropia-secret` → `MINIO_ROOT_PASSWORD=entropia-secret`
- `OBJECT_STORAGE_ENDPOINT` default `http://localhost:9000` → MinIO API port
- `OBJECT_STORAGE_BUCKET` default `entropia-artifacts` → created once via `mc mb`
- `REDIS_URL` default `redis://localhost:6379/0` → matches the brew Redis instance

Data directory: `~/minio-data` (outside the repo, not tracked by git).

## Start / stop / status

```bash
# Redis — brew-managed, autostarts at login
brew services start redis
brew services stop redis
brew services info redis

# MinIO — custom LaunchAgent, autostarts at login
launchctl load ~/Library/LaunchAgents/homebrew.mxcl.minio.plist
launchctl unload ~/Library/LaunchAgents/homebrew.mxcl.minio.plist
launchctl list | grep minio
tail -f ~/Library/Logs/minio.log ~/Library/Logs/minio.err.log

# dramatiq worker — start per dev session (background)
cd backend
uv run dramatiq entropia.apps.worker.actors --processes 1 --threads 4
```

Both Redis and MinIO survive reboots/logins (LaunchAgents). The worker does
**not** auto-start — start it whenever you need real job processing (e.g. to
exercise the actual backtest RUN chain instead of Ready-Check-only flows).

## One-time bucket creation (already done on this machine)

```bash
mc alias set entropia-local http://localhost:9000 entropia entropia-secret
mc mb entropia-local/entropia-artifacts
```

## Verification

```bash
# 1. Dependency health
curl -s http://localhost:8000/api/v1/health/ready | python3 -m json.tool
# expect: {"status": "ok", "checks": {"postgres": "ok", "redis": "ok", "object_storage": "ok"}}

# 2. Full smoke test (core API + deps + metrics + identity + frontend)
make smoke

# 3. Worker round-trip (queue -> worker actually executes)
cd backend
uv run python -c "
from entropia.apps.worker.actors import system_heartbeat
system_heartbeat.send(note='manual-check')
"
# then check the worker's own stdout/log for a 'worker.heartbeat' line
```

`system_heartbeat` (`backend/src/entropia/apps/worker/actors.py`) exists
specifically to prove the queue/worker round-trip without needing a full
market-data ingest chain — use it for a quick sanity check.

## Honest boundary

- This is a **host-native** substitute for `docker compose up`, not a
  replacement for it — CI and the documented Docker path in the root
  `README.md` are unaffected and still the source of truth for
  containerized verification.
- If Docker Desktop's self-update prompt gets approved later, the Docker
  Compose path (`docker compose up -d --build` + `make smoke`) remains the
  preferred way to validate the full containerized stack end to end (per
  `CLAUDE.md`); this document is the fallback for machines where that isn't
  currently possible.
- The dramatiq worker is a plain background process for this dev session
  only (mirrors how `uvicorn` itself is started manually) — it does not
  survive a reboot. Turn it into a LaunchAgent too if you want it durable
  across restarts.
