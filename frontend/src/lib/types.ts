export type Severity = "critical" | "high" | "medium" | "low";

export type IncidentStatus =
  | "open"
  | "investigating"
  | "awaiting_approval"
  | "resolved"
  | "dismissed";

export type DemoScenario = "A" | "B" | "C";

export type QualitativeConfidence = "low" | "medium" | "high";

export type AgentName =
  | "investigation"
  | "threat_intelligence"
  | "analysis"
  | "response_planner";

export type AgentRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "waiting_for_approval";

export type ThreatIntelStatus = "ok" | "unavailable" | "unknown";

export type ActionStatus = "proposed" | "approved" | "rejected";

export type RiskLevel = "low" | "medium" | "high";

export type SecurityEvent = {
  id: string;
  timestamp: string;
  eventType: string;
  sourceIp?: string;
  destinationIp?: string;
  username?: string;
  hostname?: string;
  action?: string;
  source: string;
  rawMessage: string;
  scenario: DemoScenario;
};

export type SeverityReason = {
  ruleId: string;
  eventIds: string[];
  reason: string;
};

export type MitreMapping = {
  techniqueId: string;
  name: string;
  reason: string;
  evidenceEventIds: string[];
};

export type Incident = {
  id: string;
  title: string;
  severity: Severity;
  status: IncidentStatus;
  summary: string;
  createdAt: string;
  scenario: DemoScenario;
  ruleIds: string[];
  eventIds: string[];
  severityReasons: SeverityReason[];
  investigationId: string;
  mitreTechniques: MitreMapping[];
  rootCause: {
    hypothesis: string;
    uncertainty: string;
    confidence: QualitativeConfidence;
  };
};

export type AgentRun = {
  agent: AgentName;
  status: AgentRunStatus;
  startedAt?: string;
  completedAt?: string;
  finding: string;
  evidenceEventIds: string[];
  confidence: QualitativeConfidence;
  reasoningSummary: string;
  recommendedNextStep: string;
  error?: string;
};

export type ThreatIntelResult = {
  indicator: string;
  indicatorType: "ip";
  provider: string;
  status: ThreatIntelStatus;
  summary: string;
  lookedUpAt: string;
  source: string;
};

export type TimelineEntry = {
  timestamp: string;
  title: string;
  detail: string;
  eventId?: string;
};

export type Investigation = {
  id: string;
  incidentId: string;
  status: AgentRunStatus;
  agents: AgentRun[];
  threatIntel: ThreatIntelResult[];
  timeline: TimelineEntry[];
};

export type ResponseAction = {
  id: string;
  incidentId: string;
  actionType: string;
  target: string;
  reason: string;
  evidenceIds: string[];
  riskLevel: RiskLevel;
  approvalRequired: boolean;
  status: ActionStatus;
  simulated: true;
  decidedAt?: string;
  decidedBy?: string;
};

export type IncidentReport = {
  id: string;
  incidentId: string;
  title: string;
  generatedAt: string;
  format: "html";
};

export type DashboardMetrics = {
  totalIncidents: number;
  openIncidents: number;
  criticalAndHigh: number;
  awaitingApproval: number;
};
