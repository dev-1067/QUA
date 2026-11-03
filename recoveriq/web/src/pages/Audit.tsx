import clsx from "clsx";
import { Fingerprint, Search, ShieldAlert, ShieldCheck, Undo2 } from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, ErrorBox, PageHeader, Skeleton, Spinner, useAction } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { num } from "../lib/format";
import { useApi, useDebounced } from "../lib/hooks";

export default function Audit() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [action, setAction] = useState("");
  const dq = useDebounced(q, 300);
  const qs = new URLSearchParams({ limit: "120" });
  if (dq) qs.set("q", dq);
  if (action) qs.set("action", action);
  const { data, error, loading, reload } = useApi<any>(`/audit?${qs}`);
  const tamper = useApi<any>("/audit/demo/state");
  const [tamperedRow, setTamperedRow] = useState<number | null>(null);
  useEffect(() => { setTamperedRow(tamper.data?.tampered_row ?? null); }, [tamper.data]);
  const [verify, setVerify] = useState<any>(null);
  const [open, setOpen] = useState<number | null>(null);
  const { busy, run } = useAction();
  const check = () => run("verify", () => api("/audit/verify")).then((r) => r && setVerify(r));
  useEffect(() => { check(); }, []); // eslint-disable-line

  if (error) return <ErrorBox message={error} retry={() => reload()} />;
  const isAdmin = user?.role === "admin";

  return (
    <>
      <PageHeader title="Audit trail" sub="Append-only and hash-chained: each row stores SHA-256(previous hash + its own contents). The database refuses UPDATE and DELETE on this table, and any edit made around the app breaks the chain from that row on."
        actions={<button className="btn-primary" onClick={check} disabled={!!busy}>{busy === "verify" ? <Spinner /> : <Fingerprint size={15} />} Verify chain</button>} />

      {verify && (
        <div className={clsx("card p-4 mb-4 flex flex-wrap items-center gap-4 animate-rise", verify.ok ? "border-ok/30" : "border-bad/40 bg-bad/[0.04]")}>
          <div className={clsx("h-10 w-10 rounded-full flex items-center justify-center", verify.ok ? "bg-ok/10 text-ok" : "bg-bad/10 text-bad")}>
            {verify.ok ? <ShieldCheck size={20} /> : <ShieldAlert size={20} />}
          </div>
          <div className="flex-1 min-w-[240px]">
            <div className="font-semibold text-[14.5px]">{verify.ok ? "Chain intact" : `Tampering detected at row #${verify.broken_at}`}</div>
            <div className="text-[12.5px] text-muted">
              {verify.ok ? <>All {num(verify.checked)} rows re-hashed and matched. Head <span className="font-mono">{verify.head.slice(0, 16)}…</span></> : verify.reason}
            </div>
          </div>
          {isAdmin && (
            tamperedRow ? (
              <button className="btn-secondary btn-sm" disabled={!!busy} onClick={() => run("restore", () => api("/audit/demo/restore", { method: "POST" }), "Original row restored").then((r) => { if (r) setTamperedRow(null); check(); reload(true); })}><Undo2 size={14} /> Restore row</button>
            ) : (
              <button className="btn-danger btn-sm" disabled={!!busy} title="Demo only: edits one row directly in the database, bypassing the app"
                onClick={() => run("tamper", () => api("/audit/demo/tamper", { method: "POST" }), (r: any) => `Row #${r.tampered_row} edited directly in the DB (${r.change})`).then((r: any) => { if (r) setTamperedRow(r.tampered_row); check(); reload(true); })}>
                Simulate insider tampering</button>
            )
          )}
        </div>
      )}

      <Card pad={false}>
        <div className="flex flex-wrap gap-2 p-3 border-b border-line">
          <div className="relative flex-1 min-w-[220px]">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
            <input className="input pl-9" placeholder="Search actor or payload (e.g. account number)…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <select className="select w-auto" value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">All actions</option>{data?.actions.map((a: string) => <option key={a}>{a}</option>)}
          </select>
          <span className="text-[12.5px] text-muted self-center ml-auto">{data ? `${num(data.total)} rows total` : ""}</span>
        </div>
        {loading && !data ? <div className="p-5"><Skeleton className="h-60" /></div> : (
          <div className="overflow-x-auto"><table className="table">
            <thead><tr><th>#</th><th>When</th><th>Actor</th><th>Action</th><th>Details</th><th>Hash</th></tr></thead>
            <tbody>{data?.items.map((r: any) => (
              <Fragment key={r.id}>
                <tr className={clsx("clickable", verify && !verify.ok && verify.broken_at === r.id && "bg-bad/[0.07]")} onClick={() => setOpen(open === r.id ? null : r.id)}>
                  <td className="font-mono text-[12px] text-muted">{r.id}</td>
                  <td className="whitespace-nowrap text-muted text-[12.5px]">{r.ts_local}</td>
                  <td><div className="text-[13px]">{r.actor}</div><div className="text-[11.5px] text-faint">{r.role}</div></td>
                  <td><span className="chip bg-sunken font-mono text-[11.5px]">{r.action}</span></td>
                  <td className="text-[12.5px] text-muted max-w-[380px] truncate">{Object.entries(r.payload).slice(0, 4).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join(" · ")}</td>
                  <td className="font-mono text-[11px] text-faint">{r.hash.slice(0, 10)}…</td>
                </tr>
                {open === r.id && (
                  <tr><td colSpan={6} className="bg-sunken/50">
                    <pre className="font-mono text-[11.5px] whitespace-pre-wrap break-all leading-5">{JSON.stringify(r.payload, null, 2)}</pre>
                    <div className="font-mono text-[11px] text-muted mt-2">prev {r.prev_hash}<br />hash {r.hash}{r.ip && <><br />ip {r.ip}</>}</div>
                  </td></tr>
                )}
              </Fragment>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </>
  );
}
