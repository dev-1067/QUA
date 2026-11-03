import clsx from "clsx";
import { Building2, Laptop, PhoneCall } from "lucide-react";

const STATUS: Record<string, { label: string; cls: string; dot: string }> = {
  NEW: { label: "New", cls: "bg-sunken text-muted", dot: "bg-faint" },
  SCORED: { label: "Scored", cls: "bg-sunken text-muted", dot: "bg-faint" },
  DIGITAL: { label: "Digital self-cure", cls: "bg-digital/10 text-digital", dot: "bg-digital" },
  TELE: { label: "Tele-calling", cls: "bg-tele/10 text-tele", dot: "bg-tele" },
  FIELD: { label: "Field visit", cls: "bg-field/10 text-field", dot: "bg-field" },
  PTP: { label: "Promise to pay", cls: "bg-info/10 text-info", dot: "bg-info" },
  PAYMENT_PENDING: { label: "Awaiting gateway", cls: "bg-warn/10 text-warn", dot: "bg-warn" },
  PAID: { label: "Paid · confirmed", cls: "bg-ok/10 text-ok", dot: "bg-ok" },
  CLOSED: { label: "Closed", cls: "bg-ok/10 text-ok", dot: "bg-ok" },
  BROKEN_PTP: { label: "Promise broken", cls: "bg-bad/10 text-bad", dot: "bg-bad" },
  ESCALATED: { label: "Escalated", cls: "bg-bad/10 text-bad", dot: "bg-bad" },
  DISPUTED: { label: "Disputed", cls: "bg-warn/10 text-warn", dot: "bg-warn" },
};

export function StatusPill({ status, className }: { status: string; className?: string }) {
  const s = STATUS[status] ?? { label: status, cls: "bg-sunken text-muted", dot: "bg-faint" };
  return (
    <span className={clsx("chip", s.cls, className)}>
      <span className={clsx("h-1.5 w-1.5 rounded-full", s.dot, status === "PAYMENT_PENDING" && "animate-pulse")} />
      {s.label}
    </span>
  );
}

export const CHANNEL: Record<string, { label: string; icon: any; cls: string; color: string }> = {
  FIELD: { label: "Field", icon: Building2, cls: "text-field bg-field/10", color: "rgb(var(--field))" },
  TELE: { label: "Tele", icon: PhoneCall, cls: "text-tele bg-tele/10", color: "rgb(var(--tele))" },
  DIGITAL: { label: "Digital", icon: Laptop, cls: "text-digital bg-digital/10", color: "rgb(var(--digital))" },
};

export function ChannelPill({ channel, override }: { channel?: string | null; override?: boolean }) {
  if (!channel) return <span className="chip bg-sunken text-muted">Unrouted</span>;
  const c = CHANNEL[channel];
  const I = c.icon;
  return (
    <span className={clsx("chip", c.cls)} title={override ? "Manual override" : "Decided by channel rules"}>
      <I size={12} strokeWidth={2.2} />
      {c.label}
      {override && <span className="opacity-70">·M</span>}
    </span>
  );
}

const BUCKET: Record<string, string> = {
  "SMA-0": "text-ok border-ok/25", "SMA-1": "text-warn border-warn/25", "SMA-2": "text-field border-field/30",
  NPA: "text-bad border-bad/30", CURRENT: "text-muted border-line",
};
export function BucketPill({ bucket, dpd }: { bucket: string; dpd?: number }) {
  return (
    <span className={clsx("chip border bg-transparent font-mono text-[11px]", BUCKET[bucket] ?? "text-muted border-line")}>
      {bucket}{dpd != null && <span className="text-faint">·{dpd}d</span>}
    </span>
  );
}

export function riskTone(score: number) {
  return score >= 70 ? "bg-bad" : score >= 40 ? "bg-warn" : "bg-ok";
}

export function RiskBar({ score, showValue = true }: { score: number; showValue?: boolean }) {
  return (
    <div className="flex items-center gap-2 min-w-[86px]">
      <div className="h-1.5 flex-1 rounded-full bg-sunken overflow-hidden">
        <div className={clsx("h-full rounded-full transition-[width] duration-700", riskTone(score))} style={{ width: `${Math.max(4, score)}%` }} />
      </div>
      {showValue && <span className="num text-[12.5px] font-medium w-6 text-right">{score}</span>}
    </div>
  );
}

const VER: Record<string, { label: string; cls: string }> = {
  verified: { label: "GPS verified", cls: "bg-ok/10 text-ok" },
  flagged: { label: "Flagged: far from address", cls: "bg-bad/10 text-bad" },
  low_conf: { label: "Low GPS accuracy", cls: "bg-warn/10 text-warn" },
  suspicious: { label: "Impossible travel", cls: "bg-bad/10 text-bad" },
};
export function VerificationPill({ v }: { v: string }) {
  const x = VER[v] ?? { label: v, cls: "bg-sunken text-muted" };
  return <span className={clsx("chip", x.cls)}>{x.label}</span>;
}

export function SentimentPill({ s }: { s?: string | null }) {
  if (!s) return <span className="text-faint">—</span>;
  const cls = s === "positive" ? "bg-ok/10 text-ok" : s === "negative" ? "bg-bad/10 text-bad" : "bg-sunken text-muted";
  return <span className={clsx("chip capitalize", cls)}>{s}</span>;
}

export function Logo({ dark = false, size = 28 }: { dark?: boolean; size?: number }) {
  return (
    <div className="flex items-center gap-2.5 select-none">
      <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
        <rect width="64" height="64" rx="15" fill={dark ? "#f4efe3" : "#10201b"} />
        <path d="M18 46V18h15.5c6.4 0 10.5 3.7 10.5 9.2 0 4.2-2.4 7.3-6.3 8.5L46 46h-8.2l-7.4-9.6H25.4V46H18zm7.4-15.6h7.4c2.6 0 4.1-1.3 4.1-3.4s-1.5-3.4-4.1-3.4h-7.4v6.8z"
          fill={dark ? "#10201b" : "#f4efe3"} />
        <circle cx="48" cy="18" r="5" fill="#2dd4bf" />
      </svg>
      <span className={clsx("font-semibold tracking-tight text-[16px]", dark ? "text-side-text" : "text-ink")}>
        Recover<span className="text-[#2dd4bf]">IQ</span>
      </span>
    </div>
  );
}
