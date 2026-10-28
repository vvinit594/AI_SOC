import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { API_BASE_URL, APP_NAME } from "@/lib/constants";

const FRONTEND_ROOT = path.resolve(__dirname, "../..");

describe("frontend public environment", () => {
  it("does not expose ANALYST_API_TOKEN through NEXT_PUBLIC_ constants", () => {
    expect(API_BASE_URL).not.toMatch(/token/i);
    expect(APP_NAME).not.toMatch(/token/i);
    expect(process.env.NEXT_PUBLIC_ANALYST_API_TOKEN).toBeUndefined();
  });

  it("keeps ANALYST_API_TOKEN out of the committed public env example", () => {
    const example = readFileSync(path.join(FRONTEND_ROOT, ".env.example"), "utf8");
    expect(example).not.toMatch(/NEXT_PUBLIC_ANALYST_API_TOKEN/);
    expect(example).not.toMatch(/^ANALYST_API_TOKEN=/m);
    expect(example).toMatch(/API_UPSTREAM_URL=/);
    expect(example).toMatch(/# ANALYST_API_TOKEN=/);
  });
});
