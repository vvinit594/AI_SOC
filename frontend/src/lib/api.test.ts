import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approveAction,
  detectIncidents,
  downloadIncidentReport,
  getIncidentApi,
  IngestApiError,
  listEventsApi,
  listEventsPage,
  listIncidentAuditLogs,
  listIncidentSummaries,
  listIncidentsApi,
  rejectAction,
  uploadLogs,
} from "@/lib/api";
import { API_BASE_URL } from "@/lib/constants";

const INCIDENT_ID = "a1e0c3f2-4b91-4d2a-9c18-11b0a0b7e001";
const ACTION_ID = "11111111-1111-4111-8111-111111111111";

const actionPayload = {
  id: ACTION_ID,
  incident_id: INCIDENT_ID,
  action_type: "force_password_reset",
  target: "demo_user",
  reason: "fixture",
  risk_level: "high",
  approval_status: "approved",
  execution_status: "not_executed",
  simulated: true,
  created_at: "2026-10-21T10:22:00Z",
  decided_at: "2026-10-21T11:00:00Z",
  actor: "unverified",
  incident_status: "awaiting_approval",
};

const incidentPayload = {
  id: INCIDENT_ID,
  title: "Brute-force login",
  severity: "critical",
  status: "awaiting_approval",
  summary: "R1 R2",
  scenario: "A",
  created_at: "2026-10-21T10:22:00Z",
  event_ids: [],
  actions: [{ ...actionPayload, approval_status: "proposed", decided_at: null, actor: null }],
};

function jsonResponse(status: number, body: unknown, extraHeaders?: Record<string, string>): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...extraHeaders },
  });
}

function htmlResponse(status: number, body: string, extraHeaders?: Record<string, string>): Response {
  return new Response(body, {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8", ...extraHeaders },
  });
}

