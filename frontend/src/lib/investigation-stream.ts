import { API_BASE_URL } from "@/lib/constants";
import type { AgentName, AgentRun, AgentRunStatus } from "@/lib/types";

export type StreamEventName =
  | "connected"
  | "node_started"
  | "node_completed"
  | "node_failed"
  | "investigation_completed"
  | "investigation_failed";

export type InvestigationProgressPayload = {
  investigation_id: string;
  event: StreamEventName;
  agent_name?: AgentName | null;
  status: AgentRunStatus | "connected";
  timestamp: string;
  error?: string | null;
};

export type StreamConnectionState =
  | "connecting"
  | "live"
  | "completed"
  | "failed"
  | "unavailable"
  | "error";

export function investigationStreamUrl(investigationId: string): string {
  const base = API_BASE_URL.replace(/\/$/, "");
  return `${base}/api/investigations/${investigationId}/stream`;
}

export function isTerminalStreamEvent(event: StreamEventName): boolean {
  return event === "investigation_completed" || event === "investigation_failed";
}

export function statusFromProgressEvent(
  event: StreamEventName,
): AgentRunStatus | null {
  if (event === "node_started") {
    return "running";
  }
  if (event === "node_completed") {
    return "completed";
  }
  if (event === "node_failed") {
    return "failed";
  }
  return null;
}

export function applyProgressEvent(
  agents: AgentRun[],
  payload: InvestigationProgressPayload,
): AgentRun[] {
  const nextStatus = statusFromProgressEvent(payload.event);
  if (!payload.agent_name || nextStatus === null) {
    return agents;
  }
  return agents.map((agent) => {
    if (agent.agent !== payload.agent_name) {
      return agent;
    }
    return {
      ...agent,
      status: nextStatus,
      startedAt:
        nextStatus === "running" ? payload.timestamp : agent.startedAt,
      completedAt:
        nextStatus === "completed" || nextStatus === "failed"
          ? payload.timestamp
          : agent.completedAt,
      error: payload.error ?? (nextStatus === "failed" ? agent.error : undefined),
    };
  });
}

export type InvestigationApiNode = {
  agent_name: AgentName;
  status: AgentRunStatus;
  started_at: string | null;
  completed_at: string | null;
  structured_output: Record<string, unknown>;
  error: string | null;
};

function asString(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

export function mergeApiNodes(agents: AgentRun[], nodes: InvestigationApiNode[]): AgentRun[] {
  const byName = new Map(nodes.map((node) => [node.agent_name, node]));
  return agents.map((agent) => {
    const node = byName.get(agent.agent);
    if (!node) {
      return agent;
    }
    const output = node.structured_output ?? {};
    const evidence = output.evidence_event_ids;
    return {
      ...agent,
      status: node.status,
      startedAt: node.started_at ?? agent.startedAt,
      completedAt: node.completed_at ?? agent.completedAt,
      finding: asString(output.finding, agent.finding),
      evidenceEventIds: Array.isArray(evidence)
        ? evidence.filter((item): item is string => typeof item === "string")
        : agent.evidenceEventIds,
      confidence:
        output.confidence === "low" ||
        output.confidence === "medium" ||
        output.confidence === "high"
          ? output.confidence
          : agent.confidence,
      reasoningSummary: asString(output.reasoning_summary, agent.reasoningSummary),
      recommendedNextStep: asString(output.recommended_next_step, agent.recommendedNextStep),
      error: node.error ?? undefined,
    };
  });
}
