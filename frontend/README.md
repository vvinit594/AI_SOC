# AI-SOC frontend

Next.js App Router UI for the AI-SOC dashboard. The FastAPI backend is a separate application. `GET /health` drives the header connection indicator. Response Center, persisted incident detail, audit history, and HTML report download call live APIs. Overview, event explorer, the incidents list, and dashboard metrics still use Phase 2 mock data.

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

`/api/analyst` is disabled when `NODE_ENV=production` because there is no login session. That shared-token proxy is not per-user authentication.

## Data

| Screen | Source |
|--------|--------|
| Overview, event explorer, incidents list, dashboard metrics | Phase 2 mock (`src/lib/data.ts`) |
| `/incidents/[id]` | Live `GET /api/incidents/{id}` for title/severity/status/summary/event IDs/actions. Root-cause, ATT&CK, and event timeline only if a mock snapshot exists for that ID. |
| `/response`, report download, audit history | Live APIs via `/api/analyst` in development/test |
| `/investigations/[id]` | Mock snapshot plus live SSE when the investigation exists on the API |

## Manual browser verification (no Playwright in this repo)

1. Start PostgreSQL, the FastAPI backend (`uvicorn` on port 8000), and `npm run dev`.
2. Load a scenario, run detection, investigate, then open `/response`.
3. Open a persisted incident from the Response Center, approve or reject one simulated recommendation, and confirm the audit event.
4. Download the HTML report and check the filename, simulated-action disclaimer, and that scripts are absent.
5. With `NODE_ENV=production` (or `next start` after `npm run build`), confirm `/api/analyst/...` returns 403.
