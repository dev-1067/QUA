export const inr = (v: number | null | undefined, digits = 0) =>
  v == null ? "—" : "₹" + Number(v).toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const inrShort = (v: number | null | undefined) => {
  if (v == null) return "—";
  const a = Math.abs(v);
  if (a >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
  if (a >= 1e5) return `₹${(v / 1e5).toFixed(a >= 1e6 ? 1 : 2)} L`;
  if (a >= 1e3) return `₹${(v / 1e3).toFixed(1)}k`;
  return `₹${Math.round(v)}`;
};

export const pct = (v: number | null | undefined, digits = 1) => (v == null ? "—" : `${(v * 100).toFixed(digits)}%`);
export const num = (v: number | null | undefined) => (v == null ? "—" : Number(v).toLocaleString("en-IN"));

const tz = "Asia/Kolkata";
export const dt = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString("en-IN", { timeZone: tz, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: true }) : "—";
export const dateOnly = (iso?: string | null) =>
  iso ? new Date(iso.length === 10 ? iso + "T00:00:00+05:30" : iso).toLocaleDateString("en-IN", { timeZone: tz, day: "2-digit", month: "short", year: "numeric" }) : "—";
export const timeOnly = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleTimeString("en-IN", { timeZone: tz, hour: "2-digit", minute: "2-digit", hour12: true }) : "—";

export function ago(iso?: string | null, nowMs = Date.now()) {
  if (!iso) return "—";
  const s = Math.round((nowMs - new Date(iso).getTime()) / 1000);
  if (s < 45 && s > -45) return "just now";
  if (s < 0) return "in the future";
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} h ago`;
  return `${Math.round(h / 24)} d ago`;
}

export const titleCase = (s?: string | null) => (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
export const LOAN: Record<string, string> = { personal: "Personal", two_wheeler: "Two-wheeler", gold: "Gold", msme: "MSME", consumer_durable: "Consumer durable" };
export const LANG: Record<string, string> = { en: "English", hi: "Hindi", mr: "Marathi" };

export function uuid(): string {
  // randomUUID exists only in secure contexts; a phone opening the app over plain-http LAN needs the fallback
  const c: Crypto = globalThis.crypto;
  if (typeof (c as any).randomUUID === "function") return c.randomUUID();
  const b = c.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
