import { describe, expect, it } from "vitest";

import { formatDetailValue } from "@/lib/format";

describe("formatDetailValue", () => {
  it("stringifies primitives", () => {
    expect(formatDetailValue("approved")).toBe("approved");
    expect(formatDetailValue(3)).toBe("3");
    expect(formatDetailValue(true)).toBe("true");
    expect(formatDetailValue(null)).toBe("");
  });

  it("JSON-encodes arrays and objects instead of [object Object]", () => {
    expect(formatDetailValue({ decision: "approved" })).toBe('{"decision":"approved"}');
    expect(formatDetailValue(["a", "b"])).toBe('["a","b"]');
    expect(formatDetailValue({ nested: { ok: true } })).not.toContain("[object Object]");
  });
});
