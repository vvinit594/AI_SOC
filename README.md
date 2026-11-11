# AI-SOC — Autonomous Threat Investigation & Response Platform

An Agentic AI Security Operations Center (SOC) that ingests security logs, detects suspicious activity with transparent rules, coordinates specialized LangGraph agents to investigate incidents, enriches indicators with real threat intelligence, maps behaviour to MITRE ATT&CK, and recommends a safe, human-approved response — all through a live security dashboard.

> **Status:** Phase 10 (local Docker Compose stack) implemented. Phase 11 public deployment has not started. See [`docs/MVP_SPEC.md`](docs/MVP_SPEC.md) for the frozen v1 scope.

---

## Core demo loop

1. Load a built-in scenario or upload a JSON/CSV security log.
2. The detection engine parses events and raises incidents with structured evidence.
3. Click **Investigate Incident** — a LangGraph workflow runs four agent nodes and persists each step. `GET /api/investigations/{id}/stream` pushes live (and replayed) node status over SSE.
4. Review evidence, severity, attack timeline, threat-intel results, ATT&CK mapping, and root-cause hypothesis.
5. Approve or reject the recommended (simulated) response; every decision is audited.
6. Download the incident report. Everything persists across refreshes and restarts.

## Architecture

```
┌──────────────────────┐      REST + SSE      ┌──────────────────────────┐
│  Next.js frontend    │ ───────────────────▶ │  FastAPI backend         │
│  App Router · TS     │                      │  Ingestion · Detection   │
│  Tailwind · shadcn   │ ◀─────────────────── │  LangGraph · SSE stream  │
└──────────────────────┘                      └────────────┬─────────────┘
                                                           │ SQLAlchemy / Alembic
                                                           ▼
                                              ┌──────────────────────────┐
                                              │  PostgreSQL              │
                                              │  events · incidents      │
                                              │  agent_runs · actions    │
                                              └──────────────────────────┘
                                                           │
                                       external, server-side only
                                                           ▼
                                   LLM provider · Threat-intel API · MITRE ATT&CK data
```

The frontend and backend are **separate applications**. All secrets (LLM keys, threat-intel keys, database credentials) live only on the backend.

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, Recharts |
| Backend | Python 3.13, FastAPI, Pydantic, Server-Sent Events |
| Agents | LangGraph, LangChain tool integrations, structured LLM outputs |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| Detection | Deterministic Python rules (optional scikit-learn anomaly scoring) |
| Threat intel | AbuseIPDB / VirusTotal, local MITRE ATT&CK subset |
| Deployment | Docker Compose (local), Vercel (frontend), Python host (backend), managed PostgreSQL |

## Repository layout

```
ai-soc/
├── frontend/          # Next.js application
├── backend/           # FastAPI application, detection engine, LangGraph agents
├── docs/              # Specification, environment variables, design notes
│   ├── MVP_SPEC.md
│   └── environment.md
├── docker-compose.yml # Frontend, backend, Postgres, and one-shot migrations
├── .gitignore
└── README.md
```

## Getting started

### Prerequisites

- Node.js LTS (≥ 20) and npm
- Python 3.13 (3.11+ supported; 3.13 recommended for dependency wheel compatibility)
- Git
- Docker Desktop (for local PostgreSQL from Phase 4 onward)

Verify:

```bash
node --version
npm --version
python --version     # or: py -3.13 --version on Windows
git --version
docker --version
```

### Environment variables

Copy the example files and fill in your own values — never commit real `.env` files:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

The full list of variables and their purpose is documented in [`docs/environment.md`](docs/environment.md).

### One-command local stack (Phase 10)

From a clean checkout, with Docker Desktop running:

```bash
cp .env.example .env          # optional; defaults match local development
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | [http://localhost:3000](http://localhost:3000) |
| Backend health | [http://localhost:8000/health](http://localhost:8000/health) |
| Backend docs | [http://localhost:8000/docs](http://localhost:8000/docs) (`APP_ENV=development`) |

Postgres is bound to `127.0.0.1` only. Containers use the Compose hostname `postgres`. The browser must use `http://localhost:8000`, never `http://backend:8000`.

Optional demo seed (not run automatically):

```bash
docker compose exec backend python -m app.db.seed
```

Inspect logs and health:

```bash
docker compose ps
docker compose logs --tail=200
curl http://localhost:8000/health
```

Migrations run once via the `migrate` service (`alembic upgrade head`) before the API starts. Check the version from the backend container:

```bash
docker compose exec backend alembic current
```

Stop without deleting data:

```bash
docker compose down
```

