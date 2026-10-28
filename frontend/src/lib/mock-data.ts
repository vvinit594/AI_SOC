/**
 * Phase 2 mock dataset.
 *
 * Synthetic, reproducible SOC data for the three frozen demo scenarios.
 * Uses RFC 5737 documentation IPs only. Nothing here is live threat intelligence.
 *
 * Phase 3+ will stop importing this module from the UI. Pages should go through
 * `@/lib/data` so the swap to FastAPI is localized.
 */

import type {
  DashboardMetrics,
  Incident,
  IncidentReport,
  Investigation,
  ResponseAction,
  SecurityEvent,
} from "@/lib/types";

export const MOCK_GENERATED_AT = "2026-10-21T10:22:00Z";

const EVENT = {
  bruteFailures: [
    "e0a10001-0001-4a11-8c01-000000000001",
    "e0a10001-0002-4a11-8c01-000000000002",
    "e0a10001-0003-4a11-8c01-000000000003",
    "e0a10001-0004-4a11-8c01-000000000004",
    "e0a10001-0005-4a11-8c01-000000000005",
    "e0a10001-0006-4a11-8c01-000000000006",
    "e0a10001-0007-4a11-8c01-000000000007",
    "e0a10001-0008-4a11-8c01-000000000008",
    "e0a10001-0009-4a11-8c01-000000000009",
    "e0a10001-0010-4a11-8c01-000000000010",
    "e0a10001-0011-4a11-8c01-000000000011",
    "e0a10001-0012-4a11-8c01-000000000012",
  ],
  bruteSuccess: "e0a10001-0013-4a11-8c01-000000000013",
  outbound: [
    "e0b20001-0001-4b22-8d01-000000000021",
    "e0b20001-0002-4b22-8d01-000000000022",
    "e0b20001-0003-4b22-8d01-000000000023",
    "e0b20001-0004-4b22-8d01-000000000024",
    "e0b20001-0005-4b22-8d01-000000000025",
    "e0b20001-0006-4b22-8d01-000000000026",
    "e0b20001-0007-4b22-8d01-000000000027",
    "e0b20001-0008-4b22-8d01-000000000028",
    "e0b20001-0009-4b22-8d01-000000000029",
    "e0b20001-0010-4b22-8d01-000000000030",
  ],
  benign: [
    "e0c30001-0001-4c33-8e01-000000000041",
    "e0c30001-0002-4c33-8e01-000000000042",
    "e0c30001-0003-4c33-8e01-000000000043",
    "e0c30001-0004-4c33-8e01-000000000044",
    "e0c30001-0005-4c33-8e01-000000000045",
  ],
} as const;

export const INCIDENT_IDS = {
  bruteForce: "a1e0c3f2-4b91-4d2a-9c18-11b0a0b7e001",
  outbound: "b2f1d4e3-5c02-4e3b-8d29-22c1b1c8e002",
  benign: "c3a2e5f4-6d13-4f4c-7e3a-33d2c2d9e003",
} as const;

export const INVESTIGATION_IDS = {
  bruteForce: "d4b3f6a5-7e24-405d-9f4b-44e3d3eae101",
  outbound: "e5c4a7b6-8f35-416e-8a5c-55f4e4fbf202",
  benign: "f6d5b8c7-9046-427f-7b6d-66a5f50c0303",
} as const;

function bruteFailureEvents(): SecurityEvent[] {
  return EVENT.bruteFailures.map((id, index) => {
    const minute = 15 + Math.floor(index / 4);
    const second = String((index * 7) % 60).padStart(2, "0");
    const timestamp = `2026-10-21T10:${String(minute).padStart(2, "0")}:${second}Z`;
    return {
      id,
      timestamp,
      eventType: "login_failure",
      sourceIp: "192.0.2.10",
      username: "demo_user",
      hostname: "demo-server-01",
      action: "authentication_failed",
      source: "linux_auth",
      rawMessage: `Failed password for demo_user from 192.0.2.10 port ${51200 + index} ssh2`,
      scenario: "A",
    };
  });
}

