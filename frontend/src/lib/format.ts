import type { AgentName, IncidentStatus, Severity } from "@/lib/types";

const utcDateTime = new Intl.DateTimeFormat("en-GB", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "UTC",
});

export function formatUtc(iso: string): string {
  return `${utcDateTime.format(new Date(iso))} UTC`;
}

export function shortId(id: string, prefix = 8): string {
  return id.slice(0, prefix);
}

export function severityLabel(severity: Severity): string {
  return severity.charAt(0).toUpperCase() + severity.slice(1);
}

export function statusLabel(status: IncidentStatus): string {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export const AGENT_LABELS: Record<AgentName, string> = {
  investigation: "Investigation Agent",
  threat_intelligence: "Threat Intelligence Agent",
  analysis: "Analysis Agent",
  response_planner: "Response Planner",
};
