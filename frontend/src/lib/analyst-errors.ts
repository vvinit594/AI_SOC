import { ApiError } from "@/lib/api";

export function analystErrorMessage(error: unknown): string {
  if (error instanceof DOMException && error.name === "AbortError") {
    return "Request cancelled.";
  }
  if (!(error instanceof ApiError)) {
    return "An unexpected error occurred.";
  }
  switch (error.status) {
    case 0:
      return "Unable to reach the API.";
    case 401:
      return (
        "Missing or invalid analyst token. The browser never receives ANALYST_API_TOKEN. " +
        "In development, set it only on the Next.js server (not NEXT_PUBLIC_) or leave the backend token empty."
      );
    case 403:
      if (error.code === "analyst_proxy_disabled") {
        return "Analyst operations are disabled in production because this app has no login session.";
      }
      return "Analyst decisions are unavailable because production authentication is not configured.";
    case 404:
      return "The requested incident or action was not found.";
    case 409:
      return "A conflicting decision already exists. Reloading the latest server state.";
    default:
      return error.message;
  }
}

export function shouldBlockInFlight(inFlight: boolean): boolean {
  return inFlight;
}
