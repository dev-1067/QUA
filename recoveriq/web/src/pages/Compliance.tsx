import { Moon, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, ErrorBox, PageHeader, Segmented, Skeleton, Stat } from "../components/ui";
import { useColors } from "../lib/colors";
import { dt, num } from "../lib/format";
import { useApi } from "../lib/hooks";

export default function Compliance() {
  const [days, setDays] = useState<"7" | "30">("30");
  const { data, error, loading, reload } = useApi<any>(`/compliance/report?days=${days}`);
  const c = useColors();
  if (error) return <ErrorBox message={error} retry={() => reload()} />;
  const [ws, we] = (data?.window ?? "08:00–19:00").split("–").map((t: string) => Number(t.slice(0, 2)));

  return (
    <>
      <PageHeader title="Compliance" sub="Evidence that contact rules held: when borrowers were contacted, what the policy engine blocked, and who looked at personal data."
        actions={<><Segmented value={days} onChange={setDays} items={[{ id: "7", label: "7 days" }, { id: "30", label: "30 days" }]} />
          <button className="btn-secondary" onClick={() => window.print()}>Print report</button></>} />
      {loading && !data ? <Skeleton className="h-96 rounded-xl" /> : data && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4 stagger">
            <Stat label="Contact attempts" value={num(data.total_attempts)} />
            <Stat label="Delivered outside window" value={data.delivered_outside_window} tone={data.delivered_outside_window ? "text-bad" : "text-ok"} icon={<ShieldCheck size={15} />} hint={`allowed window ${data.window}`} />
            <Stat label="Blocked by policy" value={num(data.blocked_total)} tone="text-warn" icon={<Moon size={15} />} />
            <Stat label="PII reveals" value={data.pii_reveals.length} hint="each with a written reason" />
          </div>
          <Card title="Contact attempts by hour (IST)" sub="Shaded band is the allowed window. Blocked bars are attempts the engine stopped and logged.">
            <div className="h-[260px] -ml-2">
              <ResponsiveContainer>
                <BarChart data={data.by_hour} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke={c.line} vertical={false} />
                  <ReferenceArea x1={ws} x2={we - 1} fill={c.brand} fillOpacity={0.07} />
                  <XAxis dataKey="hour" tickFormatter={(h) => `${h}:00`} tick={{ fontSize: 11, fill: c.muted }} axisLine={false} tickLine={false} interval={1} />
                  <YAxis tick={{ fontSize: 11, fill: c.muted }} axisLine={false} tickLine={false} width={40} />
                  <Tooltip cursor={{ fill: c.alpha("line", 0.4) }} contentStyle={{ background: "#17201d", border: "none", borderRadius: 8, color: "#fff", fontSize: 12 }} labelFormatter={(h) => `${h}:00–${h}:59`} />
                  <Bar dataKey="delivered" stackId="a" fill={c.digital} name="Delivered" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="blocked" stackId="a" fill={c.warn} name="Blocked" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <div className="grid lg:grid-cols-2 gap-4 mt-4">
            <Card title="Why attempts were blocked">
              {data.blocked_reasons.length === 0 ? <div className="text-[13px] text-muted">Nothing blocked in this period.</div> : data.blocked_reasons.map((r: any) => (
                <div key={r.reason} className="flex justify-between py-2 border-b border-line last:border-0 text-[13px]"><span>{r.reason}</span><span className="num font-medium">{r.n}</span></div>
              ))}
            </Card>
            <Card title="Personal data reveals" pad={false}>
              <div className="max-h-[280px] overflow-y-auto">
                {data.pii_reveals.length === 0 ? <div className="p-5 text-[13px] text-muted">No reveals in this period.</div> : (
                  <table className="table"><tbody>{data.pii_reveals.map((r: any, i: number) => (
                    <tr key={i}><td className="whitespace-nowrap text-muted text-[12.5px]">{dt(r.ts)}</td><td><div className="text-[13px]">{r.actor}</div><div className="text-[11.5px] text-faint">{r.role}</div></td>
                      <td className="font-mono text-[12px]">{r.case}</td><td className="text-[12.5px]">{r.reason}</td></tr>
                  ))}</tbody></table>
                )}
              </div>
            </Card>
          </div>
          <Card className="mt-4" title="Manual overrides & reassignments" pad={false}>
            {data.overrides.length === 0 ? <div className="p-5 text-[13px] text-muted">No overrides in this period.</div> : (
              <table className="table"><tbody>{data.overrides.map((r: any, i: number) => (
                <tr key={i}><td className="whitespace-nowrap text-muted text-[12.5px]">{dt(r.ts)}</td><td>{r.actor}</td><td className="font-mono text-[12px]">{r.action}</td>
                  <td className="font-mono text-[12px]">{r.case}</td><td className="text-[12.5px]">{r.reason}</td></tr>
              ))}</tbody></table>
            )}
          </Card>
        </>
      )}
    </>
  );
}
