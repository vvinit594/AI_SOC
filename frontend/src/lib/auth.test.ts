import { afterEach, describe, expect, it, vi } from "vitest";

import { loginAccount, registerAccount } from "@/lib/auth";
import { csrfHeaders, readCsrfToken } from "@/lib/csrf";
import { API_BASE_URL } from "@/lib/constants";

describe("auth client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("registers with JSON and credentials, never storing a token in localStorage", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "11111111-1111-4111-8111-111111111111",
          full_name: "Ada",
          email: "ada@example.com",
          created_at: "2026-11-20T00:00:00Z",
          workspace: {
            id: "22222222-2222-4222-8222-222222222222",
            name: "Ada's workspace",
            kind: "personal",
            role: "owner",
          },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    await registerAccount({
      fullName: "Ada",
      email: "ada@example.com",
      password: "CorrectHorseBattery1",
    });
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`${API_BASE_URL}/api/auth/register`);
    expect(init.credentials).toBe("include");
    expect(JSON.stringify(init)).not.toContain("localStorage");
    expect(JSON.stringify(init)).not.toContain("sessionStorage");
  });

  it("logs in with credentials included", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "11111111-1111-4111-8111-111111111111",
          full_name: "Ada",
          email: "ada@example.com",
          created_at: "2026-11-20T00:00:00Z",
          workspace: {
            id: "22222222-2222-4222-8222-222222222222",
            name: "Ada's workspace",
            kind: "personal",
            role: "owner",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    await loginAccount({ email: "ada@example.com", password: "CorrectHorseBattery1" });
    expect(fetchMock.mock.calls[0]?.[1]).toEqual(expect.objectContaining({ credentials: "include" }));
  });

  it("reads the non-HttpOnly CSRF cookie for mutation headers", () => {
    vi.stubGlobal("document", { cookie: "aisoc_csrf=csrf-test-token; path=/" });
    expect(readCsrfToken()).toBe("csrf-test-token");
    expect(csrfHeaders()).toEqual({ "X-CSRF-Token": "csrf-test-token" });
  });
});
