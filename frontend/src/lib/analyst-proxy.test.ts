import { afterEach, describe, expect, it, vi } from "vitest";

import { GET, POST } from "@/app/api/analyst/[...path]/route";
import {
  analystProxyUrl,
  isAbortError,
  isAnalystProxyAllowed,
  isUuid,
  matchAnalystProxyPath,
  parseBoundedInt,
  sanitizeUpstreamDetail,
  upstreamPath,
} from "@/lib/analyst-proxy";

const ACTION_ID = "11111111-1111-4111-8111-111111111111";
const INCIDENT_ID = "a1e0c3f2-4b91-4d2a-9c18-11b0a0b7e001";
const SECRET = "server-only-analyst-token";

function context(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

function jsonResponse(status: number, body: unknown, extra?: HeadersInit): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...extra },
  });
}

describe("analyst proxy allowlist", () => {
  it("allows only the four protected analyst operations", () => {
    expect(matchAnalystProxyPath(["actions", ACTION_ID, "approve"], "POST")).toEqual({
      kind: "action",
      actionId: ACTION_ID,
      decision: "approve",
    });
    expect(matchAnalystProxyPath(["actions", ACTION_ID, "reject"], "POST")).toEqual({
      kind: "action",
      actionId: ACTION_ID,
      decision: "reject",
    });
    expect(matchAnalystProxyPath(["incidents", INCIDENT_ID, "audit-logs"], "GET")).toEqual({
      kind: "audit",
      incidentId: INCIDENT_ID,
    });
    expect(matchAnalystProxyPath(["incidents", INCIDENT_ID, "report"], "GET")).toEqual({
      kind: "report",
      incidentId: INCIDENT_ID,
    });
  });

  it("rejects method mismatches, malformed UUIDs, and open-proxy paths", () => {
    expect(matchAnalystProxyPath(["actions", ACTION_ID, "approve"], "GET")).toBeNull();
    expect(matchAnalystProxyPath(["incidents", INCIDENT_ID, "report"], "POST")).toBeNull();
    expect(matchAnalystProxyPath(["actions", "not-a-uuid", "approve"], "POST")).toBeNull();
    expect(matchAnalystProxyPath(["incidents", INCIDENT_ID, "detect"], "GET")).toBeNull();
    expect(matchAnalystProxyPath(["http:", "", "evil.example", "secret"], "GET")).toBeNull();
    expect(matchAnalystProxyPath(["..", "etc", "passwd"], "GET")).toBeNull();
    expect(matchAnalystProxyPath(["actions", ACTION_ID, "approve", "extra"], "POST")).toBeNull();
  });

  it("builds same-origin proxy URLs and bounded query integers", () => {
    expect(analystProxyUrl(`/api/actions/${ACTION_ID}/approve`)).toBe(
      `/api/analyst/actions/${ACTION_ID}/approve`,
    );
    expect(upstreamPath({ kind: "report", incidentId: INCIDENT_ID })).toBe(
      `/api/incidents/${INCIDENT_ID}/report`,
    );
    expect(parseBoundedInt("12", 100, 1, 500)).toBe(12);
    expect(parseBoundedInt("9999", 100, 1, 500)).toBe(500);
    expect(parseBoundedInt("nope", 100, 1, 500)).toBe(100);
    expect(isUuid(ACTION_ID)).toBe(true);
    expect(isUuid("abcd")).toBe(false);
  });

  it("disables the proxy in production and allows development/test", () => {
    expect(isAnalystProxyAllowed("production")).toBe(false);
    expect(isAnalystProxyAllowed("development")).toBe(true);
    expect(isAnalystProxyAllowed("test")).toBe(true);
  });

  it("detects abort errors from DOMException or Error", () => {
    expect(isAbortError(new DOMException("Aborted", "AbortError"))).toBe(true);
    expect(isAbortError(Object.assign(new Error("Aborted"), { name: "AbortError" }))).toBe(true);
    expect(isAbortError(new Error("failed"))).toBe(false);
  });

  it("preserves safe client errors and strips secret-bearing or 5xx details", () => {
    const fallback = "Request failed with status 401";
    expect(sanitizeUpstreamDetail(401, "Invalid or missing analyst token", fallback)).toBe(
      "Invalid or missing analyst token",
    );
    expect(sanitizeUpstreamDetail(404, "Incident not found", "Request failed with status 404")).toBe(
      "Incident not found",
    );
    expect(
      sanitizeUpstreamDetail(409, "Action already approved", "Request failed with status 409"),
    ).toBe("Action already approved");
    expect(sanitizeUpstreamDetail(401, "token=short-secret", fallback)).toBe(fallback);
    expect(
      sanitizeUpstreamDetail(500, "database connection failed", "Request failed with status 500"),
    ).toBe("Request failed with status 500");
  });
});