describe("response and report API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("loads incident summaries from the list endpoint only", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { items: [incidentPayload], total: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    const incidents = await listIncidentSummaries();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(incidents).toHaveLength(1);
    expect(incidents[0]?.title).toBe("Brute-force login");
  });

  it("maps persisted events without filling missing threat intel", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        total: 1,
        items: [
          {
            id: "e0a10001-0001-4a11-8c01-000000000001",
            timestamp: "2026-10-21T10:15:00Z",
            event_type: "login_failure",
            source_ip: "192.0.2.10",
            destination_ip: null,
            username: "demo_user",
            hostname: "demo-server-01",
            action: "authentication_failed",
            source: "linux_auth",
            raw_message: "Failed password",
            scenario: "A",
            created_at: "2026-10-21T10:15:00Z",
          },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const events = await listEventsApi();
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `${API_BASE_URL}/api/events?limit=500&offset=0`,
    );
    expect(events[0]?.eventType).toBe("login_failure");
    expect(events[0]?.destinationIp).toBeUndefined();
  });

  it("pages events with limit and offset from the existing list API", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { items: [], total: 28 })),
    );
    const page = await listEventsPage({ limit: 50, offset: 50, eventType: "login_failure", scenario: "A" });
    expect(page.total).toBe(28);
    const called = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0]?.[0] as string;
    expect(called).toContain("limit=50");
    expect(called).toContain("offset=50");
    expect(called).toContain("event_type=login_failure");
    expect(called).toContain("scenario=A");
  });

  it("loads incidents from the persisted list and detail endpoints", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, { items: [incidentPayload], total: 1 }))
      .mockResolvedValueOnce(jsonResponse(200, incidentPayload));
    vi.stubGlobal("fetch", fetchMock);

    const incidents = await listIncidentsApi();
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/incidents`,
      expect.objectContaining({ method: "GET" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/incidents/${INCIDENT_ID}`,
      expect.objectContaining({ method: "GET" }),
    );
    expect(incidents).toHaveLength(1);
    expect(incidents[0]?.actions[0]?.approvalStatus).toBe("proposed");
    expect(incidents[0]?.actions[0]?.executionStatus).toBe("not_executed");
  });

  it("approves through the same-origin analyst proxy and uses the server body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, actionPayload));
    vi.stubGlobal("fetch", fetchMock);
    const result = await approveAction(ACTION_ID);
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/analyst/actions/${ACTION_ID}/approve`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.approval_status).toBe("approved");
    expect(result.execution_status).toBe("not_executed");
    expect(result.simulated).toBe(true);
  });

  it("rejects through POST /api/actions/{id}/reject", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, { ...actionPayload, approval_status: "rejected" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await rejectAction(ACTION_ID);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `/api/analyst/actions/${ACTION_ID}/reject`,
    );
    expect(result.approval_status).toBe("rejected");
  });

  it("maps 401, 403, 404, and 409 from action endpoints", async () => {
    const cases = [
      [401, "Invalid or missing analyst token"],
      [403, "ANALYST_API_TOKEN is required in production"],
      [404, "Action not found"],
      [409, "Action already has a conflicting decision"],
    ] as const;
    for (const [status, detail] of cases) {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(jsonResponse(status, { error: "http_error", detail, code: "http_error" })),
      );
      await expect(approveAction(ACTION_ID)).rejects.toMatchObject({ status, message: detail });
      vi.unstubAllGlobals();
    }
  });

  it("maps network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));
    await expect(getIncidentApi(INCIDENT_ID)).rejects.toMatchObject({
      status: 0,
      code: "network_error",
    });
  });

  it("renders audit history from persisted entries", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        total: 1,
        items: [
          {
            id: "44444444-4444-4444-8444-444444444444",
            occurred_at: "2026-10-21T11:00:00Z",
            event_type: "response_action.approved",
            actor: "unverified",
            resource_type: "response_action",
            resource_id: ACTION_ID,
            incident_id: INCIDENT_ID,
            details: { decision: "approved" },
          },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const items = await listIncidentAuditLogs(INCIDENT_ID);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `/api/analyst/incidents/${INCIDENT_ID}/audit-logs`,
    );
    expect(items).toHaveLength(1);
    expect(items[0]?.eventType).toBe("response_action.approved");
    expect(items[0]?.actor).toBe("unverified");
  });

  it("treats an empty audit list as empty, not fabricated history", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, { items: [], total: 0 })));
    await expect(listIncidentAuditLogs(INCIDENT_ID)).resolves.toEqual([]);
  });

  it("downloads HTML from the incident report endpoint and keeps the server filename", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      htmlResponse(200, "<!DOCTYPE html><html><body>ok</body></html>", {
        "Content-Disposition": `attachment; filename="incident-${INCIDENT_ID}-report.html"`,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const report = await downloadIncidentReport(INCIDENT_ID);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      `/api/analyst/incidents/${INCIDENT_ID}/report`,
    );
    expect(report.filename).toBe(`incident-${INCIDENT_ID}-report.html`);
    expect(report.contentType).toContain("text/html");
    expect(await report.blob.text()).toContain("<!DOCTYPE html>");
  });

  it("uses a safe fallback filename when Content-Disposition is missing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(htmlResponse(200, "<html></html>")),
    );
    const report = await downloadIncidentReport(INCIDENT_ID);
    expect(report.filename).toBe(`incident-${INCIDENT_ID}-report.html`);
  });

  it("does not treat a JSON error body as an HTML report", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(404, { error: "not_found", detail: "Incident not found", code: "not_found" }),
      ),
    );
    await expect(downloadIncidentReport(INCIDENT_ID)).rejects.toMatchObject({
      status: 404,
      message: "Incident not found",
    });
  });

  it("rejects a successful non-HTML payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, { not: "html" }, { "Content-Type": "application/json" }),
      ),
    );
    await expect(downloadIncidentReport(INCIDENT_ID)).rejects.toMatchObject({
      code: "unexpected_content_type",
    });
  });

  it("propagates aborted requests", async () => {
    const abort = Object.assign(new Error("Aborted"), { name: "AbortError" });
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(abort));
    await expect(listIncidentAuditLogs(INCIDENT_ID)).rejects.toMatchObject({
      name: "AbortError",
    });
  });

  it("treats malformed JSON error bodies as a status failure without leaking secrets", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("{not-json ANALYST_API_TOKEN=leaked}", {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await expect(approveAction(ACTION_ID)).rejects.toMatchObject({
      status: 500,
      message: "Request failed with status 500",
    });
  });

  it("keeps public incident reads on the FastAPI origin", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, incidentPayload));
    vi.stubGlobal("fetch", fetchMock);
    await getIncidentApi(INCIDENT_ID);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`${API_BASE_URL}/api/incidents/${INCIDENT_ID}`);
  });
});

describe("log upload and detection client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("posts JSON as multipart field file", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, { accepted: 1, rejected: 0, event_ids: ["e1"], errors: [] }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File([JSON.stringify([{ timestamp: "2026-10-21T12:00:00Z" }])], "events.json", {
      type: "application/json",
    });
    const result = await uploadLogs(file);
    expect(result.accepted).toBe(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`${API_BASE_URL}/api/logs/upload`);
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.body as FormData).get("file")).toBeInstanceOf(File);
    expect(init.headers).toEqual({ Accept: "application/json" });
  });

  it("posts CSV as multipart field file", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, { accepted: 1, rejected: 0, event_ids: ["e2"], errors: [] }),
      ),
    );
    const file = new File(["timestamp,event_type\n2026-10-21T12:00:00Z,login_success\n"], "events.csv", {
      type: "text/csv",
    });
    await expect(uploadLogs(file)).resolves.toMatchObject({ accepted: 1, rejected: 0 });
  });

  it("surfaces oversized uploads from the backend 413", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(413, {
          error: "http_error",
          detail: "Upload exceeds MAX_UPLOAD_SIZE_MB",
          code: "http_error",
        }),
      ),
    );
    const file = new File(["{}"], "events.json", { type: "application/json" });
    await expect(uploadLogs(file)).rejects.toMatchObject({
      status: 413,
      message: "Upload exceeds MAX_UPLOAD_SIZE_MB",
    });
  });

  it("returns partial ingestion without treating it as a hard failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, {
          accepted: 1,
          rejected: 1,
          event_ids: ["ok"],
          errors: [{ index: 1, detail: "timestamp: Input should be a valid datetime" }],
        }),
      ),
    );
    const result = await uploadLogs(new File(["[]"], "events.json", { type: "application/json" }));
    expect(result.accepted).toBe(1);
    expect(result.rejected).toBe(1);
    expect(result.errors[0]?.index).toBe(1);
  });

  it("keeps rejected record indexes when every row is invalid", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(400, {
          error: "ingest_error",
          detail: "No valid events in upload",
          code: "ingest_error",
          errors: [{ index: 0, detail: "timestamp: Field required" }],
        }),
      ),
    );
    const caught = uploadLogs(new File(["[]"], "events.json", { type: "application/json" }));
    await expect(caught).rejects.toBeInstanceOf(IngestApiError);
    await expect(caught).rejects.toMatchObject({
      status: 400,
      errors: [{ index: 0, detail: "timestamp: Field required" }],
    });
  });

  it("maps unsupported format failures from the backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(400, {
          error: "http_error",
          detail: "Unsupported file type; upload JSON or CSV",
          code: "http_error",
        }),
      ),
    );
    await expect(
      uploadLogs(new File(["hello"], "events.txt", { type: "text/plain" })),
    ).rejects.toMatchObject({
      status: 400,
      message: "Unsupported file type; upload JSON or CSV",
    });
  });

  it("maps network failures on upload", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));
    await expect(
      uploadLogs(new File(["{}"], "events.json", { type: "application/json" })),
    ).rejects.toMatchObject({ status: 0, code: "network_error" });
  });

  it("refreshes events from GET /api/events after a confirmed upload", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, { accepted: 1, rejected: 0, event_ids: ["e1"], errors: [] }),
      )
      .mockResolvedValueOnce(jsonResponse(200, { items: [], total: 1 }));
    vi.stubGlobal("fetch", fetchMock);
    await uploadLogs(new File(["{}"], "events.json", { type: "application/json" }));
    const page = await listEventsPage({ limit: 50, offset: 0 });
    expect(page.total).toBe(1);
    expect(fetchMock.mock.calls[1]?.[0]).toBe(`${API_BASE_URL}/api/events?limit=50&offset=0`);
  });

  it("posts detection only to POST /api/incidents/detect", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        matches: [
          {
            rule_id: "R1",
            severity: "high",
            event_ids: ["e1"],
            reason: "threshold",
            matched_threshold: "5",
            timestamp: "2026-10-21T12:00:00Z",
            incident_id: INCIDENT_ID,
          },
        ],
        incidents: [incidentPayload],
        created: 1,
        updated: 0,
        skipped: 0,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const result = await detectIncidents();
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/incidents/detect`,
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.created).toBe(1);
    expect(result.incidents[0]?.id).toBe(INCIDENT_ID);
    expect(result.matches[0]?.rule_id).toBe("R1");
  });

  it("maps detection failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(500, { error: "http_error", detail: "Database unavailable", code: "http_error" }),
      ),
    );
    await expect(detectIncidents()).rejects.toMatchObject({
      status: 500,
      message: "Database unavailable",
    });
  });
});
