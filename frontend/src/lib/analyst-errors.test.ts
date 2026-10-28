import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { analystErrorMessage, shouldBlockInFlight } from "@/lib/analyst-errors";

describe("analyst error mapping", () => {
  it("explains 401 without exposing a token workaround", () => {
    const message = analystErrorMessage(new ApiError("nope", 401, "http_error"));
    expect(message.toLowerCase()).toContain("token");
    expect(message).toContain("not NEXT_PUBLIC_");
    expect(message).not.toMatch(/NEXT_PUBLIC_ANALYST_API_TOKEN\s*=/);
    expect(message.toLowerCase()).toContain("browser");
  });

  it("explains 403 as production authentication not configured", () => {
    expect(analystErrorMessage(new ApiError("forbidden", 403, "http_error"))).toContain(
      "production authentication is not configured",
    );
  });

  it("explains a disabled production proxy without treating it as login", () => {
    expect(
      analystErrorMessage(new ApiError("disabled", 403, "analyst_proxy_disabled")),
    ).toContain("no login session");
  });

  it("maps 404, 409, and network failures", () => {
    expect(analystErrorMessage(new ApiError("missing", 404, "not_found"))).toContain("not found");
    expect(analystErrorMessage(new ApiError("conflict", 409, "http_error"))).toContain(
      "conflicting decision",
    );
    expect(analystErrorMessage(new ApiError("down", 0, "network_error"))).toContain(
      "Unable to reach the API",
    );
  });

  it("blocks duplicate in-flight work", () => {
    expect(shouldBlockInFlight(true)).toBe(true);
    expect(shouldBlockInFlight(false)).toBe(false);
  });
});