export const mockEvents: SecurityEvent[] = [
  ...bruteFailureEvents(),
  {
    id: EVENT.bruteSuccess,
    timestamp: "2026-10-21T10:19:48Z",
    eventType: "login_success",
    sourceIp: "192.0.2.10",
    username: "demo_user",
    hostname: "demo-server-01",
    action: "authentication_succeeded",
    source: "linux_auth",
    rawMessage: "Accepted password for demo_user from 192.0.2.10 port 51312 ssh2",
    scenario: "A",
  },
  ...EVENT.outbound.map((id, index) => ({
    id,
    timestamp: `2026-10-21T11:${String(2 + index).padStart(2, "0")}:14Z`,
    eventType: "outbound_connection",
    sourceIp: "192.0.2.50",
    destinationIp: "198.51.100.88",
    hostname: "demo-server-02",
    action: "connection_opened",
    source: "firewall",
    rawMessage: `Outbound TCP 192.0.2.50:44300 -> 198.51.100.88:443 (repeat ${index + 1}/10)`,
    scenario: "B" as const,
  })),
  {
    id: EVENT.benign[0],
    timestamp: "2026-10-21T08:01:12Z",
    eventType: "login_success",
    sourceIp: "192.0.2.40",
    username: "j.patel",
    hostname: "demo-workstation-04",
    action: "authentication_succeeded",
    source: "linux_auth",
    rawMessage: "Accepted publickey for j.patel from 192.0.2.40 port 49811 ssh2",
    scenario: "C",
  },
  {
    id: EVENT.benign[1],
    timestamp: "2026-10-21T08:03:44Z",
    eventType: "login_success",
    sourceIp: "192.0.2.41",
    username: "a.chen",
    hostname: "demo-workstation-07",
    action: "authentication_succeeded",
    source: "linux_auth",
    rawMessage: "Accepted publickey for a.chen from 192.0.2.41 port 50102 ssh2",
    scenario: "C",
  },
  {
    id: EVENT.benign[2],
    timestamp: "2026-10-21T08:07:02Z",
    eventType: "login_failure",
    sourceIp: "192.0.2.42",
    username: "m.rossi",
    hostname: "demo-workstation-09",
    action: "authentication_failed",
    source: "linux_auth",
    rawMessage: "Failed password for m.rossi from 192.0.2.42 port 50331 ssh2",
    scenario: "C",
  },
  {
    id: EVENT.benign[3],
    timestamp: "2026-10-21T08:07:18Z",
    eventType: "login_success",
    sourceIp: "192.0.2.42",
    username: "m.rossi",
    hostname: "demo-workstation-09",
    action: "authentication_succeeded",
    source: "linux_auth",
    rawMessage: "Accepted password for m.rossi from 192.0.2.42 port 50332 ssh2",
    scenario: "C",
  },
  {
    id: EVENT.benign[4],
    timestamp: "2026-10-21T08:30:00Z",
    eventType: "admin_task",
    sourceIp: "192.0.2.20",
    username: "svc-backup",
    hostname: "demo-server-01",
    action: "scheduled_backup_started",
    source: "cron",
    rawMessage: "Authorized scheduled backup job BACKUP-DAILY-0830 started by svc-backup",
    scenario: "C",
  },
];