**Do not** run `docker compose down -v` unless you intend to destroy the named volume (`aisoc_pgdata`) and every stored event, incident, and audit row. To inspect the volume name: `docker volume ls`. A destructive reset is `docker compose down` followed by removing that volume — never do this to preserve demo data.

If host port `5432` is already taken (common on Windows), copy `docker-compose.override.example.yml` to `docker-compose.override.yml` and set host `DATABASE_URL` to port `55432`. See [`docs/environment.md`](docs/environment.md).

The Compose frontend image runs production Next.js (`NODE_ENV=production`), so `/api/analyst` stays disabled. Public incident reads still go to `http://localhost:8000`. Direct FastAPI approve/reject works in development with an empty `ANALYST_API_TOKEN` (actor `unverified`). That is not a login session.

### Host-run frontend and backend

**Frontend (Phase 2)**

```bash
cd frontend
cp .env.example .env.local   # optional; defaults match local development
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Live backend data is used by Response Center, persisted incident detail, audit history, and HTML report download. Overview, event explorer, the incidents list, dashboard metrics, and ATT&CK/root-cause narrative remain Phase 2 mock snapshots unless a matching mock ID exists. The header health indicator calls `GET /health`.

```bash
npm run build    # production build check
```

**Backend (Phase 3–5)**

```bash
cd backend
uv venv --python 3.13 .venv
uv pip install --python .venv -r requirements-dev.txt
copy .env.example .env
```

Start PostgreSQL, apply migrations, and seed the three demo scenarios:

```bash
docker compose up -d postgres
cd backend
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\python.exe -m app.db.seed
.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

On macOS or Linux, activate `.venv` and run `alembic upgrade head`, `python -m app.db.seed`, then `uvicorn app.main:app --reload --port 8000`.

- Health: [http://localhost:8000/health](http://localhost:8000/health)
- Events: [http://localhost:8000/api/events](http://localhost:8000/api/events)
- Incidents: [http://localhost:8000/api/incidents](http://localhost:8000/api/incidents)
- Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

Pytest uses an in-memory SQLite database for most tests and does not require Docker. PostgreSQL integration tests use a disposable database (`aisoc_phase5_verify` / `aisoc_phase9_verify`) and skip if they would touch live `aisoc`:

```bash
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check app
.venv\Scripts\python.exe -m ruff format --check .
```

Frontend checks (from `frontend/`):

```bash
npm test
npx tsc --noEmit
npm run lint
npm run build
```

There is no Playwright suite in this repository. Browser verification of the Response Center remains a manual procedure (see `frontend/README.md`).

Protected analyst UI calls go through same-origin `/api/analyst` in development/test. The browser never receives `ANALYST_API_TOKEN`. Production disables that proxy because there is no login session.

## Development roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Define MVP scope | ✅ Done |
| 1 | Development environment & repository | ✅ Done |
| 2 | Next.js frontend foundation | ✅ Done |
| 3 | FastAPI backend | ✅ Done |
| 4 | Database & event schemas | ✅ Done |
| 5 | Log ingestion & threat detection | ✅ Done |
| 6 | Agentic AI workflow (LangGraph) | ✅ Done |
| 7 | Live investigation progress (SSE) | ✅ Done |
| 8 | Response center & incident reports | ✅ Done |
| 9 | Testing & security hardening | ✅ Done |
| 10 | Dockerize | ✅ Done |
| 11 | Deploy & go live | ⏳ |
| 12 | Final demo preparation | ⏳ |

## Demo scenarios

| Scenario | Description | Expected result |
|----------|-------------|-----------------|
| A — Brute-force login | Many failed logins from one IP, then a success | High/critical incident, ATT&CK T1110, account-security actions |
| B — Suspicious outbound | Host repeatedly connects to an unusual external IP | Medium/high incident, real reputation lookup (or explicit "unavailable") |
| C — Benign activity | Normal logins and a scheduled admin task | No confirmed attack; proportionate low severity with explanation |

All sample data is synthetic and uses RFC 5737 documentation IP ranges.

## Safety & limitations

- Response actions in v1 are **simulated** and clearly labelled; nothing is blocked, isolated, or disabled for real.
- Uploaded logs and external API responses are treated as **untrusted data**; instructions inside logs never override system policy.
- Failed threat-intel lookups are reported as *unavailable*, never fabricated.
- LLM confidence is a qualitative label, not a calibrated probability.
- Not built yet: live log streaming, SIEM/EDR integrations, AI SOC assistant, custom-trained models.
- The Docker frontend is a production Next.js server, so `/api/analyst` remains disabled until real login exists.

## License

TBD.
