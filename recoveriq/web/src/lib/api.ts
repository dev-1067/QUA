export type User = {
  id: string; name: string; email: string; role: "agent" | "l2" | "l1" | "exec" | "admin"; role_label: string;
  branch_id: string | null; branch: string | null; region_id: string | null; home_lat?: number; home_lng?: number;
};

const KEY = "riq-session";
type Session = { access_token: string; refresh_token: string; user: User };

export const session = {
  get(): Session | null {
    try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; }
  },
  set(s: Session | null) {
    try { s ? localStorage.setItem(KEY, JSON.stringify(s)) : localStorage.removeItem(KEY); } catch { /* private mode */ }
    window.dispatchEvent(new Event("riq-session"));
  },
};

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

let refreshing: Promise<boolean> | null = null;

async function refresh(): Promise<boolean> {
  const s = session.get();
  if (!s) return false;
  refreshing ??= fetch("/api/v1/auth/refresh", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: s.refresh_token }),
  }).then(async (r) => {
    if (!r.ok) { session.set(null); return false; }
    session.set(await r.json());
    return true;
  }).catch(() => false).finally(() => { setTimeout(() => (refreshing = null), 0); });
  return refreshing;
}

function message(body: any, fallback: string) {
  if (!body) return fallback;
  if (typeof body.detail === "string") return body.detail;
  if (body.error?.message) return body.error.message;
  return fallback;
}

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown; auth?: boolean } = {}): Promise<T> {
  const { json, auth = true, ...init } = opts;
  const headers = new Headers(init.headers);
  if (json !== undefined) { headers.set("Content-Type", "application/json"); init.body = JSON.stringify(json); }
  const s = session.get();
  if (auth && s) headers.set("Authorization", `Bearer ${s.access_token}`);
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection.");
  }
  if (res.status === 401 && auth && s && !path.startsWith("/auth/")) {
    if (await refresh()) return api<T>(path, opts);
    throw new ApiError(401, "Your session expired. Please sign in again.");
  }
  const type = res.headers.get("content-type") || "";
  const body = type.includes("application/json") ? await res.json().catch(() => null) : null;
  if (!res.ok) throw new ApiError(res.status, message(body, `Request failed (${res.status})`));
  return body as T;
}

export async function openFile(path: string): Promise<void> {
  // authenticated download (receipts, CSV)
  const s = session.get();
  const res = await fetch(`/api/v1${path}`, { headers: s ? { Authorization: `Bearer ${s.access_token}` } : {} });
  if (res.status === 401 && (await refresh())) return openFile(path);
  if (!res.ok) throw new ApiError(res.status, "Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const disp = res.headers.get("content-disposition") || "";
  const name = /filename="?([^"]+)"?/.exec(disp)?.[1];
  if (blob.type === "application/pdf") window.open(url, "_blank");
  else { const a = document.createElement("a"); a.href = url; a.download = name || "download"; a.click(); }
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