export const mockIncidents: Incident[] = [
  {
    id: INCIDENT_IDS.bruteForce,
    title: "Brute-force login followed by success on demo_user",
    severity: "critical",
    status: "awaiting_approval",
    summary:
      "12 failed SSH logins for demo_user from 192.0.2.10 within five minutes, immediately followed by a successful login from the same source.",
    createdAt: "2026-10-21T10:20:02Z",
    scenario: "A",
    ruleIds: ["R1", "R2"],
    eventIds: [...EVENT.bruteFailures, EVENT.bruteSuccess],
    severityReasons: [
      {
        ruleId: "R1",
        eventIds: [...EVENT.bruteFailures],
        reason:
          "Repeated authentication failures: 12 failures from 192.0.2.10 against demo_user inside a 5-minute window (threshold 5).",
      },
      {
        ruleId: "R2",
        eventIds: [EVENT.bruteFailures[11], EVENT.bruteSuccess],
        reason:
          "Failure followed by success: login_success for the same source IP and username within the R1 window.",
      },
    ],
    investigationId: INVESTIGATION_IDS.bruteForce,
    mitreTechniques: [
      {
        techniqueId: "T1110",
        name: "Brute Force",
        reason: "Volume of failed authentications from one source against one account.",
        evidenceEventIds: [...EVENT.bruteFailures],
      },
      {
        techniqueId: "T1078",
        name: "Valid Accounts",
        reason: "A successful login occurred after the brute-force sequence.",
        evidenceEventIds: [EVENT.bruteSuccess],
      },
    ],
    rootCause: {
      hypothesis:
        "An external source exhausted password guesses against demo_user and obtained a valid session.",
      uncertainty:
        "Password spray versus a targeted guess cannot be distinguished from these logs alone. No endpoint telemetry is attached in v1.",
      confidence: "high",
    },
  },
  {
    id: INCIDENT_IDS.outbound,
    title: "Repeated outbound connections to 198.51.100.88",
    severity: "high",
    status: "investigating",
    summary:
      "demo-server-02 opened 10 outbound TCP connections to 198.51.100.88:443 in a short window. Reputation lookup is recorded as unavailable in this mock run.",
    createdAt: "2026-10-21T11:12:40Z",
    scenario: "B",
    ruleIds: ["R3"],
    eventIds: [...EVENT.outbound],
    severityReasons: [
      {
        ruleId: "R3",
        eventIds: [...EVENT.outbound],
        reason:
          "Unusual outbound activity: 10 connections from demo-server-02 to a single external IP within 5 minutes (threshold 10).",
      },
    ],
    investigationId: INVESTIGATION_IDS.outbound,
    mitreTechniques: [
      {
        techniqueId: "T1071",
        name: "Application Layer Protocol",
        reason: "Repeated HTTPS connections to one uncommon external endpoint.",
        evidenceEventIds: [...EVENT.outbound],
      },
    ],
    rootCause: {
      hypothesis:
        "The host established a repeating outbound channel. Without a successful reputation result this is treated as suspicious, not confirmed C2.",
      uncertainty:
        "Threat-intelligence lookup status is unavailable in this mock. The destination is not labelled malicious solely because the lookup failed.",
      confidence: "medium",
    },
  },
  {
    id: INCIDENT_IDS.benign,
    title: "Routine morning logins and scheduled backup",
    severity: "low",
    status: "resolved",
    summary:
      "Business-hours logins by known staff and one isolated failed password, followed by an authorized backup job. Detection rules did not meet attack thresholds.",
    createdAt: "2026-10-21T08:31:10Z",
    scenario: "C",
    ruleIds: [],
    eventIds: [...EVENT.benign],
    severityReasons: [
      {
        ruleId: "none",
        eventIds: [EVENT.benign[2]],
        reason:
          "A single login failure is below the R1 threshold of 5 failures in 5 minutes. No incident of confirmed attack is claimed.",
      },
    ],
    investigationId: INVESTIGATION_IDS.benign,
    mitreTechniques: [],
    rootCause: {
      hypothesis:
        "Activity is consistent with normal start-of-day access and a scheduled administrative backup.",
      uncertainty:
        "v1 has no directory baseline of 'normal' users beyond the seeded scenario. Classification is proportionate to the observed evidence only.",
      confidence: "high",
    },
  },
];