describe("analyst proxy route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("returns 403 in production without forwarding upstream", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("ANALYST_API_TOKEN", SECRET);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const request = new Request(`http://localhost:3000/api/analyst/actions/${ACTION_ID}/approve`, {
      method: "POST",
    });
    const response = await POST(request, context(["actions", ACTION_ID, "approve"]));
    expect(response.status).toBe(403);
    const body = (await response.json()) as { code: string; detail: string };
    expect(body.code).toBe("analyst_proxy_disabled");
    expect(body.detail.toLowerCase()).toContain("no authenticated user session");
    expect(JSON.stringify(body)).not.toContain(SECRET);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("injects the server token and ignores a client Authorization header", async () => {
    vi.stubEnv("NODE_ENV", "test");
    vi.stubEnv("ANALYST_API_TOKEN", SECRET);
    vi.stubEnv("API_UPSTREAM_URL", "http://upstream.test");
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, { id: ACTION_ID, approval_status: "approved", simulated: true }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const request = new Request(`http://localhost:3000/api/analyst/actions/${ACTION_ID}/approve`, {
      method: "POST",
      headers: { Authorization: "Bearer client-forged-token" },
    });
    const response = await POST(request, context(["actions", ACTION_ID, "approve"]));
    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `http://upstream.test/api/actions/${ACTION_ID}/approve`,
    );
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>;
    expect(headers.Authorization).toBe(`Bearer ${SECRET}`);
    expect(headers.Authorization).not.toContain("client-forged-token");
  });

  it("does not log the analyst token", async () => {
    vi.stubEnv("ANALYST_API_TOKEN", SECRET);
    vi.stubEnv("API_UPSTREAM_URL", "http://upstream.test");
    const info = vi.spyOn(console, "info").mockImplementation(() => undefined);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(401, { detail: "Invalid or missing analyst token" })),
    );
    const request = new Request(
      `http://localhost:3000/api/analyst/incidents/${INCIDENT_ID}/audit-logs`,
    );
    const response = await GET(request, context(["incidents", INCIDENT_ID, "audit-logs"]));
    expect(response.status).toBe(401);
    const logged = info.mock.calls.map((call) => call.map(String).join(" ")).join("\n");
    expect(logged).not.toContain(SECRET);
    expect(logged).not.toContain("Authorization");
  });

  it("rejects unknown proxy paths instead of forwarding them", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const request = new Request("http://localhost:3000/api/analyst/incidents/detect", {
      method: "POST",
    });
    const response = await POST(request, context(["incidents", "detect"]));
    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sanitizes long secret-like upstream error details", async () => {
    vi.stubEnv("API_UPSTREAM_URL", "http://upstream.test");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(500, {
          detail: `token=${SECRET} password=super-secret-database-url-should-not-leak-to-browser`,
        }),
      ),
    );
    const request = new Request(
      `http://localhost:3000/api/analyst/incidents/${INCIDENT_ID}/audit-logs`,
    );
    const response = await GET(request, context(["incidents", INCIDENT_ID, "audit-logs"]));
    const body = (await response.json()) as { detail: string };
    expect(response.status).toBe(500);
    expect(body.detail).toBe("Request failed with status 500");
    expect(body.detail).not.toContain(SECRET);
    expect(body.detail).not.toContain("super-secret-database");
  });

  it("sanitizes short secret-bearing 401 details without dropping a safe 401", async () => {
    vi.stubEnv("API_UPSTREAM_URL", "http://upstream.test");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(401, { detail: "token=abc" })));
    const secretResponse = await GET(
      new Request(`http://localhost:3000/api/analyst/incidents/${INCIDENT_ID}/audit-logs`),
      context(["incidents", INCIDENT_ID, "audit-logs"]),
    );
    expect(secretResponse.status).toBe(401);
    expect(((await secretResponse.json()) as { detail: string }).detail).toBe(
      "Request failed with status 401",
    );

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(401, { detail: "Invalid or missing analyst token" })),
    );
    const safeResponse = await GET(
      new Request(`http://localhost:3000/api/analyst/incidents/${INCIDENT_ID}/audit-logs`),
      context(["incidents", INCIDENT_ID, "audit-logs"]),
    );
    expect(safeResponse.status).toBe(401);
    expect(((await safeResponse.json()) as { detail: string }).detail).toBe(
      "Invalid or missing analyst token",
    );
  });

  it("preserves 404 and 409 details used by the UI", async () => {
    vi.stubEnv("API_UPSTREAM_URL", "http://upstream.test");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(409, { detail: "Action already approved" })),
    );
    const conflict = await POST(
      new Request(`http://localhost:3000/api/analyst/actions/${ACTION_ID}/reject`, {
        method: "POST",
      }),
      context(["actions", ACTION_ID, "reject"]),
    );
    expect(conflict.status).toBe(409);
    expect(((await conflict.json()) as { detail: string }).detail).toBe("Action already approved");
  });

  it("does not forward malformed JSON or unexpected content types", async () => {
    vi.stubEnv("API_UPSTREAM_URL", "http://upstream.test");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("{not-json token=leaked}", {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const malformed = await GET(
      new Request(`http://localhost:3000/api/analyst/incidents/${INCIDENT_ID}/audit-logs`),
      context(["incidents", INCIDENT_ID, "audit-logs"]),
    );
    const malformedBody = (await malformed.json()) as { detail: string };
    expect(malformed.status).toBe(502);
    expect(malformedBody.detail).not.toContain("leaked");
    expect(malformedBody.detail).not.toContain("token=");

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>not json</html>", {
          status: 200,
          headers: { "Content-Type": "text/html" },
        }),
      ),
    );
    const unexpected = await POST(
      new Request(`http://localhost:3000/api/analyst/actions/${ACTION_ID}/approve`, {
        method: "POST",
      }),
      context(["actions", ACTION_ID, "approve"]),
    );
    expect(unexpected.status).toBe(502);
    expect(((await unexpected.json()) as { detail: string }).detail).toBe(
      "Unexpected upstream content type",
    );
  });

  it("forwards HTML reports with a sanitized filename", async () => {
    vi.stubEnv("API_UPSTREAM_URL", "http://upstream.test");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<!DOCTYPE html><html><body>ok</body></html>", {
          status: 200,
          headers: {
            "Content-Type": "text/html; charset=utf-8",
            "Content-Disposition": 'attachment; filename="../../evil.html"',
          },
        }),
      ),
    );
    const request = new Request(
      `http://localhost:3000/api/analyst/incidents/${INCIDENT_ID}/report`,
    );
    const response = await GET(request, context(["incidents", INCIDENT_ID, "report"]));
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/html");
    expect(response.headers.get("content-disposition")).toBe(
      `attachment; filename="incident-${INCIDENT_ID}-report.html"`,
    );
    expect(await response.text()).toContain("<!DOCTYPE html>");
  });

  it("returns 504 when the upstream request times out", async () => {
    vi.stubEnv("API_UPSTREAM_URL", "http://upstream.test");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new DOMException("Aborted", "AbortError")),
    );
    const request = new Request(`http://localhost:3000/api/analyst/actions/${ACTION_ID}/reject`, {
      method: "POST",
    });
    const response = await POST(request, context(["actions", ACTION_ID, "reject"]));
    expect(response.status).toBe(504);
  });
});
