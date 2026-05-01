/** Normalize base URL so requests hit `/api/v1/...` (avoids 404 when VITE_API_URL is `http://host:8000` only). */
function normalizeApiBase(env: string | undefined): string {
  if (env == null || env === "") return "/api/v1";
  const u = env.replace(/\/+$/, "");
  if (u.endsWith("/api/v1")) return u;
  if (u.endsWith("/api")) return `${u}/v1`;
  if (/^https?:\/\//i.test(u)) return `${u}/api/v1`;
  return u;
}

export const API_BASE = normalizeApiBase(import.meta.env.VITE_API_URL);
const APP_API_KEY_STORAGE = "ai-sec-test.app_api_key";
const EMBEDDED_APP_API_KEY = typeof import.meta !== "undefined"
  ? String(import.meta.env.VITE_APP_SECRET ?? "").trim()
  : "";

function emitAuthEvent(name: string, detail?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

export function hasEmbeddedAppApiKey(): boolean {
  return EMBEDDED_APP_API_KEY.length > 0;
}

export function getStoredAppApiKey(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(APP_API_KEY_STORAGE)?.trim() ?? "";
}

export function getEffectiveAppApiKey(): string {
  return EMBEDDED_APP_API_KEY || getStoredAppApiKey();
}

export function setStoredAppApiKey(value: string): void {
  if (typeof window === "undefined") return;
  const trimmed = value.trim();
  if (trimmed) {
    window.localStorage.setItem(APP_API_KEY_STORAGE, trimmed);
  } else {
    window.localStorage.removeItem(APP_API_KEY_STORAGE);
  }
  emitAuthEvent("app-api-key-updated", {
    configured: Boolean(trimmed || EMBEDDED_APP_API_KEY),
  });
}

export function clearStoredAppApiKey(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(APP_API_KEY_STORAGE);
  emitAuthEvent("app-api-key-updated", {
    configured: Boolean(EMBEDDED_APP_API_KEY),
  });
}

function buildHeaders(options?: RequestInit): Headers {
  const headers = new Headers(options?.headers ?? {});
  const hasBody = options?.body != null && !(options.body instanceof FormData);
  if (hasBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const apiKey = getEffectiveAppApiKey();
  if (apiKey && !headers.has("X-API-Key")) {
    headers.set("X-API-Key", apiKey);
  }
  return headers;
}

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: buildHeaders(options),
  });
  if (!res.ok) {
    const text = await res.text();
    if (res.status === 401) {
      emitAuthEvent("app-api-auth-required", { path });
    }
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function download(path: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: buildHeaders(),
  });

  if (!res.ok) {
    const text = await res.text();
    if (res.status === 401) {
      emitAuthEvent("app-api-auth-required", { path });
    }
    throw new Error(text || `Request failed: ${res.status}`);
  }

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/i);
  const filename = match?.[1] ?? "download";
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
