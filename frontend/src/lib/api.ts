import { API_BASE_URL } from "@/lib/constants";
import type { AgentName, AgentRunStatus } from "@/lib/types";

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
  const base = API_BASE_URL.replace(/\/$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

async function parseJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }
  return response.json();
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: "GET",
      headers: { Accept: "application/json" },
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
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
