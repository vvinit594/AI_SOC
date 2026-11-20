import {
  mapAuditLog,
  mapIncident,
  type ActionDecisionApi,
  type AuditLogListApi,
  type IncidentApiItem,
  type IncidentListApi,
} from "@/lib/actions";
import { isAbortError } from "@/lib/analyst-proxy";
import { API_BASE_URL } from "@/lib/constants";
import { csrfHeaders } from "@/lib/csrf";
import { isHtmlContentType, safeReportFilename } from "@/lib/report";
import type {
  AgentName,
  AgentRunStatus,
  AuditLogEntry,
  DemoScenario,
  PersistedIncident,
  SecurityEvent,
} from "@/lib/types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export type RecordErrorApi = {
  index: number;
  detail: string;
};

export class IngestApiError extends ApiError {
  readonly errors: RecordErrorApi[];

  constructor(message: string, status: number, code: string, errors: RecordErrorApi[]) {
    super(message, status, code);
    this.name = "IngestApiError";
    this.errors = errors;
  }
}

export type HealthResponse = {
  status: "ok";
  service: string;
  environment: "development" | "test" | "production";
  version: string;
};

type ErrorBody = {
  error?: string;
  detail?: string;
  code?: string;
  errors?: RecordErrorApi[];
};

function apiUrl(path: string): string {
  if (path.startsWith("/api/analyst/")) {
    return path;
  }
  const base = API_BASE_URL.replace(/\/$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

async function parseJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function jsonRequest<T>(
  path: string,
  method: "GET" | "POST",
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(method === "POST" ? csrfHeaders() : {}),
      },
      signal,
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }
    throw new ApiError("Unable to reach the API", 0, "network_error");
  }

  const body = await parseJson(response);
  if (!response.ok) {
    const errorBody = (body ?? {}) as ErrorBody;
    throw new ApiError(
      errorBody.detail ?? `Request failed with status ${response.status}`,
      response.status,
      errorBody.code ?? (response.status === 401 ? "unauthenticated" : "http_error"),
    );
  }
  return body as T;
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return jsonRequest<T>(path, "GET", signal);
}

export async function apiPost<T>(path: string, signal?: AbortSignal): Promise<T> {
  return jsonRequest<T>(path, "POST", signal);
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiGet<HealthResponse>("/health", signal);
}

export type InvestigationApiNode = {
  agent_name: AgentName;
  status: AgentRunStatus;
  started_at: string | null;
  completed_at: string | null;
  structured_output: Record<string, unknown>;
  error: string | null;
};

export type InvestigationApiResponse = {
  id: string;
  incident_id: string;
  status: AgentRunStatus;
  nodes: InvestigationApiNode[];
};

export function getInvestigationApi(
  investigationId: string,
  signal?: AbortSignal,
): Promise<InvestigationApiResponse> {
  return apiGet<InvestigationApiResponse>(
    `/api/investigations/${investigationId}`,
    signal,
  );
}

export async function listIncidentSummaries(
  signal?: AbortSignal,
): Promise<PersistedIncident[]> {
  const listed = await apiGet<IncidentListApi>("/api/incidents", signal);
  return listed.items.map(mapIncident);
}

export async function listIncidentsApi(signal?: AbortSignal): Promise<PersistedIncident[]> {
  const listed = await apiGet<IncidentListApi>("/api/incidents", signal);
  const detailed = await Promise.all(
    listed.items.map((item) => apiGet<IncidentApiItem>(`/api/incidents/${item.id}`, signal)),
  );
  return detailed.map(mapIncident);
}

export type SecurityEventApiItem = {
  id: string;
  timestamp: string;
  event_type: string;
  source_ip: string | null;
  destination_ip: string | null;
  username: string | null;
  hostname: string | null;
  action: string | null;
  source: string;
  raw_message: string;
  scenario: string | null;
};

export type EventListApi = {
  items: SecurityEventApiItem[];
  total: number;
};

export type ListEventsQuery = {
  eventType?: string;
  scenario?: string;
  limit?: number;
  offset?: number;
  signal?: AbortSignal;
};

export function mapSecurityEvent(row: SecurityEventApiItem): SecurityEvent {
  return {
    id: row.id,
    timestamp: row.timestamp,
    eventType: row.event_type,
    sourceIp: row.source_ip ?? undefined,
    destinationIp: row.destination_ip ?? undefined,
    username: row.username ?? undefined,
    hostname: row.hostname ?? undefined,
    action: row.action ?? undefined,
    source: row.source,
    rawMessage: row.raw_message,
    scenario: row.scenario ?? "",
  };
}

export function eventsListPath(query: ListEventsQuery = {}): string {
  const params = new URLSearchParams();
  params.set("limit", String(query.limit ?? 50));
  params.set("offset", String(query.offset ?? 0));
  if (query.eventType && query.eventType !== "all") {
    params.set("event_type", query.eventType);
  }
  if (query.scenario && query.scenario !== "all") {
    params.set("scenario", query.scenario);
  }
  return `/api/events?${params.toString()}`;
}

export async function listEventsPage(
  query: ListEventsQuery = {},
): Promise<{ items: SecurityEvent[]; total: number }> {
  const listed = await apiGet<EventListApi>(eventsListPath(query), query.signal);
  return { items: listed.items.map(mapSecurityEvent), total: listed.total };
}

