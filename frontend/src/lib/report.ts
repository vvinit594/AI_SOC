const FILENAME_STAR = /filename\*\s*=\s*UTF-8''([^;]+)/i;
const FILENAME = /filename\s*=\s*(?:"((?:\\.|[^"])*)"|([^;\s]+))/i;

export function parseContentDispositionFilename(header: string | null): string | null {
  if (!header) {
    return null;
  }
  const encoded = header.match(FILENAME_STAR);
  if (encoded?.[1]) {
    try {
      const decoded = decodeURIComponent(encoded[1]).trim();
      return decoded || null;
    } catch {
      return null;
    }
  }
  const basic = header.match(FILENAME);
  const raw = (basic?.[1] ?? basic?.[2] ?? "").trim();
  return raw || null;
}

export function isSafeReportFilename(name: string): boolean {
  if (!name || name.length > 180) {
    return false;
  }
  if (name.includes("/") || name.includes("\\") || name.includes("..")) {
    return false;
  }
  if (!/^[\w.\-]+$/.test(name)) {
    return false;
  }
  return name.toLowerCase().endsWith(".html");
}

export function fallbackReportFilename(incidentId: string): string {
  const candidate = `incident-${incidentId}-report.html`;
  return isSafeReportFilename(candidate) ? candidate : "incident-report.html";
}

export function safeReportFilename(header: string | null, incidentId: string): string {
  const parsed = parseContentDispositionFilename(header);
  if (parsed && isSafeReportFilename(parsed)) {
    return parsed;
  }
  return fallbackReportFilename(incidentId);
}

export function isHtmlContentType(contentType: string | null): boolean {
  const value = (contentType ?? "").toLowerCase();
  return value.includes("text/html");
}

export const BLOB_URL_REVOKE_MS = 60_000;

export function saveBlob(
  blob: Blob,
  filename: string,
  revokeAfterMs = BLOB_URL_REVOKE_MS,
): () => void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  const timer = setTimeout(() => URL.revokeObjectURL(url), revokeAfterMs);
  return () => {
    clearTimeout(timer);
    URL.revokeObjectURL(url);
  };
}
