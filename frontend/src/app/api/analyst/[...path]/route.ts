import { safeReportFilename } from "@/lib/report";
import {
  ANALYST_PROXY_TIMEOUT_MS,
  isAbortError,
  isAnalystProxyAllowed,
  jsonError,
  matchAnalystProxyPath,
  parseBoundedInt,
  upstreamPath,
  type AnalystProxyTarget,
} from "@/lib/analyst-proxy";

const SAFE_DETAIL_MAX = 300;

function upstreamOrigin(): string {
  const configured =
    process.env.API_UPSTREAM_URL?.trim() || process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  return (configured || "http://localhost:8000").replace(/\/$/, "");
}

function authorizationHeader(): Record<string, string> {
  const token = process.env.ANALYST_API_TOKEN?.trim();
  if (!token) {
    return {};
  }
  return { Authorization: `Bearer ${token}` };
}

function logProxy(method: string, path: string, status: number): void {
  console.info(`analyst-proxy method=${method} path=${path} status=${status}`);
}

function safeDetail(text: string, fallback: string): string {
  const trimmed = text.trim();
  if (!trimmed || trimmed.length > SAFE_DETAIL_MAX) {
    return fallback;
  }
  if (/token|password|secret|authorization|bearer|database/i.test(trimmed) && trimmed.length > 80) {
    return fallback;
  }
  return trimmed;
}

function buildUpstreamUrl(target: AnalystProxyTarget, requestUrl: string): string {
  const origin = upstreamOrigin();
  const path = upstreamPath(target);
  if (target.kind !== "audit") {
    return `${origin}${path}`;
  }
  const incoming = new URL(requestUrl);
  const limit = parseBoundedInt(incoming.searchParams.get("limit"), 100, 1, 500);
  const offset = parseBoundedInt(incoming.searchParams.get("offset"), 0, 0, 1_000_000);
  return `${origin}${path}?limit=${limit}&offset=${offset}`;
}

async function proxy(
  request: Request,
  segments: string[],
): Promise<Response> {
  if (!isAnalystProxyAllowed()) {
    logProxy(request.method, new URL(request.url).pathname, 403);
    return jsonError(
      403,
      "Analyst proxy is disabled in production because there is no authenticated user session.",
      "analyst_proxy_disabled",
    );
  }

  const target = matchAnalystProxyPath(segments, request.method);
  if (target === null) {
    return jsonError(404, "Unknown analyst proxy route", "not_found");
  }

  const accept = target.kind === "report" ? "text/html" : "application/json";
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ANALYST_PROXY_TIMEOUT_MS);
  try {
    const response = await fetch(buildUpstreamUrl(target, request.url), {
      method: request.method,
      headers: {
        Accept: accept,
        ...authorizationHeader(),
      },
      cache: "no-store",
      signal: controller.signal,
    });

    if (target.kind === "report" && response.ok) {
      const contentType = response.headers.get("content-type") ?? "";
      if (!contentType.toLowerCase().includes("text/html")) {
        return jsonError(502, "Upstream report was not HTML", "http_error");
      }
      const body = await response.arrayBuffer();
      const filename = safeReportFilename(
        response.headers.get("content-disposition"),
        target.incidentId,
      );
      logProxy(request.method, upstreamPath(target), response.status);
      return new Response(body, {
        status: 200,
        headers: {
          "Content-Type": contentType,
          "Content-Disposition": `attachment; filename="${filename}"`,
          "X-Content-Type-Options": "nosniff",
          "Cache-Control": "no-store",
        },
      });
    }

    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      const payload = (await response.json()) as {
        error?: string;
        detail?: string;
        code?: string;
      };
      logProxy(request.method, upstreamPath(target), response.status);
      return Response.json(
        {
          error: payload.error ?? "http_error",
          detail: safeDetail(
            String(payload.detail ?? ""),
            `Request failed with status ${response.status}`,
          ),
          code: payload.code ?? "http_error",
        },
        { status: response.status },
      );
    }

    if (!response.ok) {
      logProxy(request.method, upstreamPath(target), response.status);
      return jsonError(response.status, `Request failed with status ${response.status}`);
    }

    const text = await response.text();
    logProxy(request.method, upstreamPath(target), response.status);
    return new Response(text, {
      status: response.status,
      headers: { "Content-Type": contentType || "application/json" },
    });
  } catch (error) {
    if (isAbortError(error)) {
      return jsonError(504, "Upstream request timed out");
    }
    return jsonError(502, "Unable to reach the API");
  } finally {
    clearTimeout(timer);
  }
}

async function segmentsFrom(
  context: { params: Promise<{ path?: string[] }> },
): Promise<string[]> {
  const params = await context.params;
  return params.path ?? [];
}

export async function GET(
  request: Request,
  context: { params: Promise<{ path?: string[] }> },
): Promise<Response> {
  return proxy(request, await segmentsFrom(context));
}

export async function POST(
  request: Request,
  context: { params: Promise<{ path?: string[] }> },
): Promise<Response> {
  return proxy(request, await segmentsFrom(context));
}