export async function listEventsApi(signal?: AbortSignal): Promise<SecurityEvent[]> {
  const page = await listEventsPage({ limit: 500, offset: 0, signal });
  return page.items;
}

export type LogUploadApi = {
  accepted: number;
  rejected: number;
  event_ids: string[];
  errors: RecordErrorApi[];
};

export async function uploadLogs(file: File, signal?: AbortSignal): Promise<LogUploadApi> {
  const body = new FormData();
  body.append("file", file, file.name);
  let response: Response;
  try {
    response = await fetch(apiUrl("/api/logs/upload"), {
      method: "POST",
      credentials: "include",
      headers: { Accept: "application/json", ...csrfHeaders() },
      body,
      signal,
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }
    throw new ApiError("Unable to reach the API", 0, "network_error");
  }

  const payload = await parseJson(response);
  const errorBody = (payload ?? {}) as ErrorBody;
  const recordErrors = Array.isArray(errorBody.errors) ? errorBody.errors : [];

  if (!response.ok) {
    if (recordErrors.length > 0) {
      throw new IngestApiError(
        errorBody.detail ?? `Request failed with status ${response.status}`,
        response.status,
        errorBody.code ?? "ingest_error",
        recordErrors,
      );
    }
    throw new ApiError(
      errorBody.detail ?? `Request failed with status ${response.status}`,
      response.status,
      errorBody.code ?? "http_error",
    );
  }

  const uploaded = payload as LogUploadApi;
  return {
    accepted: uploaded.accepted,
    rejected: uploaded.rejected,
    event_ids: uploaded.event_ids ?? [],
    errors: uploaded.errors ?? [],
  };
}

export type ScenarioLoadApi = {
  scenario: DemoScenario;
  accepted: number;
  event_ids: string[];
};

export function loadDemoScenario(
  scenario: DemoScenario,
  signal?: AbortSignal,
): Promise<ScenarioLoadApi> {
  return apiPost<ScenarioLoadApi>(`/api/scenarios/${scenario}/load`, signal);
}

export type DetectionMatchApi = {
  rule_id: string;
  severity: string;
  event_ids: string[];
  reason: string;
  matched_threshold: string;
  timestamp: string;
  incident_id: string;
};

export type DetectIncidentsApi = {
  matches: DetectionMatchApi[];
  incidents: IncidentApiItem[];
  created: number;
  updated: number;
  skipped: number;
};

export function detectIncidents(signal?: AbortSignal): Promise<DetectIncidentsApi> {
  return apiPost<DetectIncidentsApi>("/api/incidents/detect", signal);
}

export type InvestigateApiResponse = {
  investigation: InvestigationApiResponse;
  created: boolean;
};

export function startInvestigationApi(
  incidentId: string,
  signal?: AbortSignal,
): Promise<InvestigateApiResponse> {
  return apiPost<InvestigateApiResponse>(
    `/api/incidents/${incidentId}/investigate`,
    signal,
  );
}

export async function getIncidentApi(
  incidentId: string,
  signal?: AbortSignal,
): Promise<PersistedIncident> {
  const row = await apiGet<IncidentApiItem>(`/api/incidents/${incidentId}`, signal);
  return mapIncident(row);
}

export async function listIncidentAuditLogs(
  incidentId: string,
  signal?: AbortSignal,
): Promise<AuditLogEntry[]> {
  const payload = await apiGet<AuditLogListApi>(
    `/api/incidents/${incidentId}/audit-logs`,
    signal,
  );
  return payload.items.map(mapAuditLog);
}

export async function approveAction(
  actionId: string,
  signal?: AbortSignal,
): Promise<ActionDecisionApi> {
  return apiPost<ActionDecisionApi>(`/api/actions/${actionId}/approve`, signal);
}

export async function rejectAction(
  actionId: string,
  signal?: AbortSignal,
): Promise<ActionDecisionApi> {
  return apiPost<ActionDecisionApi>(`/api/actions/${actionId}/reject`, signal);
}

export type DownloadedReport = {
  blob: Blob;
  filename: string;
  contentType: string;
};

export async function downloadIncidentReport(
  incidentId: string,
  signal?: AbortSignal,
): Promise<DownloadedReport> {
  let response: Response;
  try {
    response = await fetch(apiUrl(`/api/incidents/${incidentId}/report`), {
      method: "GET",
      credentials: "include",
      headers: { Accept: "text/html" },
      signal,
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }
    throw new ApiError("Unable to reach the API", 0, "network_error");
  }

  if (!response.ok) {
    const body = await parseJson(response);
    const errorBody = (body ?? {}) as ErrorBody;
    throw new ApiError(
      errorBody.detail ?? `Request failed with status ${response.status}`,
      response.status,
      errorBody.code ?? "http_error",
    );
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!isHtmlContentType(contentType)) {
    throw new ApiError(
      "Report response was not HTML",
      response.status,
      "unexpected_content_type",
    );
  }

  const blob = await response.blob();
  return {
    blob,
    filename: safeReportFilename(response.headers.get("content-disposition"), incidentId),
    contentType,
  };
}

