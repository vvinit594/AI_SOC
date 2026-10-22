# AI-SOC frontend

Next.js App Router UI for the AI-SOC dashboard. The FastAPI backend is a separate application. This package calls `GET /health` for the dashboard connection indicator. Incident records still come from mock data until Phase 5.

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
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | FastAPI origin used by `src/lib/api.ts` |
| `NEXT_PUBLIC_APP_NAME` | `AI-SOC` | Header product name |

## Data

Pages still read incidents and events from `src/lib/data.ts` → `src/lib/mock-data.ts`. The only live backend call in Phase 3 is `getHealth()` from `src/lib/api.ts`. Mock records cover the three frozen demo scenarios (brute-force, suspicious outbound, benign).
