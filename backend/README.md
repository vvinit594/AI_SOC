# AI-SOC backend

FastAPI application for log processing, detection, and agent orchestration. The Next.js frontend is a separate package.

Phase 3 implements the process shell: configuration, logging, CORS, routing, and `GET /health`. Phase 4 adds PostgreSQL via SQLAlchemy, typed event/incident schemas, Alembic migrations, and read APIs for events and incidents. Phase 5 adds JSON/CSV upload, demo scenario loaders, and deterministic R1/R2/R3 detection with incident correlation. Phase 6 runs a four-node LangGraph investigation (`POST /api/incidents/{id}/investigate`) and persists each node in `agent_runs`. Phase 7 streams live progress on `GET /api/investigations/{id}/stream` from persisted `agent_runs` (replay + follow). Phase 8A persists response-action decisions and exposes `POST /api/actions/{id}/approve` and `/reject` (simulated only). Phase 8B records those decisions in append-only `audit_logs` and exposes `GET /api/incidents/{id}/audit-logs`. Downloadable reports and frontend wiring are not in this phase.

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
- Investigate: `POST /api/incidents/{id}/investigate`
- Investigation: `GET /api/investigations/{id}`
- Live progress (SSE): `GET /api/investigations/{id}/stream`
- Approve action: `POST /api/actions/{id}/approve` (simulated; see below)
- Reject action: `POST /api/actions/{id}/reject` (simulated; see below)
- Incident audit history: `GET /api/incidents/{id}/audit-logs`
- Docs: http://localhost:8000/docs (disabled when `APP_ENV=production`)

### Approve / reject (Phase 8A)

`GET /api/incidents/{id}` includes persisted `response_actions` with database UUIDs (not mock IDs).

| Current `approval_status` | Approve | Reject |
|---------------------------|---------|--------|
| `proposed` | 200, persist `approved` | 200, persist `rejected` |
| same decision again | 200 idempotent (original `actor` and `decided_at`) | 200 idempotent |
| opposite decision | 409 | 409 |
| unknown UUID | 404 | 404 |
| invalid UUID | 422 | 422 |

Authentication uses `ANALYST_API_TOKEN` (`Authorization: Bearer …`). Development/test with an empty token records `unverified`. A valid configured token records `analyst`. Production with an empty token returns 403. See `../docs/environment.md`.

Decisions set `decided_at` (UTC) and keep `simulated=true` and `execution_status=not_executed`. No containment function is invoked. Incident status stays `awaiting_approval` even when one of several actions is decided; action-level status is the source of truth. Incidents are never auto-resolved by an approval.

Re-running an investigation does not delete or reset approved/rejected rows and does not recreate a proposed duplicate for the same `(action_type, target)`. Concurrent contradictory decisions are serialized with the existing incident advisory lock plus `SELECT … FOR UPDATE` on PostgreSQL.

### Audit history (Phase 8B)

A successful approve or reject inserts one `audit_logs` row in the **same transaction** as the action update. If audit validation or insert fails, the decision is rolled back. Repeating the same decision, 409 conflicts, and 404/422 errors do not write a success audit event. `details` only accepts `decision`, `previous_approval_status`, `resulting_approval_status`, and `action_type`. There is no unique constraint on `(resource_type, resource_id, event_type)`.

`GET /api/incidents/{id}/audit-logs` returns `{items, total}` newest-first (`occurred_at` descending) with the same pagination bounds as incident list (`limit` 1–500, default 100). It uses the same `ANALYST_API_TOKEN` policy as approve/reject. There is no endpoint to edit or delete audit rows. Application code is append-only; a DBA with SQL access can still change the table. Retention is not automated.

## Checks

Run every command from this `backend/` directory with **this** `.venv`, not a global `python` and not a venv at the repo root. On this Windows machine the unprefixed `python` command is 3.14 and does not include SQLAlchemy.

```powershell
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\alembic.exe check
```

Alembic reads `backend/alembic.ini`. Running `alembic` from the repository root fails with `No 'script_location' key found`.

## Environment

See `../docs/environment.md`. Phase 3–8B read:

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
| `LLM_PROVIDER` | `none` | `none` \| `openai`. Missing keys do not invent findings. |
| `THREAT_INTEL_PROVIDER` | `none` | `none` \| `abuseipdb`. Failures are `unavailable`. |
| `ANALYST_API_TOKEN` | empty | Shared bearer for approve/reject. Empty is allowed in development/test (`unverified`) and refused in production (403). |
