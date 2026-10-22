export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME ?? "AI-SOC";

/** FastAPI origin. Unused in Phase 2 — wired in Phase 3. */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const DATA_MODE = "mock" as const;
