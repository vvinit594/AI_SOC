# AI-SOC frontend

Next.js App Router UI for the AI-SOC dashboard. The FastAPI backend is a separate application; this package talks to it over REST and SSE once Phase 3+ is in place.

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
```

## Environment

See `../docs/environment.md`. Only `NEXT_PUBLIC_*` variables belong here; they are not secrets.

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | FastAPI origin (used from Phase 3) |
| `NEXT_PUBLIC_APP_NAME` | `AI-SOC` | Header product name |

## Data in Phase 2

Pages read from `src/lib/data.ts`, which currently returns `src/lib/mock-data.ts`. Do not call FastAPI from UI components yet. Mock records cover the three frozen demo scenarios (brute-force, suspicious outbound, benign).