export const mockInvestigations: Investigation[] = [
  {
    id: INVESTIGATION_IDS.bruteForce,
    incidentId: INCIDENT_IDS.bruteForce,
    status: "waiting_for_approval",
    agents: [
      {
        agent: "investigation",
        status: "completed",
        startedAt: "2026-10-21T10:20:10Z",
        completedAt: "2026-10-21T10:20:18Z",
        finding:
          "Clustered 12 login_failure events and 1 login_success from 192.0.2.10 against demo_user on demo-server-01.",
        evidenceEventIds: [...EVENT.bruteFailures, EVENT.bruteSuccess],
        confidence: "high",
        reasoningSummary:
          "Events share source IP, username, host, and a 5-minute window. Open questions: whether the password was guessed or reused, and whether the session is still active.",
        recommendedNextStep: "Enrich 192.0.2.10 and inspect the successful session.",
      },
      {
        agent: "threat_intelligence",
        status: "completed",
        startedAt: "2026-10-21T10:20:18Z",
        completedAt: "2026-10-21T10:20:22Z",
        finding:
          "Lookup for 192.0.2.10 returned a mock AbuseIPDB result. This is documentation-range traffic, not a live reputation score.",
        evidenceEventIds: [EVENT.bruteFailures[0], EVENT.bruteSuccess],
        confidence: "medium",
        reasoningSummary:
          "The indicator was queried through the bounded lookup tool. Result is labelled as mock enrichment for Phase 2.",
        recommendedNextStep: "Combine intel with the authentication timeline.",
      },
      {
        agent: "analysis",
        status: "completed",
        startedAt: "2026-10-21T10:20:22Z",
        completedAt: "2026-10-21T10:20:31Z",
        finding:
          "Supported ATT&CK mapping: T1110 Brute Force and T1078 Valid Accounts. Sequence is failures then success.",
        evidenceEventIds: [...EVENT.bruteFailures, EVENT.bruteSuccess],
        confidence: "high",
        reasoningSummary:
          "The timeline is fully evidenced by event IDs. No malware sample or additional host telemetry is present.",
        recommendedNextStep: "Draft account-security response actions for analyst approval.",
      },
      {
        agent: "response_planner",
        status: "waiting_for_approval",
        startedAt: "2026-10-21T10:20:31Z",
        completedAt: "2026-10-21T10:20:36Z",
        finding:
          "Proposed simulated actions: force password reset for demo_user, review the session, and flag 192.0.2.10 for analyst review.",
        evidenceEventIds: [EVENT.bruteSuccess],
        confidence: "high",
        reasoningSummary:
          "Actions are labelled simulated. Nothing is blocked or disabled until a later authorized integration exists.",
        recommendedNextStep: "Wait for analyst approval or rejection.",
      },
    ],
    threatIntel: [
      {
        indicator: "192.0.2.10",
        indicatorType: "ip",
        provider: "abuseipdb",
        status: "ok",
        summary:
          "Mock enrichment only. 192.0.2.10 is an RFC 5737 documentation address, not a live reputation verdict.",
        lookedUpAt: "2026-10-21T10:20:21Z",
        source: "mock://threat-intel",
      },
    ],
    timeline: [
      {
        timestamp: "2026-10-21T10:15:00Z",
        title: "Authentication failures begin",
        detail: "First failed SSH password for demo_user from 192.0.2.10.",
        eventId: EVENT.bruteFailures[0],
      },
      {
        timestamp: "2026-10-21T10:18:21Z",
        title: "Failure volume crosses R1",
        detail: "Repeated authentication failures exceeded the configured threshold.",
        eventId: EVENT.bruteFailures[11],
      },
      {
        timestamp: "2026-10-21T10:19:48Z",
        title: "Successful login",
        detail: "Same source IP and username authenticated successfully (R2).",
        eventId: EVENT.bruteSuccess,
      },
      {
        timestamp: "2026-10-21T10:20:36Z",
        title: "Response plan ready",
        detail: "Simulated remediation steps waiting for analyst approval.",
      },
    ],
  },
  {
    id: INVESTIGATION_IDS.outbound,
    incidentId: INCIDENT_IDS.outbound,
    status: "running",
    agents: [
      {
        agent: "investigation",
        status: "completed",
        startedAt: "2026-10-21T11:12:48Z",
        completedAt: "2026-10-21T11:12:54Z",
        finding:
          "10 outbound connections from demo-server-02 (192.0.2.50) to 198.51.100.88:443.",
        evidenceEventIds: [...EVENT.outbound],
        confidence: "high",
        reasoningSummary:
          "The pattern matches R3. Next question is whether the destination has a known reputation.",
        recommendedNextStep: "Look up 198.51.100.88.",
      },
      {
        agent: "threat_intelligence",
        status: "completed",
        startedAt: "2026-10-21T11:12:54Z",
        completedAt: "2026-10-21T11:13:04Z",
        finding:
          "Reputation lookup for 198.51.100.88 is unavailable. The workflow continued without fabricating a score.",
        evidenceEventIds: [EVENT.outbound[0]],
        confidence: "low",
        reasoningSummary:
          "Provider timeout/unavailable is recorded explicitly. The IP is not treated as malicious because the lookup failed.",
        recommendedNextStep: "Analyse with internal evidence only.",
        error: "Threat intelligence provider unavailable (mock).",
      },
      {
        agent: "analysis",
        status: "running",
        startedAt: "2026-10-21T11:13:04Z",
        finding: "Drafting an evidence-based sequence. External reputation remains unknown.",
        evidenceEventIds: [...EVENT.outbound],
        confidence: "medium",
        reasoningSummary:
          "T1071 is supported by the connection pattern. T1041 exfiltration is not claimed — payload size and destination role are unknown.",
        recommendedNextStep: "Finish ATT&CK mapping and uncertainty notes.",
      },
      {
        agent: "response_planner",
        status: "queued",
        finding: "Waiting for analysis to complete.",
        evidenceEventIds: [],
        confidence: "low",
        reasoningSummary: "No response plan until analysis finishes.",
        recommendedNextStep: "Queue containment recommendations for approval.",
      },
    ],
    threatIntel: [
      {
        indicator: "198.51.100.88",
        indicatorType: "ip",
        provider: "abuseipdb",
        status: "unavailable",
        summary:
          "Lookup did not complete. Status is unavailable — not a malicious verdict.",
        lookedUpAt: "2026-10-21T11:13:04Z",
        source: "mock://threat-intel",
      },
    ],
    timeline: [
      {
        timestamp: "2026-10-21T11:02:14Z",
        title: "First outbound connection",
        detail: "demo-server-02 connected to 198.51.100.88:443.",
        eventId: EVENT.outbound[0],
      },
      {
        timestamp: "2026-10-21T11:11:14Z",
        title: "R3 threshold reached",
        detail: "Ten connections to the same external IP inside the detection window.",
        eventId: EVENT.outbound[9],
      },
      {
        timestamp: "2026-10-21T11:13:04Z",
        title: "Threat intel unavailable",
        detail: "External lookup recorded as unavailable; investigation continues.",
      },
    ],
  },
  {
    id: INVESTIGATION_IDS.benign,
    incidentId: INCIDENT_IDS.benign,
    status: "completed",
    agents: [
      {
        agent: "investigation",
        status: "completed",
        startedAt: "2026-10-21T08:31:20Z",
        completedAt: "2026-10-21T08:31:26Z",
        finding:
          "Five events: three successful staff logins, one isolated failure then success, and a scheduled backup.",
        evidenceEventIds: [...EVENT.benign],
        confidence: "high",
        reasoningSummary:
          "No source produced five failures in five minutes. The backup event is labelled authorized in the log.",
        recommendedNextStep: "Confirm no ATT&CK technique is evidenced.",
      },
      {
        agent: "threat_intelligence",
        status: "completed",
        startedAt: "2026-10-21T08:31:26Z",
        completedAt: "2026-10-21T08:31:28Z",
        finding: "No suspicious external indicator required a reputation lookup.",
        evidenceEventIds: [],
        confidence: "high",
        reasoningSummary: "Internal documentation-range sources only.",
        recommendedNextStep: "Produce a low-severity explanation.",
      },
      {
        agent: "analysis",
        status: "completed",
        startedAt: "2026-10-21T08:31:28Z",
        completedAt: "2026-10-21T08:31:34Z",
        finding:
          "Insufficient evidence of an attack. No MITRE technique is mapped. Severity remains low.",
        evidenceEventIds: [...EVENT.benign],
        confidence: "high",
        reasoningSummary:
          "The isolated failure is consistent with a mistyped password. Claiming a confirmed attack would be unsupported.",
        recommendedNextStep: "Close with no containment action.",
      },
      {
        agent: "response_planner",
        status: "completed",
        startedAt: "2026-10-21T08:31:34Z",
        completedAt: "2026-10-21T08:31:36Z",
        finding: "No simulated containment proposed. Monitor only.",
        evidenceEventIds: [],
        confidence: "high",
        reasoningSummary: "Over-response would not be proportionate to the evidence.",
        recommendedNextStep: "Keep the incident resolved.",
      },
    ],
    threatIntel: [],
    timeline: [
      {
        timestamp: "2026-10-21T08:01:12Z",
        title: "Staff logins begin",
        detail: "j.patel authenticated with a public key.",
        eventId: EVENT.benign[0],
      },
      {
        timestamp: "2026-10-21T08:07:02Z",
        title: "Isolated failure",
        detail: "One failed password for m.rossi, below detection threshold.",
        eventId: EVENT.benign[2],
      },
      {
        timestamp: "2026-10-21T08:30:00Z",
        title: "Scheduled backup",
        detail: "Authorized BACKUP-DAILY-0830 started by svc-backup.",
        eventId: EVENT.benign[4],
      },
    ],
  },
];

