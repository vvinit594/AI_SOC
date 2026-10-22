# AI-SOC backend

FastAPI application for log processing, detection, and agent orchestration. The Next.js frontend is a separate package.

Phase 3 implements the process shell: configuration, logging, CORS, routing, and `GET /health`. Phase 4 adds PostgreSQL via SQLAlchemy, typed event/incident schemas, Alembic migrations, and read APIs for events and incidents. Log ingestion, detection, and agents are not implemented yet.

## Setup

Python 3.13 is recommended (3.11+ supported). From this directory:

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv -r requirements-dev.txt
copy .env.example .env   # Windows
# cp .env.example .env   # macOS / Linux
```

Without `uv`:

```bash
python3.13 -m venv .venv
# Windows: .venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

## Database

Local PostgreSQL is defined at the repo root:

```bash
docker compose up -d postgres
```

Apply migrations and seed the three frozen demo scenarios (RFC 5737 documentation IPs, stable UUIDs matching the frontend mock data):

```bash
# Windows
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m app.db.seed

# macOS / Linux
.venv/bin/alembic upgrade head
.venv/bin/python -m app.db.seed
```

`DATABASE_URL` defaults to `postgresql+psycopg://aisoc:aisoc@localhost:5432/aisoc`. Pytest does not use Postgres; tests create tables on `sqlite:///:memory:`.

If host port 5432 is already taken (for example a Windows `postgresql-x64-18` service), keep the Compose database as-is and point local `DATABASE_URL` at another published host port. Do not change the committed Compose credentials or drop the volume. A gitignored `docker-compose.override.yml` can publish an extra host port without editing `docker-compose.yml`.

## Run

```bash
# Windows
.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000

# macOS / Linux
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://localhost:8000/health
- Events: http://localhost:8000/api/events
- Incidents: http://localhost:8000/api/incidents
- Docs: http://localhost:8000/docs (disabled when `APP_ENV=production`)

## Checks

```bash
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check app
```

## Environment

See `../docs/environment.md`. Phase 3–4 read:

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_ENV` | `development` | `development` \| `test` \| `production` |
| `APP_NAME` | `AI-SOC API` | Service name in docs and health |
| `LOG_LEVEL` | `INFO` | Stdlib logging level |
| `API_HOST` | `0.0.0.0` | Bind host |
| `API_PORT` | `8000` | Bind port |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Explicit frontend origin allowlist. Never `*`. |
| `DATABASE_URL` | `postgresql+psycopg://aisoc:aisoc@localhost:5432/aisoc` | SQLAlchemy URL |
| `DB_POOL_SIZE` | `5` | Connection pool size |
| `DB_MAX_OVERFLOW` | `5` | Extra connections beyond pool size |
