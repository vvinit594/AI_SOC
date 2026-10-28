# AI-SOC — Autonomous Threat Investigation & Response Platform

An Agentic AI Security Operations Center (SOC) that ingests security logs, detects suspicious activity with transparent rules, coordinates specialized LangGraph agents to investigate incidents, enriches indicators with real threat intelligence, maps behaviour to MITRE ATT&CK, and recommends a safe, human-approved response — all through a live security dashboard.

> **Status:** Phase 8A (persisted response actions and approve/reject API) complete. Phase 8B audit-log history, 8C reports, and 8D frontend integration have not started. See [`docs/MVP_SPEC.md`](docs/MVP_SPEC.md) for the frozen v1 scope.

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
├── docker-compose.yml # Local PostgreSQL (full stack in Phase 10)
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

### Running locally

**Frontend (Phase 2)**

```bash
cd frontend
cp .env.example .env.local   # optional; defaults match local development
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Incident tables still use mock data. The header health indicator calls `GET /health` on the FastAPI backend.

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

Pytest uses an in-memory SQLite database and does not require Docker:

```bash
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check app
```

The frontend still reads Phase 2 mock data. Backend `GET /api/events` and `GET /api/incidents` persist the same demo IDs; the UI swap is a later wiring step, not Phase 6.

The final target is a single command:

```bash
docker compose up --build
```

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
| 8 | Response center & incident reports | ⏳ |
| 9 | Testing & security hardening | ⏳ |
| 10 | Dockerize | ⏳ |
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

## License

TBD.