export const mockActions: ResponseAction[] = [
  {
    id: "act-0001-reset-password",
    incidentId: INCIDENT_IDS.bruteForce,
    actionType: "force_password_reset",
    target: "demo_user",
    reason: "Valid session obtained after a brute-force sequence (R1 + R2).",
    riskLevel: "medium",
    approvalStatus: "proposed",
    executionStatus: "not_executed",
    simulated: true,
    createdAt: MOCK_GENERATED_AT,
    decidedAt: null,
    actor: null,
  },
  {
    id: "act-0002-review-session",
    incidentId: INCIDENT_IDS.bruteForce,
    actionType: "review_session",
    target: "demo-server-01 / demo_user",
    reason: "Successful SSH login from 192.0.2.10 should be reviewed by an administrator.",
    riskLevel: "low",
    approvalStatus: "proposed",
    executionStatus: "not_executed",
    simulated: true,
    createdAt: MOCK_GENERATED_AT,
    decidedAt: null,
    actor: null,
  },
  {
    id: "act-0003-flag-ip",
    incidentId: INCIDENT_IDS.bruteForce,
    actionType: "flag_ip_for_review",
    target: "192.0.2.10",
    reason: "Source IP produced the entire failure-then-success cluster.",
    riskLevel: "low",
    approvalStatus: "proposed",
    executionStatus: "not_executed",
    simulated: true,
    createdAt: MOCK_GENERATED_AT,
    decidedAt: null,
    actor: null,
  },
  {
    id: "act-0004-review-host",
    incidentId: INCIDENT_IDS.outbound,
    actionType: "review_host",
    target: "demo-server-02",
    reason:
      "Repeated outbound connections to one external IP. Containment is not proposed until analysis finishes.",
    riskLevel: "medium",
    approvalStatus: "proposed",
    executionStatus: "not_executed",
    simulated: true,
    createdAt: MOCK_GENERATED_AT,
    decidedAt: null,
    actor: null,
  },
];

