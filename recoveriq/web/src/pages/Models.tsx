import clsx from "clsx";
import { BrainCircuit, CheckCheck, RotateCcw } from "lucide-react";
import { Card, ErrorBox, PageHeader, Skeleton, Spinner, useAction } from "../components/ui";
import { api } from "../lib/api";
import { dt, num, pct } from "../lib/format";
import { useApi } from "../lib/hooks";

const TONE: Record<string, string> = { active: "bg-ok/10 text-ok", shadow: "bg-info/10 text-info", retired: "bg-sunken text-muted" };

export default function Models() {
  const { data, error, loading, reload } = useApi<any>("/models");
  const { busy, run } = useAction();
  if (error) return <ErrorBox message={error} retry={() => reload()} />;
  const models = data?.models ?? [];
  const shadow = models.find((m: any) => m.status === "shadow");
  const active = models.find((m: any) => m.status === "active");

  return (
    <>
      <PageHeader title="Learning loop" sub="Outcomes recorded here (paid, broken promises, escalations) retrain the self-cure model. A new model runs in shadow next to the live one and only goes live after a manager approves it. Older versions stay available for rollback."
        actions={<button className="btn-primary" disabled={!!busy} onClick={() => run("train", () => api("/models/retrain", { method: "POST" }), (r: any) => `Trained v${r.version} · AUC ${r.metrics.auc}`).then(() => reload(true))}>
          {busy === "train" ? <Spinner /> : <BrainCircuit size={15} />} Retrain now</button>} />
      <p className="text-[12.5px] text-muted -mt-3 mb-5">{data?.note}</p>

      {loading && !data ? <Skeleton className="h-64 rounded-xl" /> : (
        <div className="grid lg:grid-cols-3 gap-4">
          {models.map((m: any) => (
            <Card key={m.id} title={<span className="flex items-center gap-2 font-mono">{m.name} <span className={clsx("chip font-sans", TONE[m.status])}>{m.status}</span></span>}
              sub={`Trained ${dt(m.created_at)} on ${num(m.training_rows)} rows (${num(m.real_outcome_rows)} real outcomes)`}>
              <div className="grid grid-cols-3 gap-2">
                {[["AUC", m.metrics.auc.toFixed(3)], ["Precision@20%", pct(m.metrics.precision_at_20pct, 0)], ["Base rate", pct(m.metrics.base_rate, 0)]].map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-sunken/70 px-2.5 py-2"><div className="label text-[10px]">{k}</div><div className="num font-semibold text-[15px]">{v}</div></div>
                ))}
              </div>
              <div className="label mt-4 mb-2">Feature weights (standardised)</div>
              <div className="space-y-1.5">
                {m.weights.slice(0, 7).map((w: any) => (
                  <div key={w.feature} className="grid grid-cols-[1fr_90px] items-center gap-2 text-[12px]">
                    <span className="truncate">{w.label}</span>
                    <div className="relative h-2 bg-sunken rounded-full">
                      <span className="absolute top-0 bottom-0 left-1/2 w-px bg-line-strong" />
                      <div className={clsx("absolute top-0 bottom-0 rounded-full", w.coef > 0 ? "bg-ok/70 left-1/2" : "bg-bad/70 right-1/2")} style={{ width: `${Math.min(50, Math.abs(w.coef) * 45)}%` }} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-3 border-t border-line flex items-center justify-between">
                <span className="text-[12px] text-muted">{m.approved_by ? `Approved by ${m.approved_by}` : "Not approved"}</span>
                {m.status !== "active" && (
                  <button className={m.status === "shadow" ? "btn-primary btn-sm" : "btn-secondary btn-sm"} disabled={!!busy}
                    onClick={() => run(m.id, () => api(`/models/${m.id}/approve`, { method: "POST" }), `v${m.version} is now live`).then(() => reload(true))}>
                    {busy === m.id ? <Spinner size={13} /> : m.status === "shadow" ? <><CheckCheck size={14} /> Approve & activate</> : <><RotateCcw size={14} /> Roll back to this</>}
                  </button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {shadow && active && data.shadow_comparison.length > 0 && (
        <Card className="mt-4" title={`Shadow comparison · v${shadow.version} vs live v${active.version}`} sub="Self-cure probability for today's highest-priority cases" pad={false}>
          <table className="table">
            <thead><tr><th>Account</th><th className="text-right">Live v{active.version}</th><th className="text-right">Shadow v{shadow.version}</th><th className="text-right">Δ</th></tr></thead>
            <tbody>{data.shadow_comparison.map((r: any) => (
              <tr key={r.case_id}><td className="font-mono text-[12.5px]">{r.account_no}</td><td className="text-right num">{pct(r.active)}</td><td className="text-right num">{pct(r.shadow)}</td>
                <td className={clsx("text-right num font-medium", r.delta > 0 ? "text-ok" : r.delta < 0 ? "text-bad" : "text-muted")}>{r.delta > 0 ? "+" : ""}{(r.delta * 100).toFixed(1)} pp</td></tr>
            ))}</tbody>
          </table>
        </Card>
      )}
    </>
  );
}
