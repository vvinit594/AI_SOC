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
| `APP_ENV` | no | `development` | no | `development` \| `test` \| `production`. Controls debug output, docs exposure, and approve/reject token policy. If unset, Pydantic resolves `development` — it is never silently treated as production. `test` follows the development approval policy. |
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
| `LLM_PROVIDER` | no | `none` | no | `none` \| `openai`. With `none`, analysis uses evidence-backed deterministic rules and records `llm_status=unavailable`. |
| `LLM_API_KEY` | when provider is `openai` | — | **yes** | API key for the selected provider. |
| `LLM_MODEL` | no | `gpt-4o-mini` | no | Model name. Must support JSON structured output. |
| `LLM_TIMEOUT_SECONDS` | no | `60` | no | Per-call timeout. Timeouts are recorded on the agent run and are retryable. |
| `LLM_MAX_RETRIES` | no | `2` | no | Retries for transient provider errors. |

### Threat intelligence (Phase 6)

| Variable | Required | Default | Secret | Description |
|----------|----------|---------|--------|-------------|
| `THREAT_INTEL_PROVIDER` | no | `none` | no | `abuseipdb` \| `none`. With `none`, lookups return `unavailable` and the workflow still completes. |
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
| `RULE_SEEDED_SUSPICIOUS_IPS` | no | `198.51.100.88` | no | Comma-separated destinations that fire R3 on any connection (demo indicator). |

### Security (Phase 8A token; Phase 9 rate limits)

| Variable | Required | Default | Secret | Description |
|----------|----------|---------|--------|-------------|
| `ANALYST_API_TOKEN` | production: yes | empty (`None`) | **yes** | Shared bearer token for `POST /api/actions/{id}/approve`, `/reject`, `GET /api/incidents/{id}/audit-logs`, and `GET /api/incidents/{id}/report`. See behavior below. Not used for per-user identity. |
| `RATE_LIMIT_INVESTIGATE_PER_MINUTE` | no | `5` | no | Rate limit for `POST /api/incidents/{id}/investigate`. **Not implemented in Phase 8A.** |
| `RATE_LIMIT_UPLOAD_PER_MINUTE` | no | `10` | no | Rate limit for `POST /api/logs/upload`. **Not implemented in Phase 8A.** |

#### `ANALYST_API_TOKEN` behavior (Phase 8A)

The token is compared with `Authorization: Bearer <token>` using a length-hiding digest compare. Token values are never logged or returned. An `X-Analyst-Id` header is ignored and is not proof of identity.

| `APP_ENV` | Token configured? | Request | Result | Recorded `actor` |
|-----------|-------------------|---------|--------|------------------|
| `development` or `test` | no / empty | no bearer required | 200 | `unverified` |
| `development` or `test` | yes | matching bearer | 200 | `analyst` |
| `development` or `test` | yes | missing or wrong bearer | 401 | — |
| `production` | no / empty | any | 403 | — |
| `production` | yes | matching bearer | 200 | `analyst` |
| `production` | yes | missing or wrong bearer | 401 | — |

Limitations: this is a **shared** token. It identifies only the generic actor `analyst`, never a named person. It is not session login, RBAC, or per-analyst audit identity.

Phase 8B audit rows are append-only in application code. A database administrator with SQL access can still update or delete `audit_logs`. There is no automated retention or purge.

---

## Frontend (`frontend/.env.local`)

| Variable | Required | Default | Secret | Description |
|----------|----------|---------|--------|-------------|
| `NEXT_PUBLIC_API_BASE_URL` | yes | `http://localhost:8000` | no | Base URL of the FastAPI backend. In production, the deployed API URL (HTTPS). Redeploy after changing. |
| `NEXT_PUBLIC_APP_NAME` | no | `AI-SOC` | no | Display name in the UI header. |

---

## Local PostgreSQL via Docker Compose (Phase 4 / 10)

Compose publishes Postgres on host port `5432`. If that port is already bound (common on Windows when `postgresql-x64-18` is installed), the API will fail with password authentication errors because it is talking to the wrong server. Leave the committed Compose service unchanged and use a gitignored override port plus a matching local `DATABASE_URL`.

On a host where both Windows PostgreSQL and Docker publish `5432`, `localhost:5432` on IPv4 typically reaches the Windows service. Point `DATABASE_URL` at the Compose override port (for example `55432`) and run Alembic from `backend/` so it loads `backend/.env`.

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
