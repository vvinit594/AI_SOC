import { describe, expect, it } from "vitest";

import {
  claimsLiveExecution,
  containmentLabel,
  mapIncident,
  mapResponseAction,
  replaceIncidentAction,
  type IncidentApiItem,
  type ResponseActionApi,
} from "@/lib/actions";
import type { PersistedIncident } from "@/lib/types";

const actionApi: ResponseActionApi = {
  id: "11111111-1111-4111-8111-111111111111",
  incident_id: "22222222-2222-4222-8222-222222222222",
  action_type: "force_password_reset",
  target: "demo_user",
  reason: "fixture",
  risk_level: "high",
  approval_status: "proposed",
  execution_status: "not_executed",
  simulated: true,
  created_at: "2026-10-21T10:22:00Z",
  decided_at: null,
  actor: null,
};

describe("response action mapping", () => {
  it("maps API actions into the UI model", () => {
    const action = mapResponseAction(actionApi);
    expect(action.approvalStatus).toBe("proposed");
    expect(action.executionStatus).toBe("not_executed");
    expect(action.simulated).toBe(true);
    expect(action.incidentId).toBe(actionApi.incident_id);
  });

  it("maps incidents including nested actions", () => {
    const row: IncidentApiItem = {
      id: actionApi.incident_id,
      title: "Brute force",
      severity: "high",
      status: "awaiting_approval",
      summary: "R1",
      scenario: "A",
      created_at: "2026-10-21T10:22:00Z",
      event_ids: [],
      actions: [actionApi],
    };
    const incident = mapIncident(row);
    expect(incident.actions).toHaveLength(1);
    expect(incident.actions[0]?.actionType).toBe("force_password_reset");
  });

  it("replaces one action without implying siblings were decided", () => {
    const incident: PersistedIncident = mapIncident({
      id: actionApi.incident_id,
      title: "Brute force",
      severity: "high",
      status: "awaiting_approval",
      summary: "R1",
      scenario: "A",
      created_at: "2026-10-21T10:22:00Z",
      event_ids: [],
      actions: [
        actionApi,
        { ...actionApi, id: "33333333-3333-4333-8333-333333333333", action_type: "flag_ip_for_review" },
      ],
    });
    const decided = mapResponseAction({
      ...actionApi,
      approval_status: "approved",
      actor: "unverified",
      decided_at: "2026-10-21T11:00:00Z",
    });
    const next = replaceIncidentAction([incident], decided, "awaiting_approval");
    expect(next[0]?.status).toBe("awaiting_approval");
    expect(next[0]?.actions[0]?.approvalStatus).toBe("approved");
    expect(next[0]?.actions[1]?.approvalStatus).toBe("proposed");
  });
});

describe("containment labelling", () => {
  it("never describes simulated or unexecuted actions as executed", () => {
    const label = containmentLabel({
      executionStatus: "not_executed",
      simulated: true,
    });
    expect(label.toLowerCase()).toContain("not performed");
    expect(label.toLowerCase()).toContain("simulated");
    expect(claimsLiveExecution(label)).toBe(false);
    expect(label.toLowerCase().replaceAll("not_executed", "")).not.toContain("executed");
  });

  it("does not treat a failed attempt as successful containment", () => {
    const label = containmentLabel({
      executionStatus: "failed",
      simulated: false,
    });
    expect(label.toLowerCase()).toContain("failed");
    expect(claimsLiveExecution(label)).toBe(false);
  });
});
