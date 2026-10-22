# Environment Variables

This document lists every environment variable the AI-SOC application reads, where it is used, and whether it is secret.

**Rules**

- Real values live only in local `.env` files (git-ignored) and in the deployment provider's secret settings.
- `.env.example` files are committed with placeholder values and no secrets.
- Secrets (LLM keys, threat-intel keys, database credentials) are **backend-only**. The frontend never receives them.
- Any variable prefixed `NEXT_PUBLIC_` is bundled into the browser and must never contain a secret.

---

## Backend (`backend/.env`)

### Application

| Variable | Required | Default | Secret | Description |
|----------|----------|---------|--------|-------------|
| `APP_ENV` | no | `development` | no | `development` \| `test` \| `production`. Controls debug output and docs exposure. |
| `APP_NAME` | no | `AI-SOC API` | no | Display name in FastAPI docs and health response. |
| `LOG_LEVEL` | no | `INFO` | no | Python logging level. |
| `API_HOST` | no | `0.0.0.0` | no | Bind host for uvicorn. |
| `API_PORT` | no | `8000` | no | Bind port for uvicorn. |
| `CORS_ALLOWED_ORIGINS` | yes | `http://localhost:3000` | no | Comma-separated explicit allowlist of frontend origins. Never `*`. In production, set to the real Vercel URL. |

### Database (Phase 4)

| Variable | Required | Default | Secret | Description |
|----------|----------|---------|--------|-------------|
| `DATABASE_URL` | no | `postgresql+psycopg://aisoc:aisoc@localhost:5432/aisoc` | **yes** | SQLAlchemy URL. Matches the local Compose Postgres service. Use `?sslmode=require` with managed providers. Pytest uses `sqlite:///:memory:` and does not read this value. |
| `DB_POOL_SIZE` | no | `5` | no | SQLAlchemy connection pool size. Keep within the managed DB's connection limit. |
| `DB_MAX_OVERFLOW` | no | `5` | no | Extra connections allowed beyond pool size. |

### LLM provider (Phase 6)

| Variable | Required | Default | Secret | Description |
|----------|----------|---------|--------|-------------|
| `LLM_PROVIDER` | yes | `openai` | no | Which LangChain integration to load (e.g. `openai`, `anthropic`, `google`, `groq`). |
| `LLM_API_KEY` | yes | — | **yes** | API key for the selected provider. |
| `LLM_MODEL` | yes | — | no | Model name. Must support tool calling and structured output. |
| `LLM_TIMEOUT_SECONDS` | no | `60` | no | Per-call timeout. Timeouts are recorded on the agent run and are retryable. |
| `LLM_MAX_RETRIES` | no | `2` | no | Retries for transient provider errors. |

### Threat intelligence (Phase 6)

| Variable | Required | Default | Secret | Description |
|----------|----------|---------|--------|-------------|
| `THREAT_INTEL_PROVIDER` | no | `abuseipdb` | no | `abuseipdb` \| `virustotal` \| `none`. With `none`, lookups return `unavailable` and the workflow still completes. |
| `THREAT_INTEL_API_KEY` | no* | — | **yes** | API key for the selected provider. *Required unless provider is `none`. |
| `THREAT_INTEL_TIMEOUT_SECONDS` | no | `10` | no | Lookup timeout. Failures are reported as `unavailable`, never fabricated. |
| `THREAT_INTEL_CACHE_TTL_SECONDS` | no | `86400` | no | How long an indicator's enrichment result is cached (24 h). |

### Ingestion & detection (Phase 5)

| Variable | Required | Default | Secret | Description |
|----------|----------|---------|--------|-------------|
| `MAX_UPLOAD_SIZE_MB` | no | `10` | no | Reject uploads larger than this. |
| `MAX_EVENTS_PER_UPLOAD` | no | `50000` | no | Parsing limit per file. |
| `RULE_AUTH_FAILURE_THRESHOLD` | no | `5` | no | R1: failures from one source within the window. |
| `RULE_AUTH_FAILURE_WINDOW_MINUTES` | no | `5` | no | R1/R2 time window. |
| `RULE_OUTBOUND_CONNECTION_THRESHOLD` | no | `10` | no | R3: connections from one host to one external IP within the window. |
| `RULE_OUTBOUND_WINDOW_MINUTES` | no | `5` | no | R3 time window. |

### Security (Phase 8–9)

| Variable | Required | Default | Secret | Description |
|----------|----------|---------|--------|-------------|
| `ANALYST_API_TOKEN` | prod: yes | — | **yes** | Shared bearer token required on approval/rejection endpoints when the app is publicly reachable. |
| `RATE_LIMIT_INVESTIGATE_PER_MINUTE` | no | `5` | no | Rate limit for `POST /api/incidents/{id}/investigate`. |
| `RATE_LIMIT_UPLOAD_PER_MINUTE` | no | `10` | no | Rate limit for `POST /api/logs/upload`. |

---

## Frontend (`frontend/.env.local`)

| Variable | Required | Default | Secret | Description |
|----------|----------|---------|--------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | yes | `http://localhost:8000` | no | Base URL of the FastAPI backend. In production, the deployed API URL (HTTPS). Redeploy after changing. |
| `NEXT_PUBLIC_APP_NAME` | no | `AI-SOC` | no | Display name in the UI header. |

---

## Local PostgreSQL via Docker Compose (Phase 4 / 10)

| Variable | Default | Secret | Description |
|----------|---------|--------|-------------|
| `POSTGRES_USER` | `aisoc` | **yes** | Database user created by the Postgres container. |
| `POSTGRES_PASSWORD` | `aisoc` | **yes** | Local-only development password. Use a strong value in any shared environment. |
| `POSTGRES_DB` | `aisoc` | no | Database name. |
| `POSTGRES_PORT` | `5432` | no | Host port mapped to the container. |

---

## Deployment mapping

| Variable | Set where |
|----------|-----------|
| `DATABASE_URL`, `LLM_*`, `THREAT_INTEL_*`, `ANALYST_API_TOKEN`, `CORS_ALLOWED_ORIGINS` | Backend host secret settings |
| `NEXT_PUBLIC_API_BASE_URL` | Vercel project environment variables |
| `POSTGRES_*` | Managed PostgreSQL provider (connection string exported as `DATABASE_URL`) |

---

## Checklist before every commit

- [ ] No `.env` or `.env.local` staged (`git status` shows only `.env.example`).
- [ ] No API keys or connection strings in code, docs, or screenshots.
- [ ] New variables added here and to the relevant `.env.example`.
