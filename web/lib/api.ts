export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;
  fields: Record<string, string>;
  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    const list = (details.fields as { field: string; message: string }[] | undefined) ?? [];
    this.fields = Object.fromEntries(list.map((f) => [f.field, f.message]));
  }
}

let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
const listeners = new Set<(signedIn: boolean) => void>();

export const setToken = (t: string | null) => {
  accessToken = t;
  listeners.forEach((l) => l(t !== null));
};
export const getToken = () => accessToken;
export const onAuthChange = (fn: (signedIn: boolean) => void) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

const BASE = "/api/v1";

async function parse(res: Response) {
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = null;
  }
  if (!res.ok) {
    const e = (body as { error?: { code: string; message: string; details?: Record<string, unknown> } } | null)?.error;
    throw new ApiError(res.status, e?.code ?? "http_error", e?.message ?? "Something went wrong. Please try again.", e?.details ?? {});
  }
  return body;
}

export async function refreshSession(): Promise<boolean> {
  // The API sets a non-secret hint cookie at sign-in, so anonymous visitors do not trigger a pointless 401.
  if (typeof document !== "undefined" && !document.cookie.split("; ").includes("rw_session=1")) {
    setToken(null);
    return false;
  }
  if (!refreshing) {
    refreshing = fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" })
      .then(async (r) => {
        if (!r.ok) {
          setToken(null);
          return false;
        }
        const data = await r.json();
        setToken(data.access_token);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: FormData;
  headers?: Record<string, string>;
  idempotencyKey?: string;
}

export async function api<T = any>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json", ...opts.headers };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  if (opts.idempotencyKey) headers["Idempotency-Key"] = opts.idempotencyKey;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const res = await fetch(`${BASE}${path}`, { method: opts.method ?? (body ? "POST" : "GET"), headers, body, credentials: "same-origin" });
  if (res.status === 401 && !retried && !path.startsWith("/auth/login") && !path.startsWith("/auth/refresh")) {
    if (await refreshSession()) return api<T>(path, opts, true);
  }
  return (await parse(res)) as T;
}

export const fetcher = (path: string): Promise<any> => api<any>(path);
export const newKey = () => (typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : String(Date.now()) + Math.random());

export const qs = (params: Record<string, string | number | boolean | null | undefined>) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  });
  const s = p.toString();
  return s ? `?${s}` : "";
};
