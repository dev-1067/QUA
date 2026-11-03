import clsx from "clsx";
import { CalendarClock, FastForward, Siren } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { StatusPill } from "../components/badges";
import { Card, Empty, PageHeader, Skeleton, Spinner, Tabs, useAction } from "../components/ui";
import { api } from "../lib/api";
import { useAuth, can } from "../lib/auth";
import { dateOnly, dt, inr } from "../lib/format";
import { useApi, useLive } from "../lib/hooks";

type Tab = "open" | "broken" | "kept" | "escalations";

export default function Promises() {
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "open";
  const nav = useNavigate();
  const { user } = useAuth();
  const list = useApi<any[]>(tab === "escalations" ? null : `/promises?status=${tab}`, [tab]);
  const esc = useApi<any[]>(can.manage(user) ? "/escalations" : null);
  const { busy, run } = useAction();
  useLive((e) => { if (["ptp.broken", "ptp.created", "payment.confirmed", "clock.changed"].includes(e.type)) { list.reload(true); esc.reload(true); } });

  return (
    <>
      <PageHeader title="Promises & escalations"
        sub="A promise breaks one day after its due date if the gateway hasn't confirmed payment. The first break sends the case to a field visit; the second escalates it to the branch manager."
        actions={<button className="btn-secondary" disabled={!!busy}
          onClick={() => run("ptp", () => api("/scheduler/ptp", { method: "POST" }), (r: any) => `Scheduler ran · ${r.promises_broken} promise(s) broken`).then(() => { list.reload(true); esc.reload(true); })}>
          {busy ? <Spinner /> : <FastForward size={15} />} Run PTP check now</button>} />
      <Card pad={false}>
        <div className="px-3">
          <Tabs value={tab} onChange={(t) => setParams({ tab: t })} items={[
            { id: "open", label: "Open" }, { id: "broken", label: "Broken" }, { id: "kept", label: "Kept" },
            { id: "escalations", label: "Escalations", count: esc.data?.length },
          ]} />
        </div>
        {tab !== "escalations" ? (
          list.loading && !list.data ? <div className="p-5"><Skeleton className="h-40" /></div> : !list.data?.length ? <Empty icon={<CalendarClock size={18} />} title={`No ${tab} promises`} /> : (
            <div className="overflow-x-auto"><table className="table">
              <thead><tr><th>Account</th><th>Borrower</th><th className="text-right">Amount</th><th>Due</th><th>Captured via</th><th>Agent</th><th>Case</th></tr></thead>
              <tbody>{list.data.map((p) => (
                <tr key={p.id} className="clickable" onClick={() => nav(`/app/cases/${p.case_id}`)}>
                  <td className="font-mono text-[12.5px] text-brand">{p.account_no}</td><td>{p.borrower}</td>
                  <td className="text-right num font-medium">{inr(p.amount)}</td>
                  <td className="whitespace-nowrap">
                    {dateOnly(p.promised_date)}
                    {tab === "open" && <span className={clsx("chip ml-2", p.days_left < 0 ? "bg-bad/10 text-bad" : p.days_left <= 1 ? "bg-warn/10 text-warn" : "bg-sunken text-muted")}>
                      {p.days_left < 0 ? `${-p.days_left} d overdue` : p.days_left === 0 ? "today" : `in ${p.days_left} d`}</span>}
                    {tab !== "open" && <span className="text-[12px] text-muted block">{tab} {dt(p.resolved_at)}</span>}
                  </td>
                  <td className="text-muted capitalize">{p.channel}</td><td className="text-muted">{p.agent ?? "—"}</td><td><StatusPill status={p.case_status} /></td>
                </tr>))}
              </tbody></table></div>
          )
        ) : (
          !esc.data?.length ? <Empty icon={<Siren size={18} />} title="Nothing escalated" body="Cases land here after repeated broken promises." /> : (
            <div className="overflow-x-auto"><table className="table">
              <thead><tr><th>Account</th><th>Borrower</th><th>Status</th><th className="text-right">Broken</th><th className="text-right">Risk</th><th className="text-right">Overdue</th><th>Agent</th><th>Escalated to</th></tr></thead>
              <tbody>{esc.data.map((c) => (
                <tr key={c.id} className="clickable" onClick={() => nav(`/app/cases/${c.id}`)}>
                  <td className="font-mono text-[12.5px] text-brand">{c.account_no}</td><td>{c.borrower}</td><td><StatusPill status={c.status} /></td>
                  <td className="text-right num text-bad font-medium">{c.broken_ptp_count}</td><td className="text-right num">{c.risk_score}</td>
                  <td className="text-right num">{inr(c.amount_due)}</td><td className="text-muted">{c.agent ?? "—"}</td><td>{c.escalated_to ?? "—"}</td>
                </tr>))}
              </tbody></table></div>
          )
        )}
      </Card>
    </>
  );
}
