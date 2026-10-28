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
        "Missing or invalid analyst token. This UI does not send ANALYST_API_TOKEN " +
        "from the browser. Development works when the backend token is empty."
      );
    case 403:
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
