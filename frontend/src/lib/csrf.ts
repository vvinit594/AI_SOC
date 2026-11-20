export const CSRF_COOKIE_NAME = "aisoc_csrf";
export const CSRF_HEADER_NAME = "X-CSRF-Token";

export function readCsrfToken(): string | null {
  if (typeof document === "undefined") {
    return null;
  }
  const parts = document.cookie.split(";");
  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed.startsWith(`${CSRF_COOKIE_NAME}=`)) {
      return decodeURIComponent(trimmed.slice(CSRF_COOKIE_NAME.length + 1));
    }
  }
  return null;
}

export function csrfHeaders(): Record<string, string> {
  const token = readCsrfToken();
  if (!token) {
    return {};
  }
  return { [CSRF_HEADER_NAME]: token };
}
