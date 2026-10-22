export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME ?? "AI-SOC";

/** FastAPI origin. Used by `src/lib/api.ts` for health and later API calls. */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const DATA_MODE = "mock" as const;
