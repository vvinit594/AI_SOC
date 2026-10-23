import { describe, expect, it } from "vitest";

import {
  applyProgressEvent,
  isTerminalStreamEvent,
  mergeApiNodes,
  statusFromProgressEvent,
  type InvestigationProgressPayload,
} from "@/lib/investigation-stream";
import type { AgentRun } from "@/lib/types";

const agents: AgentRun[] = [
  {
    agent: "investigation",
    status: "queued",
    finding: "",
    evidenceEventIds: [],
    confidence: "low",
    reasoningSummary: "",
    recommendedNextStep: "",
  },
  {
    agent: "threat_intelligence",
    status: "queued",
    finding: "",
    evidenceEventIds: [],
    confidence: "low",
    reasoningSummary: "",
    recommendedNextStep: "",
  },
  {
    agent: "analysis",
    status: "queued",
    finding: "",
    evidenceEventIds: [],
    confidence: "low",
    reasoningSummary: "",
    recommendedNextStep: "",
  },
  {
    agent: "response_planner",
    status: "queued",
    finding: "",
    evidenceEventIds: [],
    confidence: "low",
    reasoningSummary: "",
    recommendedNextStep: "",
  },
];

function event(
  name: InvestigationProgressPayload["event"],
  agent: InvestigationProgressPayload["agent_name"] = null,
): InvestigationProgressPayload {
  return {
    investigation_id: "inv-1",
    event: name,
    agent_name: agent,
    status: statusFromProgressEvent(name) ?? "connected",
    timestamp: "2026-10-23T12:00:00Z",
    error: name === "node_failed" ? "RuntimeError" : null,
  };
}

describe("investigation stream reducer", () => {
  it("ignores connection and workflow events for agent rows", () => {
    const next = applyProgressEvent(agents, event("connected"));
    expect(next.every((agent) => agent.status === "queued")).toBe(true);
    expect(applyProgressEvent(agents, event("investigation_completed"))).toEqual(agents);
  });

  it("applies started, completed, and failed in order", () => {
    const started = applyProgressEvent(agents, event("node_started", "investigation"));
    expect(started[0]?.status).toBe("running");
    const completed = applyProgressEvent(started, event("node_completed", "investigation"));
    expect(completed[0]?.status).toBe("completed");
    const failed = applyProgressEvent(started, event("node_failed", "analysis"));
    expect(failed[2]?.status).toBe("failed");
    expect(failed[2]?.error).toBe("RuntimeError");
  });

  it("does not mark other agents complete", () => {
    const next = applyProgressEvent(agents, event("node_completed", "investigation"));
    expect(next[1]?.status).toBe("queued");
    expect(next[2]?.status).toBe("queued");
  });

  it("treats investigation completed/failed as terminal", () => {
    expect(isTerminalStreamEvent("investigation_completed")).toBe(true);
    expect(isTerminalStreamEvent("investigation_failed")).toBe(true);
    expect(isTerminalStreamEvent("node_completed")).toBe(false);
  });

  it("merges persisted API nodes without fabricating findings", () => {
    const merged = mergeApiNodes(agents, [
      {
        agent_name: "investigation",
        status: "completed",
        started_at: "2026-10-23T12:00:00Z",
        completed_at: "2026-10-23T12:00:01Z",
        structured_output: { finding: "Loaded 13 evidence events." },
        error: null,
      },
    ]);
    expect(merged[0]?.status).toBe("completed");
    expect(merged[0]?.finding).toBe("Loaded 13 evidence events.");
    expect(merged[1]?.finding).toBe("");
  });
});
