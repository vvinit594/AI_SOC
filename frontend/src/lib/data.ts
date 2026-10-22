/**
 * UI data access layer.
 *
 * Phase 2: returns in-memory mock data.
 * Phase 3+: replace these function bodies with the FastAPI client.
 * Page and feature components should import from here, not from `mock-data.ts`.
 */

import {
  mockActions,
  mockEvents,
  mockIncidents,
  mockInvestigations,
  mockMetrics,
  mockReports,
  SCENARIO_META,
} from "@/lib/mock-data";
import type {
  DashboardMetrics,
  DemoScenario,
  Incident,
  IncidentReport,
  Investigation,
  ResponseAction,
  SecurityEvent,
} from "@/lib/types";

export function listIncidents(): Incident[] {
  return mockIncidents;
}

export function getIncident(id: string): Incident | undefined {
  return mockIncidents.find((incident) => incident.id === id);
}

export function listEvents(): SecurityEvent[] {
  return mockEvents;
}

export function getEventsForIncident(incident: Incident): SecurityEvent[] {
  const ids = new Set(incident.eventIds);
  return mockEvents.filter((event) => ids.has(event.id));
}

export function getEvent(id: string): SecurityEvent | undefined {
  return mockEvents.find((event) => event.id === id);
}

export function getInvestigation(id: string): Investigation | undefined {
  return mockInvestigations.find((investigation) => investigation.id === id);
}

export function getInvestigationForIncident(
  incidentId: string,
): Investigation | undefined {
  return mockInvestigations.find(
    (investigation) => investigation.incidentId === incidentId,
  );
}

export function listActions(): ResponseAction[] {
  return mockActions;
}

export function getActionsForIncident(incidentId: string): ResponseAction[] {
  return mockActions.filter((action) => action.incidentId === incidentId);
}

export function listReports(): IncidentReport[] {
  return mockReports;
}

export function getReport(id: string): IncidentReport | undefined {
  return mockReports.find((report) => report.id === id);
}

export function getMetrics(): DashboardMetrics {
  return mockMetrics;
}

export function getScenarioMeta(scenario: DemoScenario) {
  return SCENARIO_META[scenario];
}

export function listScenarios() {
  return Object.entries(SCENARIO_META).map(([id, meta]) => ({
    id: id as DemoScenario,
    ...meta,
  }));
}

export function getPrimaryInvestigationId(): string {
  return mockIncidents[0].investigationId;
}
