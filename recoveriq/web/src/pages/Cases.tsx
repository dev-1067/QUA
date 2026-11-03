import clsx from "clsx";
import { ArrowDownWideNarrow, ChevronLeft, ChevronRight, Filter, Search, SearchX, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { BucketPill, ChannelPill, RiskBar, StatusPill } from "../components/badges";
import { Card, Empty, ErrorBox, PageHeader, Skeleton } from "../components/ui";
import { inr, LOAN, num, pct } from "../lib/format";
import { useApi, useDebounced, useLive } from "../lib/hooks";

const STATUSES = ["DIGITAL", "TELE", "FIELD", "PTP", "PAYMENT_PENDING", "BROKEN_PTP", "ESCALATED", "DISPUTED", "PAID", "CLOSED"];
const BUCKETS = ["SMA-0", "SMA-1", "SMA-2", "NPA", "CURRENT"];
const PAGE = 25;

export default function Cases() {
  const [params, setParams] = useSearchParams();
  const nav = useNavigate();
  const [q, setQ] = useState(params.get("q") ?? "");
  const dq = useDebounced(q, 300);
  const status = params.get("status") ?? "";
  const bucket = params.get("bucket") ?? "";
  const channel = params.get("channel") ?? "";
  const sort = params.get("sort") ?? "priority";
  const page = Number(params.get("page") ?? 0);
  const defaults = params.get("default") === "1";
  const set = (k: string, v: string) => {
    const p = new URLSearchParams(params);
    v ? p.set(k, v) : p.delete(k);
    if (k !== "page") p.delete("page");
    setParams(p, { replace: true });
  };
  useEffect(() => { if ((params.get("q") ?? "") !== dq) set("q", dq); /* eslint-disable-next-line */ }, [dq]);

  const qs = new URLSearchParams({ limit: String(PAGE), offset: String(page * PAGE), sort });
  if (status) qs.set("status", status);
  if (bucket) qs.set("bucket", bucket);
  if (channel) qs.set("channel", channel);
  if (dq) qs.set("q", dq);
  if (defaults) qs.set("default_only", "true");
  const { data, error, loading, reload } = useApi<any>(`/cases?${qs}`);
  const [flash, setFlash] = useState<Record<string, number>>({});
  useLive((e) => {
    if (!e.case_id || !data?.items?.some((c: any) => c.id === e.case_id)) return;
    setFlash((f) => ({ ...f, [e.case_id]: Date.now() }));
    reload(true);
  });

  const filters = [status, bucket, channel, dq, defaults ? "1" : ""].filter(Boolean).length;
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;

  return (
    <>
      <PageHeader title="Case queue" sub="One record per loan account, ranked by priority. Priority blends risk, amount at stake and days past due." />
      <Card pad={false}>
        <div className="flex flex-wrap items-center gap-2 p-3 border-b border-line">
          <div className="relative flex-1 min-w-[220px]">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
            <input className="input pl-9" placeholder="Search account no., city, pincode or name…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <Filter size={15} className="text-faint ml-1 hidden sm:block" />
          <select className="select w-auto min-w-[150px]" value={status} onChange={(e) => set("status", e.target.value)}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase())}</option>)}
          </select>
          <select className="select w-auto" value={channel} onChange={(e) => set("channel", e.target.value)}>
            <option value="">All channels</option><option value="FIELD">Field</option><option value="TELE">Tele</option><option value="DIGITAL">Digital</option>
          </select>
          <select className="select w-auto" value={bucket} onChange={(e) => set("bucket", e.target.value)}>
            <option value="">All buckets</option>{BUCKETS.map((b) => <option key={b}>{b}</option>)}
          </select>
          <label className="flex items-center gap-2 text-[13px] text-muted px-2 cursor-pointer select-none">
            <input type="checkbox" className="accent-[rgb(var(--brand))]" checked={defaults} onChange={(e) => set("default", e.target.checked ? "1" : "")} />
            Default only
          </label>
          <div className="flex items-center gap-1.5 ml-auto">
            <ArrowDownWideNarrow size={15} className="text-faint" />
            <select className="select w-auto" value={sort} onChange={(e) => set("sort", e.target.value)}>
              <option value="priority">Priority</option><option value="risk">Risk score</option><option value="dpd">Days past due</option>
              <option value="amount">Overdue amount</option><option value="selfcure">Self-cure chance</option><option value="updated">Recently updated</option>
            </select>
          </div>
          {filters > 0 && <button className="btn-ghost btn-sm" onClick={() => { setQ(""); setParams({}, { replace: true }); }}><X size={14} /> Clear</button>}
        </div>

        {error ? <div className="p-4"><ErrorBox message={error} retry={() => reload()} /></div> : (
          <div className="overflow-x-auto">
            <table className="table">
              <thead>
                <tr>
                  <th>Account</th><th>Borrower</th><th>Loan</th><th>Bucket</th><th className="text-right">Overdue</th>
                  <th>Risk</th><th className="text-right">Self-cure</th><th>Channel</th><th>Status</th><th>Agent</th>
                </tr>
              </thead>
              <tbody>
                {loading && !data && Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}><td colSpan={10}><Skeleton className="h-5" /></td></tr>
                ))}
                {data?.items.map((c: any) => (
                  <tr key={c.id} className={clsx("clickable", flash[c.id] && Date.now() - flash[c.id] < 2500 && "bg-brand-soft/60")}
                    onClick={() => nav(`/app/cases/${c.id}`)}>
                    <td>
                      <div className="font-mono text-[12.5px] font-medium text-brand">{c.account_no}</div>
                      {c.is_default && <span className="chip bg-bad/10 text-bad mt-1">Default</span>}
                    </td>
                    <td>
                      <div className="font-medium">{c.borrower_name}</div>
                      <div className="text-[12px] text-muted">{c.city} · {c.pincode}</div>
                    </td>
                    <td className="text-muted whitespace-nowrap">{LOAN[c.loan_type]}</td>
                    <td><BucketPill bucket={c.dpd_bucket} dpd={c.dpd} /></td>
                    <td className="text-right num font-medium whitespace-nowrap">{inr(c.amount_due)}</td>
                    <td><RiskBar score={c.risk_score} /></td>
                    <td className="text-right num text-muted">{pct(c.p_selfcure, 0)}</td>
                    <td><ChannelPill channel={c.channel} override={c.channel_override} /></td>
                    <td><StatusPill status={c.status} /></td>
                    <td className="text-muted whitespace-nowrap">{c.agent_name ?? <span className="text-faint">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data && data.items.length === 0 && <Empty icon={<SearchX size={18} />} title="No cases match these filters" body="Try clearing a filter or searching a different city or account number." />}
          </div>
        )}
        {data && data.total > 0 && (
          <div className="flex items-center justify-between px-4 py-3 text-[12.5px] text-muted">
            <span className="num">{num(page * PAGE + 1)}–{num(Math.min(data.total, (page + 1) * PAGE))} of {num(data.total)}</span>
            <div className="flex items-center gap-1">
              <button className="btn-secondary btn-sm px-2" disabled={page === 0} onClick={() => set("page", String(page - 1))} aria-label="Previous page"><ChevronLeft size={15} /></button>
              <span className="px-2 num">{page + 1} / {pages}</span>
              <button className="btn-secondary btn-sm px-2" disabled={page + 1 >= pages} onClick={() => set("page", String(page + 1))} aria-label="Next page"><ChevronRight size={15} /></button>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
