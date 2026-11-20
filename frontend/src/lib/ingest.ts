/** Matches backend `Settings.max_upload_size_mb` default (MAX_UPLOAD_SIZE_MB). */
export const MAX_UPLOAD_SIZE_MB = 10;
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;
export const EVENTS_PAGE_SIZE = 50;

const JSON_MEDIA = new Set(["application/json", "text/json"]);
const CSV_MEDIA = new Set(["text/csv", "application/csv"]);

export type UploadValidationCode = "unsupported_format" | "oversized" | "empty";

export type UploadValidationError = {
  code: UploadValidationCode;
  message: string;
};

export function isSupportedUpload(file: Pick<File, "name" | "type">): boolean {
  const name = file.name.toLowerCase();
  if (name.endsWith(".json") || name.endsWith(".csv")) {
    return true;
  }
  const media = (file.type || "").split(";")[0].trim().toLowerCase();
  return JSON_MEDIA.has(media) || CSV_MEDIA.has(media);
}

export function validateUploadFile(
  file: Pick<File, "name" | "type" | "size">,
  maxBytes = MAX_UPLOAD_BYTES,
): UploadValidationError | null {
  if (file.size <= 0) {
    return { code: "empty", message: "Upload is empty" };
  }
  if (file.size > maxBytes) {
    return {
      code: "oversized",
      message: `Upload exceeds MAX_UPLOAD_SIZE_MB (${Math.floor(maxBytes / (1024 * 1024))} MB)`,
    };
  }
  if (!isSupportedUpload(file)) {
    return { code: "unsupported_format", message: "Unsupported file type; upload JSON or CSV" };
  }
  return null;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
