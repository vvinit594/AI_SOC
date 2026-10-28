import {
  mapAuditLog,
  mapIncident,
  type ActionDecisionApi,
  type AuditLogListApi,
  type IncidentApiItem,
  type IncidentListApi,
} from "@/lib/actions";
import { analystProxyUrl, isAbortError } from "@/lib/analyst-proxy";
import { API_BASE_URL } from "@/lib/constants";
import { isHtmlContentType, safeReportFilename } from "@/lib/report";
import type { AgentName, AgentRunStatus, AuditLogEntry, PersistedIncident } from "@/lib/types";

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
      headers: { Accept: "application/json" },
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
      errorBody.code ?? "http_error",
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

export async function listIncidentsApi(signal?: AbortSignal): Promise<PersistedIncident[]> {
  const listed = await apiGet<IncidentListApi>("/api/incidents", signal);
  const detailed = await Promise.all(
    listed.items.map((item) => apiGet<IncidentApiItem>(`/api/incidents/${item.id}`, signal)),
  );
  return detailed.map(mapIncident);
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
    analystProxyUrl(`/api/incidents/${incidentId}/audit-logs`),
    signal,
  );
  return payload.items.map(mapAuditLog);
}

export async function approveAction(
  actionId: string,
  signal?: AbortSignal,
): Promise<ActionDecisionApi> {
  return apiPost<ActionDecisionApi>(analystProxyUrl(`/api/actions/${actionId}/approve`), signal);
}

export async function rejectAction(
  actionId: string,
  signal?: AbortSignal,
): Promise<ActionDecisionApi> {
  return apiPost<ActionDecisionApi>(analystProxyUrl(`/api/actions/${actionId}/reject`), signal);
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
    response = await fetch(apiUrl(analystProxyUrl(`/api/incidents/${incidentId}/report`)), {
      method: "GET",
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

