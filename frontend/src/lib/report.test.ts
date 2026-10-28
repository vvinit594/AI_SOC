import { describe, expect, it } from "vitest";

import {
  fallbackReportFilename,
  isHtmlContentType,
  isSafeReportFilename,
  parseContentDispositionFilename,
  safeReportFilename,
} from "@/lib/report";

const INCIDENT_ID = "a1e0c3f2-4b91-4d2a-9c18-11b0a0b7e001";

describe("report filename handling", () => {
  it("parses a quoted Content-Disposition filename", () => {
    expect(
      parseContentDispositionFilename(
        `attachment; filename="incident-${INCIDENT_ID}-report.html"`,
      ),
    ).toBe(`incident-${INCIDENT_ID}-report.html`);
  });

  it("parses RFC 5987 filename*", () => {
    expect(
      parseContentDispositionFilename(
        "attachment; filename*=UTF-8''incident-report.html",
      ),
    ).toBe("incident-report.html");
  });

  it("returns null when the header is missing or empty", () => {
    expect(parseContentDispositionFilename(null)).toBeNull();
    expect(parseContentDispositionFilename("attachment")).toBeNull();
  });

  it("rejects path traversal and non-html names", () => {
    expect(isSafeReportFilename("../../etc/passwd.html")).toBe(false);
    expect(isSafeReportFilename("report.exe")).toBe(false);
    expect(isSafeReportFilename("report.html.txt")).toBe(false);
    expect(isSafeReportFilename(`incident-${INCIDENT_ID}-report.html`)).toBe(true);
  });

  it("falls back when Content-Disposition is absent or malformed", () => {
    expect(safeReportFilename(null, INCIDENT_ID)).toBe(
      `incident-${INCIDENT_ID}-report.html`,
    );
    expect(safeReportFilename('attachment; filename="../../evil.html"', INCIDENT_ID)).toBe(
      `incident-${INCIDENT_ID}-report.html`,
    );
    expect(safeReportFilename('attachment; filename="notes.exe"', INCIDENT_ID)).toBe(
      `incident-${INCIDENT_ID}-report.html`,
    );
    expect(fallbackReportFilename("not a uuid")).toBe("incident-report.html");
  });

  it("accepts HTML content types only", () => {
    expect(isHtmlContentType("text/html; charset=utf-8")).toBe(true);
    expect(isHtmlContentType("application/json")).toBe(false);
    expect(isHtmlContentType(null)).toBe(false);
  });
});
