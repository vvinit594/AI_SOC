# AI-SOC frontend

Next.js App Router UI for the AI-SOC dashboard. The FastAPI backend is a separate application. Public routes (`/welcome`, `/login`, `/register`, `/forgot-password`, `/reset-password`) are unauthenticated. SOC routes are wrapped in `AuthGate`, which calls `GET /api/auth/me` with credentials included and sends expired sessions to `/login?reason=expired`. `GET /health` drives the header connection indicator. Response Center, persisted incident detail, audit history, and HTML report download call live APIs using the session cookie. Overview, event explorer, the incidents list, and dashboard metrics still use Phase 2 mock data.

## Stack

Next.js 16 · React 19 · TypeScript · Tailwind CSS 4 · shadcn/ui · Recharts · Lucide

## Scripts

```bash
cp .env.example .env.local
npm install
npm run dev      # http://localhost:3000
npm run build
npm run start
npm run lint
npm test         # vitest
npx tsc --noEmit
```

## Environment

See `../docs/environment.md`. `NEXT_PUBLIC_*` values are bundled into the browser and must not be secrets.

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | FastAPI origin for public browser calls |
| `NEXT_PUBLIC_APP_NAME` | `AI-SOC` | Header product name |
| `ANALYST_API_TOKEN` | empty | **Server-only.** Injected by `/api/analyst`. Never `NEXT_PUBLIC_`. |
| `API_UPSTREAM_URL` | `NEXT_PUBLIC_API_BASE_URL` | **Server-only** FastAPI origin for the analyst proxy |

Signed-in pages call FastAPI with `credentials: "include"`. The leftover `/api/analyst` proxy is disabled when `NODE_ENV=production` (`analyst_proxy_disabled`). That shared-token helper is not per-user authentication; cookie sessions are. The Compose frontend image is a production Next.js server, so the proxy stays disabled inside Docker while session calls to `http://localhost:8000` still work.

`NEXT_PUBLIC_API_BASE_URL` must remain a browser-reachable host URL (`http://localhost:8000`). Compose sets `API_UPSTREAM_URL=http://backend:8000` only on the server.

## Data

| Screen | Source |
|--------|--------|
| Overview, event explorer, incidents list, dashboard metrics | Phase 2 mock (`src/lib/data.ts`) |
| `/incidents/[id]` | Live `GET /api/incidents/{id}` for title/severity/status/summary/event IDs/actions. Root-cause, ATT&CK, and event timeline only if a mock snapshot exists for that ID. |
| `/response`, report download, audit history | Live FastAPI calls with the session cookie |
| `/investigations/[id]` | Mock snapshot plus live SSE when the investigation exists on the API |

## Manual browser verification (no Playwright in this repo)

1. Start PostgreSQL, the FastAPI backend (`uvicorn` on port 8000), and `npm run dev`.
2. Register at `/register`, confirm the dashboard loads, then log out from the sidebar.
3. Log in again. Load a scenario, run detection, investigate, then open `/response`.
4. Open a persisted incident from the Response Center, approve or reject one simulated recommendation, and confirm the audit actor is `user:{uuid}`.
5. Download the HTML report and check the filename, simulated-action disclaimer, and that scripts are absent.
6. With `NODE_ENV=production` (or `next start` after `npm run build`), confirm `/api/analyst/...` returns 403 while session cookie calls to FastAPI still work.
7. Confirm `/forgot-password` does not claim that an email was sent.
