import clsx from "clsx";
import { Award, CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";
import { Card, Drawer, PageHeader, Segmented, Skeleton } from "../components/ui";
import { dt, inr, num } from "../lib/format";
import { useApi } from "../lib/hooks";

export default function Leaderboard() {
  const [days, setDays] = useState<"7" | "30">("30");
  const { data, loading } = useApi<any>(`/leaderboard?days=${days}`);
  const [sel, setSel] = useState<any>(null);
  const rows = data?.rows ?? [];
  const top = rows[0]?.points || 1;

  return (
    <>
      <PageHeader title="Leaderboard" sub="Points come only from evidence the system can check, so nobody can type their way up the table. Tap an agent to see every payment and visit behind their score."
        actions={<Segmented value={days} onChange={setDays} items={[{ id: "7", label: "7 days" }, { id: "30", label: "30 days" }]} />} />
      <div className="card px-5 py-3 mb-4 text-[13px] flex flex-wrap items-center gap-2">
        <Award size={16} className="text-brand" /> <span className="text-muted">Points =</span>
        <span className="font-mono text-[12.5px]">{data?.formula ?? "…"}</span>
        <span className="text-muted">· flagged or unverified visits earn 0</span>
      </div>
      <Card pad={false}>
        {loading && !data ? <div className="p-5"><Skeleton className="h-72" /></div> : (
          <ul className="divide-y divide-line">
            {rows.map((r: any) => (
              <li key={r.id} onClick={() => setSel(r)} className="px-5 py-3 flex items-center gap-4 cursor-pointer hover:bg-sunken/70 transition-colors">
                <span className={clsx("h-8 w-8 rounded-full flex items-center justify-center text-[13px] font-semibold num shrink-0",
                  r.rank === 1 ? "bg-[#f5d77a] text-[#5c4300]" : r.rank === 2 ? "bg-[#dfe3e6] text-[#3d4448]" : r.rank === 3 ? "bg-[#ecc39d] text-[#5a3112]" : "bg-sunken text-muted")}>{r.rank}</span>
                <div className="w-48 min-w-0">
                  <div className="text-[13.5px] font-medium truncate">{r.name}</div>
                  <div className="text-[12px] text-muted truncate">{r.branch}</div>
                </div>
                <div className="flex-1 hidden sm:block">
                  <div className="h-2 rounded-full bg-sunken overflow-hidden"><div className="h-full rounded-full bg-brand transition-[width] duration-700" style={{ width: `${(r.points / top) * 100}%` }} /></div>
                </div>
                <div className="hidden md:grid grid-cols-3 gap-6 text-[12.5px] text-right">
                  <div><div className="num font-medium">{inr(r.collected)}</div><div className="text-muted text-[11.5px]">collected</div></div>
                  <div><div className="num font-medium">{r.verified_visits}</div><div className="text-muted text-[11.5px]">verified visits</div></div>
                  <div><div className="num font-medium">{r.kept_ptps}</div><div className="text-muted text-[11.5px]">kept promises</div></div>
                </div>
                <div className="w-20 text-right"><div className="text-[17px] font-semibold num">{num(r.points)}</div><div className="text-[11px] text-muted">points</div></div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Drawer open={!!sel} onClose={() => setSel(null)} title={sel ? `${sel.name} · ${num(sel.points)} points` : ""}>
        {sel && (
          <div className="space-y-6 text-[13px]">
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg bg-sunken p-3"><div className="label">₹ ÷ 100</div><div className="num text-[17px] font-semibold">{num(Math.round(sel.collected / 100))}</div></div>
              <div className="rounded-lg bg-sunken p-3"><div className="label">5 × visits</div><div className="num text-[17px] font-semibold">{sel.verified_visits * 5}</div></div>
              <div className="rounded-lg bg-sunken p-3"><div className="label">10 × kept</div><div className="num text-[17px] font-semibold">{sel.kept_ptps * 10}</div></div>
            </div>
            <section>
              <div className="label mb-2">Gateway-confirmed payments</div>
              {sel.proof.payments.length === 0 ? <div className="text-muted">None in this period.</div> : sel.proof.payments.map((p: any) => (
                <div key={p.gateway_payment_id} className="flex justify-between py-1.5 border-b border-line"><span><span className="font-mono text-[12px]">{p.account_no}</span> <span className="text-muted">· {p.receipt_no}</span></span><span className="num">{inr(p.amount)}</span></div>
              ))}
            </section>
            <section>
              <div className="label mb-2">Visits</div>
              {sel.proof.visits.map((v: any, i: number) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b border-line">
                  <span className="flex items-center gap-1.5">{v.counts ? <CheckCircle2 size={14} className="text-ok" /> : <XCircle size={14} className="text-bad" />}<span className="font-mono text-[12px]">{v.account_no}</span></span>
                  <span className="text-muted">{v.verification.replace("_", " ")} · {Math.round(v.distance_m)} m · {dt(v.ts)}</span>
                </div>
              ))}
            </section>
            <section>
              <div className="label mb-2">Kept promises</div>
              {sel.proof.kept_ptps.length === 0 ? <div className="text-muted">None in this period.</div> : sel.proof.kept_ptps.map((p: any, i: number) => (
                <div key={i} className="flex justify-between py-1.5 border-b border-line"><span className="font-mono text-[12px]">{p.account_no}</span><span className="num">{inr(p.amount)}</span></div>
              ))}
            </section>
          </div>
        )}
      </Drawer>
    </>
  );
}
