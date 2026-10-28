import { afterEach, describe, expect, it, vi } from "vitest";

import {
  approveAction,
  downloadIncidentReport,
  getIncidentApi,
  listIncidentAuditLogs,
  listIncidentsApi,
  rejectAction,
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

  it("approves through POST /api/actions/{id}/approve and uses the server body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, actionPayload));
    vi.stubGlobal("fetch", fetchMock);
    const result = await approveAction(ACTION_ID);
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/actions/${ACTION_ID}/approve`,
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
      `${API_BASE_URL}/api/actions/${ACTION_ID}/reject`,
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
      `${API_BASE_URL}/api/incidents/${INCIDENT_ID}/audit-logs`,
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
      `${API_BASE_URL}/api/incidents/${INCIDENT_ID}/report`,
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
});