export const mockReports: IncidentReport[] = [
  {
    id: "rpt-0001",
    incidentId: INCIDENT_IDS.bruteForce,
    title: "Incident report — brute-force login",
    generatedAt: "2026-10-21T10:21:00Z",
    format: "html",
  },
  {
    id: "rpt-0002",
    incidentId: INCIDENT_IDS.benign,
    title: "Incident report — benign morning activity",
    generatedAt: "2026-10-21T08:32:00Z",
    format: "html",
  },
];

export const mockMetrics: DashboardMetrics = {
  totalIncidents: mockIncidents.length,
  openIncidents: mockIncidents.filter(
    (incident) =>
      incident.status === "open" ||
      incident.status === "investigating" ||
      incident.status === "awaiting_approval",
  ).length,
  criticalAndHigh: mockIncidents.filter(
    (incident) => incident.severity === "critical" || incident.severity === "high",
  ).length,
  awaitingApproval: mockIncidents.filter(
    (incident) => incident.status === "awaiting_approval",
  ).length,
};

export const SCENARIO_META: Record<
  "A" | "B" | "C",
  { name: string; incidentId: string; blurb: string }
> = {
  A: {
    name: "Brute-force login",
    incidentId: INCIDENT_IDS.bruteForce,
    blurb: "Many failed logins from one IP, then a success. Primary demo path.",
  },
  B: {
    name: "Suspicious outbound connection",
    incidentId: INCIDENT_IDS.outbound,
    blurb: "Repeated connections to an unusual IP, with an unavailable reputation lookup.",
  },
  C: {
    name: "Benign activity",
    incidentId: INCIDENT_IDS.benign,
    blurb: "Normal logins and a scheduled backup. No confirmed attack is claimed.",
  },
};
