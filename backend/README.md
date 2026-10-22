# AI-SOC backend

FastAPI application for log processing, detection, and agent orchestration. The Next.js frontend is a separate package.

Phase 3 implements the process shell: configuration, logging, CORS, routing, and `GET /health`. Domain endpoints are reserved as empty routers until later phases.

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

## Run

```bash
# Windows
.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000

# macOS / Linux
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://localhost:8000/health
- Docs: http://localhost:8000/docs (disabled when `APP_ENV=production`)

## Checks

```bash
.venv\Scripts\python.exe -m pytest
.venv\Scripts\ruff.exe check app
```

## Environment

See `../docs/environment.md`. Phase 3 reads:

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_ENV` | `development` | `development` \| `test` \| `production` |
| `APP_NAME` | `AI-SOC API` | Service name in docs and health |
| `LOG_LEVEL` | `INFO` | Stdlib logging level |
| `API_HOST` | `0.0.0.0` | Bind host |
| `API_PORT` | `8000` | Bind port |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | Explicit frontend origin allowlist. Never `*`. |
