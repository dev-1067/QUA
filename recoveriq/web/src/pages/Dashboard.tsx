import clsx from "clsx";
import {
  AlertOctagon, ArrowUpRight, BadgeIndianRupee, CircleDollarSign, Gauge, HandCoins, Layers, MapPin, Percent, Radio, Receipt,
} from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { CHANNEL } from "../components/badges";
import { Card, CountUp, ErrorBox, PageHeader, Segmented, Skeleton, Stat } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useColors } from "../lib/colors";
import { ago, inr, inrShort, num, pct } from "../lib/format";
import { useApi, useLive, useNow } from "../lib/hooks";

type Feed = { id: number; kind: string; title: string; sub: string; ts: string; case_id?: string };

function ChartTip({ active, payload, label, fmt }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg bg-[#17201d] text-white px-3 py-2 text-[12px] shadow-pop">
      <div className="text-white/60 mb-0.5">{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 num">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.payload?.fill }} />
          {fmt ? fmt(p.value, p.dataKey) : p.value}
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const [days, setDays] = useState<"7" | "30">("30");
  const { data, error, loading, reload } = useApi<any>(`/dashboards/summary?days=${days}`, []);
  const c = useColors();
  const nav = useNavigate();
  const now = useNow(20000);
  const [feed, setFeed] = useState<Feed[]>([]);
  const [ageMode, setAgeMode] = useState<"amount" | "count">("amount");

  useLive((e) => {
    const map: Record<string, [string, string]> = {
      "payment.confirmed": ["pay", `Payment confirmed · ${e.account_no}`],
      "field.checkin": ["visit", `${e.agent_name} checked in · ${e.account_no}`],
      "ptp.created": ["ptp", `Promise recorded · ${e.account_no}`],
      "ptp.broken": ["broken", `Promise broken · ${e.account_no}`],
      "note.created": ["note", `New borrower note · ${e.account_no}`],
      "contact.blocked": ["block", `Contact blocked by policy · ${e.account_no}`],
      "contact.nudge": ["nudge", `Nudge delivered · ${e.account_no}`],
      "payment.initiated": ["pending", `Borrower opened checkout · ${e.account_no}`],
      "dispute.raised": ["broken", `Dispute raised · ${e.account_no}`],
    };
    const m = map[e.type];
    if (!m) return;
    const sub = e.type === "payment.confirmed" ? `${inr(e.amount)} · ${e.receipt_no}` :
      e.type === "field.checkin" ? `${String(e.verification).replace("_", " ")} · ${String(e.outcome).replace(/_/g, " ")}` : e.status ?? "";
    setFeed((f) => [{ id: Date.now() + Math.random(), kind: m[0], title: m[1], sub, ts: new Date().toISOString(), case_id: e.case_id }, ...f].slice(0, 14));
    if (["payment.confirmed", "ptp.broken"].includes(e.type)) reload(true);
  });

  if (error) return <ErrorBox message={error} retry={() => reload()} />;
  const k = data?.kpis;
  const first = user?.name.split(" ")[0];
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <>
      <PageHeader
        title={`${greet}, ${first}`}
        sub="Portfolio health, collections and field activity across your scope. Numbers update as payments are confirmed by the gateway."
        actions={<Segmented value={days} onChange={setDays} items={[{ id: "7", label: "7 days" }, { id: "30", label: "30 days" }]} />}
      />

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 stagger">
        {loading && !k ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[92px] rounded-xl" />) : k && (
          <>
            <Stat label="Overdue book" icon={<Layers size={15} />} value={<CountUp value={k.overdue_amount} format={inrShort} />} hint={`${num(k.open_cases)} open accounts`} />
            <Stat label="Collected" icon={<BadgeIndianRupee size={15} />} tone="text-ok" value={<CountUp value={k.collected} format={inrShort} />} hint={`${num(k.payments)} gateway-confirmed payments`} />
            <Stat label="Collection rate" icon={<Percent size={15} />} value={pct(k.collection_rate)} hint="collected ÷ (collected + overdue)" />
            <Stat label="Cost per ₹100" icon={<Receipt size={15} />} value={k.cost_per_recovery == null ? "—" : `₹${(k.cost_per_recovery * 100).toFixed(2)}`} hint={`${inrShort(k.spend)} spent on visits & messages`} />
            <Stat label="Digital self-cure" icon={<Gauge size={15} />} tone="text-digital" value={pct(k.self_cure_rate)} hint="paid without a field visit" />
            <Stat label="Promises kept" icon={<HandCoins size={15} />} value={pct(k.ptp_kept_rate)} hint={`${num(k.ptp_open)} still open`} />
          </>
        )}
      </div>

      {k && (k.awaiting_gateway > 0 || k.escalated > 0 || k.disputed > 0) && (
        <div className="mt-3 flex flex-wrap gap-2 animate-fade">
          {k.awaiting_gateway > 0 && <Link to="/app/cases?status=PAYMENT_PENDING" className="chip bg-warn/10 text-warn py-1 px-2 text-[12.5px]"><CircleDollarSign size={13} /> {k.awaiting_gateway} awaiting gateway confirmation</Link>}
          {k.escalated > 0 && <Link to="/app/promises?tab=escalations" className="chip bg-bad/10 text-bad py-1 px-2 text-[12.5px]"><AlertOctagon size={13} /> {k.escalated} escalated to managers</Link>}
          {k.disputed > 0 && <Link to="/app/disputes" className="chip bg-sunken text-muted py-1 px-2 text-[12.5px]">{k.disputed} open disputes</Link>}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-5">
        <Card className="xl:col-span-2" title="Collections" sub="Daily amount confirmed by the payment gateway">
          <div className="h-[240px] -ml-2">
            {data ? (
              <ResponsiveContainer>
                <AreaChart data={data.trend} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={c.brand} stopOpacity={0.28} />
                      <stop offset="100%" stopColor={c.brand} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={c.line} vertical={false} />
                  <XAxis dataKey="date" tickFormatter={(d) => new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}
                    tick={{ fontSize: 11, fill: c.muted }} axisLine={false} tickLine={false} minTickGap={24} />
                  <YAxis tickFormatter={(v) => inrShort(v)} tick={{ fontSize: 11, fill: c.muted }} axisLine={false} tickLine={false} width={64} />
                  <Tooltip content={<ChartTip fmt={(v: number) => inr(v)} />} cursor={{ stroke: c.line }} />
                  <Area type="monotone" dataKey="amount" stroke={c.brand} strokeWidth={2} fill="url(#g1)" animationDuration={900} />
                </AreaChart>
              </ResponsiveContainer>
            ) : <Skeleton className="h-full" />}
          </div>
        </Card>

        <Card title="Channel mix" sub="Open accounts by routing decision">
          {data ? (
            <div className="flex items-center gap-4">
              <div className="h-[180px] w-[180px] shrink-0">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={["FIELD", "TELE", "DIGITAL"].map((ch) => ({ name: ch, value: data.by_channel[ch] || 0 }))}
                      dataKey="value" innerRadius={56} outerRadius={84} paddingAngle={2} stroke="none" animationDuration={800}>
                      {["FIELD", "TELE", "DIGITAL"].map((ch) => <Cell key={ch} fill={c[ch.toLowerCase() as "field"]} />)}
                    </Pie>
                    <Tooltip content={<ChartTip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-3 flex-1">
                {["FIELD", "TELE", "DIGITAL"].map((ch) => {
                  const total = ["FIELD", "TELE", "DIGITAL"].reduce((s, x) => s + (data.by_channel[x] || 0), 0) || 1;
                  const v = data.by_channel[ch] || 0;
                  const I = CHANNEL[ch].icon;
                  return (
                    <Link key={ch} to={`/app/cases?channel=${ch}`} className="block group">
                      <div className="flex items-center justify-between text-[13px]">
                        <span className="flex items-center gap-2"><I size={14} style={{ color: c[ch.toLowerCase() as "field"] }} />{CHANNEL[ch].label}</span>
                        <span className="num font-medium group-hover:text-brand">{num(v)}</span>
                      </div>
                      <div className="text-[11.5px] text-muted">{pct(v / total, 0)} of open book</div>
                    </Link>
                  );
                })}
              </div>
            </div>
          ) : <Skeleton className="h-[180px]" />}
        </Card>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
        <Card title="Ageing" sub="Open overdue by DPD bucket" actions={<Segmented size="sm" value={ageMode} onChange={setAgeMode} items={[{ id: "amount", label: "₹" }, { id: "count", label: "#" }]} />}>
          <div className="h-[220px] -ml-2">
            {data ? (
              <ResponsiveContainer>
                <BarChart data={data.ageing.filter((a: any) => a.bucket !== "CURRENT")} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke={c.line} vertical={false} />
                  <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: c.muted }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v) => (ageMode === "amount" ? inrShort(v) : v)} tick={{ fontSize: 11, fill: c.muted }} axisLine={false} tickLine={false} width={58} />
                  <Tooltip content={<ChartTip fmt={(v: number) => (ageMode === "amount" ? inr(v) : `${v} accounts`)} />} cursor={{ fill: c.alpha("line", 0.4) }} />
                  <Bar dataKey={ageMode} radius={[6, 6, 0, 0]} animationDuration={700}>
                    {data.ageing.filter((a: any) => a.bucket !== "CURRENT").map((a: any) => (
                      <Cell key={a.bucket} fill={{ "SMA-0": c.ok, "SMA-1": c.warn, "SMA-2": c.field, NPA: c.bad }[a.bucket as "NPA"] || c.muted} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : <Skeleton className="h-full" />}
          </div>
        </Card>

        <Card className="xl:col-span-2" title={<span className="flex items-center gap-2">Live activity <span className="h-1.5 w-1.5 rounded-full bg-ok pulse-dot text-ok" /></span>}
          sub="Events stream in over WebSocket as agents and borrowers act" actions={<Link to="/app/field" className="btn-ghost btn-sm"><MapPin size={14} /> Field map</Link>}>
          {feed.length === 0 ? (
            <div className="h-[220px] flex flex-col items-center justify-center text-center text-muted">
              <Radio size={20} className="text-faint" />
              <div className="text-[13px] mt-2">Listening for check-ins, payments and promises…</div>
              <div className="text-[12px] text-faint mt-1">Open the agent app or a pay link in another tab to see events arrive here.</div>
            </div>
          ) : (
            <ul className="h-[220px] overflow-y-auto -mx-1 pr-1">
              {feed.map((f) => (
                <li key={f.id} onClick={() => f.case_id && nav(`/app/cases/${f.case_id}`)}
                  className="animate-slideIn flex items-center gap-3 px-1 py-2 rounded-lg hover:bg-sunken cursor-pointer">
                  <span className={clsx("h-2 w-2 rounded-full shrink-0",
                    { pay: "bg-ok", visit: "bg-field", ptp: "bg-info", broken: "bg-bad", note: "bg-tele", block: "bg-warn", nudge: "bg-digital", pending: "bg-warn" }[f.kind])} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[13px] truncate">{f.title}</div>
                    <div className="text-[12px] text-muted truncate capitalize">{f.sub}</div>
                  </div>
                  <span className="text-[11.5px] text-faint shrink-0">{ago(f.ts, now)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card className="mt-4" title="Agent performance" sub={`Last ${days} days · only gateway-confirmed money and verified visits count`} pad={false}
        actions={<Link to="/app/leaderboard" className="btn-ghost btn-sm">Leaderboard <ArrowUpRight size={14} /></Link>}>
        <div className="overflow-x-auto">
          <table className="table">
            <thead><tr><th>Agent</th><th>Branch</th><th className="text-right">Workload</th><th className="text-right">Visits</th><th className="text-right">Verified</th><th className="text-right">Promises</th><th className="text-right">Kept</th><th className="text-right">Collected</th></tr></thead>
            <tbody>
              {(data?.agents ?? []).slice(0, 12).map((a: any) => (
                <tr key={a.id}>
                  <td className="font-medium">{a.name}</td>
                  <td className="text-muted">{a.branch}</td>
                  <td className="text-right num">
                    <span className={clsx(a.load / a.capacity > 0.9 && "text-warn")}>{a.load}</span><span className="text-faint">/{a.capacity}</span>
                  </td>
                  <td className="text-right num">{a.visits}</td>
                  <td className="text-right num">{pct(a.verified_pct, 0)}</td>
                  <td className="text-right num">{a.ptp_taken}</td>
                  <td className="text-right num">{pct(a.ptp_kept_pct, 0)}</td>
                  <td className="text-right num font-medium">{inr(a.collected)}</td>
                </tr>
              ))}
              {loading && !data && <tr><td colSpan={8}><Skeleton className="h-6" /></td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
