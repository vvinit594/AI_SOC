import { describe, expect, it } from "vitest";

import {
  formatFileSize,
  isSupportedUpload,
  MAX_UPLOAD_BYTES,
  validateUploadFile,
} from "@/lib/ingest";

function fakeFile(name: string, size: number, type = ""): Pick<File, "name" | "type" | "size"> {
  return { name, type, size };
}

describe("upload file validation", () => {
  it("accepts JSON by extension", () => {
    expect(validateUploadFile(fakeFile("events.json", 128, "application/json"))).toBeNull();
    expect(isSupportedUpload(fakeFile("events.JSON", 12))).toBe(true);
  });

  it("accepts CSV by extension", () => {
    expect(validateUploadFile(fakeFile("events.csv", 64, "text/csv"))).toBeNull();
  });

  it("rejects unsupported formats", () => {
    const result = validateUploadFile(fakeFile("events.txt", 32, "text/plain"));
    expect(result?.code).toBe("unsupported_format");
    expect(result?.message).toContain("JSON or CSV");
  });

  it("rejects oversized files using MAX_UPLOAD_SIZE_MB", () => {
    const result = validateUploadFile(fakeFile("events.json", MAX_UPLOAD_BYTES + 1));
    expect(result?.code).toBe("oversized");
    expect(result?.message).toContain("MAX_UPLOAD_SIZE_MB");
  });

  it("rejects empty files", () => {
    expect(validateUploadFile(fakeFile("events.json", 0))?.code).toBe("empty");
  });

  it("formats byte sizes for the selected-file label", () => {
    expect(formatFileSize(512)).toBe("512 B");
    expect(formatFileSize(2048)).toBe("2.0 KB");
    expect(formatFileSize(2 * 1024 * 1024)).toBe("2.0 MB");
  });
});
