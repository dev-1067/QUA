import clsx from "clsx";
import { FileText, Repeat2, ShieldX, Workflow } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { StatusPill } from "../components/badges";
import { Card, Empty, PageHeader, Skeleton, Spinner, Tabs, useAction } from "../components/ui";
import { api, openFile } from "../lib/api";
import { dt, inr } from "../lib/format";
import { useApi, useLive } from "../lib/hooks";

const RESULT: Record<string, string> = {
  posted: "bg-ok/10 text-ok", duplicate_ignored: "bg-info/10 text-info", rejected_bad_signature: "bg-bad/10 text-bad",
  payment_failed_recorded: "bg-warn/10 text-warn", rejected_amount_exceeds_link: "bg-bad/10 text-bad",
};

export default function Payments() {
  const [tab, setTab] = useState<"ledger" | "webhooks">("ledger");
  const pays = useApi<any[]>("/payments?limit=150");
  const hooks = useApi<any[]>("/payments/webhooks");
  const { data: meta } = useApi<any>("/meta");
  const { busy, run } = useAction();
  const [last, setLast] = useState<any>(null);
  useLive((e) => { if (["payment.confirmed", "payment.failed", "payment.initiated"].includes(e.type)) { pays.reload(true); hooks.reload(true); } });
  const refresh = () => { pays.reload(true); hooks.reload(true); };

  return (
    <>
      <PageHeader title="Payments & webhooks"
        sub="The client can never mark a case paid. Money is recorded only from an HMAC-signed gateway webhook or the reconciliation job, and a gateway payment ID can be posted once."
        actions={<span className="chip bg-sunken text-muted py-1 px-2">Gateway: <b className="text-ink capitalize ml-1">{meta?.gateway ?? "…"}</b>&nbsp;· test mode</span>} />

      <div className="grid md:grid-cols-3 gap-3 mb-4">
        <div className="card p-4">
          <div className="flex items-center gap-2 font-medium text-[13.5px]"><Repeat2 size={16} className="text-info" /> Replay a webhook</div>
          <p className="text-[12.5px] text-muted mt-1 leading-5">Re-send the latest real “paid” webhook with its original signature. Expect <b>duplicate_ignored</b>: no double posting.</p>
          <button className="btn-secondary btn-sm mt-3" disabled={!!busy || !hooks.data?.some((h) => h.result === "posted")}
            onClick={() => { const h = hooks.data!.find((x) => x.result === "posted"); run("replay", () => api(`/payments/webhooks/${h.id}/replay`, { method: "POST" })).then((r) => { if (r) { setLast({ kind: "Replay", ...r }); refresh(); } }); }}>
            {busy === "replay" ? <Spinner size={13} /> : "Replay latest"}</button>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 font-medium text-[13.5px]"><ShieldX size={16} className="text-bad" /> Forged webhook</div>
          <p className="text-[12.5px] text-muted mt-1 leading-5">Send a fake “paid” event with a wrong signature for an open link. Expect <b>401 rejected</b>, case unchanged.</p>
          <button className="btn-secondary btn-sm mt-3" disabled={!!busy}
            onClick={() => run("forge", () => api("/payments/webhooks/forge", { method: "POST" })).then((r) => { if (r) { setLast({ kind: "Forgery test", ...r }); refresh(); } })}>
            {busy === "forge" ? <Spinner size={13} /> : "Send forged event"}</button>
        </div>
        <div className="card p-4">
          <div className="flex items-center gap-2 font-medium text-[13.5px]"><Workflow size={16} className="text-brand" /> Reconciliation</div>
          <p className="text-[12.5px] text-muted mt-1 leading-5">Pull settled payments from the gateway for links whose webhook never arrived. Runs by itself every 10 minutes.</p>
          <button className="btn-secondary btn-sm mt-3" disabled={!!busy}
            onClick={() => run("rec", () => api("/payments/reconcile", { method: "POST" }), (r: any) => `Checked ${r.checked} · posted ${r.posted}`).then(refresh)}>
            {busy === "rec" ? <Spinner size={13} /> : "Run now"}</button>
        </div>
      </div>
      {last && (
        <div className="card p-4 mb-4 animate-rise font-mono text-[12px] leading-5 overflow-x-auto">
          <div className="font-sans text-[12.5px] font-medium mb-1">{last.kind} → HTTP {last.status_code}</div>
          {JSON.stringify(last.response)}
        </div>
      )}

      <Card pad={false}>
        <div className="px-3"><Tabs value={tab} onChange={setTab} items={[{ id: "ledger", label: "Confirmed payments", count: pays.data?.length }, { id: "webhooks", label: "Webhook log", count: hooks.data?.length }]} /></div>
        {tab === "ledger" ? (
          pays.loading && !pays.data ? <div className="p-5"><Skeleton className="h-40" /></div> : !pays.data?.length ? <Empty title="No payments yet" /> : (
            <div className="overflow-x-auto"><table className="table">
              <thead><tr><th>Confirmed</th><th>Account</th><th className="text-right">Amount</th><th>Method</th><th>Gateway payment ID</th><th>Source</th><th>Receipt</th><th>Case</th></tr></thead>
              <tbody>{pays.data.map((p) => (
                <tr key={p.id}>
                  <td className="whitespace-nowrap text-muted">{dt(p.confirmed_at)}</td>
                  <td><Link className="font-mono text-[12.5px] text-brand hover:underline" to={`/app/cases/${p.case_id}`}>{p.account_no}</Link></td>
                  <td className="text-right num font-medium">{inr(p.amount, 2)}</td>
                  <td className="uppercase text-[12px]">{p.method}</td>
                  <td className="font-mono text-[11.5px] text-muted">{p.gateway_payment_id}</td>
                  <td><span className={clsx("chip", p.source === "webhook" ? "bg-ok/10 text-ok" : "bg-info/10 text-info")}>{p.source}</span></td>
                  <td><button className="text-brand text-[12.5px] hover:underline inline-flex items-center gap-1" onClick={() => openFile(`/payments/${p.id}/receipt.pdf`)}><FileText size={13} />{p.receipt_no}</button></td>
                  <td><StatusPill status={p.case_status} /></td>
                </tr>))}
              </tbody></table></div>
          )
        ) : (
          !hooks.data?.length ? <Empty title="No webhooks received yet" body="Pay a link from a borrower page to see the gateway call this endpoint." /> : (
            <div className="overflow-x-auto"><table className="table">
              <thead><tr><th>Received</th><th>Event</th><th>Signature</th><th>Result</th><th>Payment ID</th></tr></thead>
              <tbody>{hooks.data.map((h) => (
                <tr key={h.id} className="animate-fade">
                  <td className="whitespace-nowrap text-muted">{dt(h.received_at)}</td><td className="font-mono text-[12px]">{h.event}</td>
                  <td>{h.signature_ok ? <span className="chip bg-ok/10 text-ok">valid HMAC</span> : <span className="chip bg-bad/10 text-bad">invalid</span>}</td>
                  <td><span className={clsx("chip", RESULT[h.result] ?? "bg-sunken text-muted")}>{h.result.replace(/_/g, " ")}</span></td>
                  <td className="font-mono text-[11.5px] text-muted">{h.gateway_payment_id ?? "—"}</td>
                </tr>))}
              </tbody></table></div>
          )
        )}
      </Card>
    </>
  );
}
