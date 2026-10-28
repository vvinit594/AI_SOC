import type {
  ActionStatus,
  AuditLogEntry,
  ExecutionStatus,
  IncidentStatus,
  PersistedIncident,
  ResponseAction,
  RiskLevel,
  Severity,
} from "@/lib/types";

export type ResponseActionApi = {
  id: string;
  incident_id: string;
  action_type: string;
  target: string | null;
  reason: string;
  risk_level: RiskLevel;
  approval_status: ActionStatus;
  execution_status: ExecutionStatus;
  simulated: boolean;
  created_at: string;
  decided_at: string | null;
  actor: string | null;
};

export type ActionDecisionApi = ResponseActionApi & {
  incident_status: IncidentStatus;
};

export type IncidentApiItem = {
  id: string;
  title: string;
  severity: Severity;
  status: IncidentStatus;
  summary: string;
  scenario: string | null;
  created_at: string;
  event_ids: string[];
  actions?: ResponseActionApi[];
};

export type IncidentListApi = {
  items: IncidentApiItem[];
  total: number;
};

export type AuditLogApi = {
  id: string;
  occurred_at: string;
  event_type: string;
  actor: string;
  resource_type: string;
  resource_id: string;
  incident_id: string | null;
  details: Record<string, unknown>;
};

export type AuditLogListApi = {
  items: AuditLogApi[];
  total: number;
};

export function mapResponseAction(row: ResponseActionApi): ResponseAction {
  return {
    id: row.id,
    incidentId: row.incident_id,
    actionType: row.action_type,
    target: row.target,
    reason: row.reason,
    riskLevel: row.risk_level,
    approvalStatus: row.approval_status,
    executionStatus: row.execution_status,
    simulated: row.simulated,
    createdAt: row.created_at,
    decidedAt: row.decided_at,
    actor: row.actor,
  };
}

export function mapIncident(row: IncidentApiItem): PersistedIncident {
  return {
    id: row.id,
    title: row.title,
    severity: row.severity,
    status: row.status,
    summary: row.summary,
    scenario: row.scenario,
    createdAt: row.created_at,
    eventIds: row.event_ids,
    actions: (row.actions ?? []).map(mapResponseAction),
  };
}

export function mapAuditLog(row: AuditLogApi): AuditLogEntry {
  return {
    id: row.id,
    occurredAt: row.occurred_at,
    eventType: row.event_type,
    actor: row.actor,
    resourceType: row.resource_type,
    resourceId: row.resource_id,
    incidentId: row.incident_id,
    details: row.details ?? {},
  };
}

export function replaceIncidentAction(
  incidents: PersistedIncident[],
  action: ResponseAction,
  incidentStatus?: IncidentStatus,
): PersistedIncident[] {
  return incidents.map((incident) => {
    if (incident.id !== action.incidentId) {
      return incident;
    }
    return {
      ...incident,
      status: incidentStatus ?? incident.status,
      actions: incident.actions.map((item) => (item.id === action.id ? action : item)),
    };
  });
}

export function containmentLabel(action: Pick<ResponseAction, "executionStatus" | "simulated">): string {
  if (action.simulated || action.executionStatus === "not_executed" || action.executionStatus === "simulated") {
    return "Not performed (simulated recommendation only)";
  }
  if (action.executionStatus === "failed") {
    return "Recorded execution attempt failed; no successful containment";
  }
  return `Recorded status ${action.executionStatus}. Not treated as live containment.`;
}

export function claimsLiveExecution(text: string): boolean {
  return /\b(was|were|has been|have been|successfully)\s+executed\b/i.test(text);
}

export function actionTypeLabel(actionType: string): string {
  return actionType.replaceAll("_", " ");
}
