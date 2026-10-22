# AI-SOC — Autonomous Threat Investigation & Response Platform

An Agentic AI Security Operations Center (SOC) that ingests security logs, detects suspicious activity with transparent rules, coordinates specialized LangGraph agents to investigate incidents, enriches indicators with real threat intelligence, maps behaviour to MITRE ATT&CK, and recommends a safe, human-approved response — all through a live security dashboard.

> **Status:** MVP in active development. See [`docs/MVP_SPEC.md`](docs/MVP_SPEC.md) for the frozen v1 scope and acceptance criteria.

---

## Core demo loop

1. Load a built-in scenario or upload a JSON/CSV security log.
2. The detection engine parses events and raises incidents with structured evidence.
3. Click **Investigate Incident** — a LangGraph workflow runs four agent nodes with live progress.
4. Review evidence, severity, attack timeline, threat-intel results, ATT&CK mapping, and root-cause hypothesis.
5. Approve or reject the recommended (simulated) response; every decision is audited.
6. Download the incident report. Everything persists across refreshes and restarts.

## Architecture

```
┌──────────────────────┐      REST + SSE      ┌──────────────────────────┐
│  Next.js frontend    │ ───────────────────▶ │  FastAPI backend         │
│  App Router · TS     │                      │  Ingestion · Detection   │
│  Tailwind · shadcn   │ ◀─────────────────── │  LangGraph agents · SSE  │
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
├── frontend/     # Next.js application
├── backend/      # FastAPI application, detection engine, LangGraph agents
├── docs/         # Specification, environment variables, design notes
│   ├── MVP_SPEC.md
│   └── environment.md
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
cp backend/.env.example backend/.env       # created in Phase 3
cp frontend/.env.example frontend/.env.local
```

The full list of variables and their purpose is documented in [`docs/environment.md`](docs/environment.md).

### Running locally

Setup instructions for the frontend (Phase 2), backend (Phase 3), and database (Phase 4) will be added here as each phase lands. The final target is a single command:

```bash
docker compose up --build
```

## Development roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| 0 | Define MVP scope | ✅ Done |
| 1 | Development environment & repository | 🔄 In progress |
| 2 | Next.js frontend foundation | ⏳ |
| 3 | FastAPI backend | ⏳ |
| 4 | Database & event schemas | ⏳ |
| 5 | Log ingestion & threat detection | ⏳ |
| 6 | Agentic AI workflow (LangGraph) | ⏳ |
| 7 | Live investigation progress (SSE) | ⏳ |
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
