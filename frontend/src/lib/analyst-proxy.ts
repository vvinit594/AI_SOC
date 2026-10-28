const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export const ANALYST_PROXY_TIMEOUT_MS = 20_000;

export type AnalystProxyTarget =
  | { kind: "action"; actionId: string; decision: "approve" | "reject" }
  | { kind: "audit"; incidentId: string }
  | { kind: "report"; incidentId: string };

export function isAnalystProxyAllowed(nodeEnv: string | undefined = process.env.NODE_ENV): boolean {
  return nodeEnv !== "production";
}

export function isUuid(value: string): boolean {
  return UUID_RE.test(value);
}

export function matchAnalystProxyPath(
  segments: string[],
  method: string,
): AnalystProxyTarget | null {
  const verb = method.toUpperCase();
  if (segments.some((part) => part === ".." || part.includes("/") || part.includes("\\"))) {
    return null;
  }
  if (
    verb === "POST" &&
    segments.length === 3 &&
    segments[0] === "actions" &&
    isUuid(segments[1] ?? "") &&
    (segments[2] === "approve" || segments[2] === "reject")
  ) {
    return { kind: "action", actionId: segments[1] ?? "", decision: segments[2] };
  }
  if (
    verb === "GET" &&
    segments.length === 3 &&
    segments[0] === "incidents" &&
    isUuid(segments[1] ?? "") &&
    segments[2] === "audit-logs"
  ) {
    return { kind: "audit", incidentId: segments[1] ?? "" };
  }
  if (
    verb === "GET" &&
    segments.length === 3 &&
    segments[0] === "incidents" &&
    isUuid(segments[1] ?? "") &&
    segments[2] === "report"
  ) {
    return { kind: "report", incidentId: segments[1] ?? "" };
  }
  return null;
}

export function upstreamPath(target: AnalystProxyTarget): string {
  if (target.kind === "action") {
    return `/api/actions/${target.actionId}/${target.decision}`;
  }
  if (target.kind === "audit") {
    return `/api/incidents/${target.incidentId}/audit-logs`;
  }
  return `/api/incidents/${target.incidentId}/report`;
}

export function analystProxyUrl(fastApiPath: string): string {
  const suffix = fastApiPath.startsWith("/api") ? fastApiPath.slice(4) : fastApiPath;
  return `/api/analyst${suffix.startsWith("/") ? suffix : `/${suffix}`}`;
}

export function parseBoundedInt(
  raw: string | null,
  fallback: number,
  min: number,
  max: number,
): number {
  if (raw === null || raw === "") {
    return fallback;
  }
  const value = Number.parseInt(raw, 10);
  if (!Number.isFinite(value)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, value));
}

export function isAbortError(error: unknown): boolean {
  return (
    (typeof DOMException !== "undefined" &&
      error instanceof DOMException &&
      error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  );
}

export function jsonError(
  status: number,
  detail: string,
  code = "http_error",
): Response {
  return Response.json(
    { error: code === "not_found" ? "not_found" : "http_error", detail, code },
    { status },
  );
}
