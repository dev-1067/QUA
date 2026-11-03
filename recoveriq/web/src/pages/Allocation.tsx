import clsx from "clsx";
import { Scale, Shuffle, Users } from "lucide-react";
import { useState } from "react";
import { Card, ErrorBox, PageHeader, Skeleton, Spinner, Stat, useAction } from "../components/ui";
import { api } from "../lib/api";
import { pct } from "../lib/format";
import { useApi } from "../lib/hooks";

export default function Allocation() {
  const [branch, setBranch] = useState("");
  const { data, error, loading, reload } = useApi<any>(`/allocation/workload${branch ? `?branch_id=${branch}` : ""}`);
  const { busy, run } = useAction();
  const [before, setBefore] = useState<Record<string, number> | null>(null);

  const act = (kind: "run" | "rebalance") => {
    setBefore(Object.fromEntries((data?.agents ?? []).map((a: any) => [a.id, a.load])));
    run(kind, () => api(`/allocation/${kind}${branch ? `?branch_id=${branch}` : ""}`, { method: "POST" }),
      (r: any) => (kind === "run" ? `Assigned ${r.assigned} case(s)${r.skipped_no_capacity ? ` · ${r.skipped_no_capacity} waiting for capacity` : ""}` : `Moved ${r.moved} case(s) to even out workload`))
      .then(() => reload(true));
  };
  if (error) return <ErrorBox message={error} retry={() => reload()} />;
  const agents = data?.agents ?? [];
  const util = agents.map((a: any) => a.utilisation);
  const spread = util.length ? Math.max(...util) - Math.min(...util) : 0;

  return (
    <>
      <PageHeader title="Allocation" sub="Field and tele cases go to agents by pincode cluster and DPD bucket, weighted by proximity, the agent's recovery record in that bucket, and spare capacity."
        actions={<>
          <select className="select w-auto" value={branch} onChange={(e) => { setBranch(e.target.value); setBefore(null); }}>
            <option value="">All branches in scope</option>{data?.branches.map((b: any) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <button className="btn-secondary" disabled={!!busy} onClick={() => act("rebalance")}>{busy === "rebalance" ? <Spinner /> : <Scale size={15} />} Rebalance</button>
          <button className="btn-primary" disabled={!!busy} onClick={() => act("run")}>{busy === "run" ? <Spinner /> : <Shuffle size={15} />} Allocate unassigned</button>
        </>} />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4 stagger">
        <Stat label="Unassigned field/tele" value={data?.unassigned ?? "—"} tone={data?.unassigned ? "text-warn" : undefined} />
        <Stat label="Agents" value={agents.length || "—"} icon={<Users size={15} />} />
        <Stat label="Avg utilisation" value={agents.length ? pct(util.reduce((a: number, b: number) => a + b, 0) / util.length, 0) : "—"} />
        <Stat label="Utilisation spread" value={agents.length ? pct(spread, 0) : "—"} hint="max − min; rebalance narrows it" tone={spread > 0.35 ? "text-warn" : "text-ok"} />
      </div>

      <Card title="Workload by agent" sub="Bar = open cases ÷ capacity. Ghost marker shows the load before your last action.">
        {loading && !data ? <Skeleton className="h-72" /> : (
          <div className="space-y-2.5">
            {agents.map((a: any) => {
              const w = Math.min(100, a.utilisation * 100);
              const prev = before?.[a.id];
              const delta = prev != null ? a.load - prev : 0;
              return (
                <div key={a.id} className="grid grid-cols-[180px_1fr_92px] items-center gap-3">
                  <div className="min-w-0">
                    <div className="text-[13px] font-medium truncate">{a.name}</div>
                    <div className="text-[11.5px] text-muted truncate">{a.branch}</div>
                  </div>
                  <div className="relative h-6 rounded-md bg-sunken overflow-hidden">
                    <div className={clsx("absolute inset-y-0 left-0 rounded-md transition-[width] duration-700 ease-out",
                      a.utilisation > 0.92 ? "bg-bad/70" : a.utilisation > 0.75 ? "bg-warn/70" : "bg-brand/70")} style={{ width: `${w}%` }} />
                    {prev != null && <div className="absolute inset-y-0 w-0.5 bg-ink/50" style={{ left: `${Math.min(100, (prev / a.capacity) * 100)}%` }} />}
                  </div>
                  <div className="text-right text-[12.5px] num">
                    <span className="font-medium">{a.load}</span><span className="text-faint">/{a.capacity}</span>
                    {delta !== 0 && <span className={clsx("ml-1.5 text-[11.5px] font-medium", delta > 0 ? "text-ok" : "text-warn")}>{delta > 0 ? "+" : ""}{delta}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <div className="mt-5 pt-4 border-t border-line text-[12.5px] text-muted leading-5">
          <span className="font-mono text-ink">fit = 0.45·proximity + 0.30·bucket_recovery + 0.25·(1 − load/capacity)</span>. Highest-priority cases are placed first;
          capacity is never exceeded. Rebalance moves the lowest-priority open cases from the busiest to the least-busy agent in the same branch.
        </div>
      </Card>
    </>
  );
}
