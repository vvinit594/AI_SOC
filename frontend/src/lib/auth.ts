import { csrfHeaders } from "@/lib/csrf";
import { API_BASE_URL } from "@/lib/constants";
import { ApiError } from "@/lib/api";
import { isAbortError } from "@/lib/analyst-proxy";

export type WorkspaceIdentity = {
  id: string;
  name: string;
  kind: string;
  role: string;
};

export type CurrentUser = {
  id: string;
  full_name: string;
  email: string;
  workspace: WorkspaceIdentity;
  created_at: string;
};

type ErrorBody = {
  error?: string;
  detail?: string;
  code?: string;
};

function authUrl(path: string): string {
  const base = API_BASE_URL.replace(/\/$/, "");
  return `${base}${path}`;
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

async function authRequest<T>(
  path: string,
  init: RequestInit,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(authUrl(path), {
      ...init,
      credentials: "include",
      signal,
      headers: {
        Accept: "application/json",
        ...(init.headers ?? {}),
      },
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

export function getCurrentUser(signal?: AbortSignal): Promise<CurrentUser> {
  return authRequest<CurrentUser>("/api/auth/me", { method: "GET" }, signal);
}

export function registerAccount(input: {
  fullName: string;
  email: string;
  password: string;
}): Promise<CurrentUser> {
  return authRequest<CurrentUser>("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      full_name: input.fullName,
      email: input.email,
      password: input.password,
    }),
  });
}

export function loginAccount(input: { email: string; password: string }): Promise<CurrentUser> {
  return authRequest<CurrentUser>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function logoutAccount(): Promise<{ ok: boolean }> {
  return authRequest<{ ok: boolean }>("/api/auth/logout", {
    method: "POST",
    headers: csrfHeaders(),
  });
}

export type ForgotPasswordResult = {
  detail: string;
  delivery: string;
  dev_recovery_token?: string | null;
};

export function requestPasswordRecovery(email: string): Promise<ForgotPasswordResult> {
  return authRequest<ForgotPasswordResult>("/api/auth/forgot-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, password: string): Promise<{ ok: boolean }> {
  return authRequest<{ ok: boolean }>("/api/auth/reset-password", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, password }),
  });
}
