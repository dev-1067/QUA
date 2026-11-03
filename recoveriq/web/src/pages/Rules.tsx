import clsx from "clsx";
import { FlaskConical, History, Save } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Card, ErrorBox, Field, PageHeader, Skeleton, Spinner, useAction } from "../components/ui";
import { api } from "../lib/api";
import { can, useAuth } from "../lib/auth";
import { dt } from "../lib/format";
import { useApi } from "../lib/hooks";

function Section({ kind, title, sub, rules, editable, children, onSave, busy, note, setNote, extra }: {
  kind: string; title: string; sub: string; rules: any; editable: boolean; children: ReactNode; onSave: () => void; busy: boolean;
  note: string; setNote: (s: string) => void; extra?: ReactNode;
}) {
  const [hist, setHist] = useState(false);
  return (
    <Card title={<span className="flex items-center gap-2">{title} <span className="chip bg-sunken text-muted font-mono">v{rules.active.version}</span></span>} sub={sub}
      actions={<button className="btn-ghost btn-sm" onClick={() => setHist((h) => !h)}><History size={14} /> History</button>}>
      {children}
      {hist && (
        <div className="mt-4 rounded-lg border border-line divide-y divide-line animate-fade">
          {rules.history.map((h: any) => (
            <div key={h.version} className="px-3 py-2 text-[12.5px] flex items-center gap-3">
              <span className={clsx("font-mono", h.active && "text-brand font-medium")}>v{h.version}</span>
              <span className="flex-1 truncate">{h.note}</span>
              <span className="text-muted">{h.created_by} · {dt(h.created_at)}</span>
            </div>
          ))}
        </div>
      )}
      {editable && (
        <div className="mt-4 pt-4 border-t border-line flex flex-wrap gap-2 items-center">
          <input className="input flex-1 min-w-[200px]" placeholder="Why are you changing this? (saved with the version)" value={note} onChange={(e) => setNote(e.target.value)} />
          {extra}
          <button className="btn-primary" disabled={busy || note.trim().length < 3} onClick={onSave}>{busy ? <Spinner /> : <Save size={15} />} Publish v{rules.active.version + 1}</button>
        </div>
      )}
    </Card>
  );
}

function Num({ label, value, onChange, step = 1, disabled, suffix }: { label: string; value: number; onChange: (v: number) => void; step?: number; disabled?: boolean; suffix?: string }) {
  return (
    <Field label={label}>
      <div className="relative">
        <input type="number" step={step} className="input num pr-10" value={value} disabled={disabled} onChange={(e) => onChange(Number(e.target.value))} />
        {suffix && <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[12px] text-faint">{suffix}</span>}
      </div>
    </Field>
  );
}

export default function Rules() {
  const { user } = useAuth();
  const editable = can.rules(user);
  const { data, error, loading, reload } = useApi<any>("/rules");
  const { busy, run } = useAction();
  const [draft, setDraft] = useState<any>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [test, setTest] = useState<any>(null);
  const [impact, setImpact] = useState<any>(null);
  useEffect(() => { if (data) setDraft(Object.fromEntries(["channel", "default", "contact_policy", "priority", "scoring"].map((k) => [k, structuredClone(data[k].active.definition)]))); }, [data]);

  if (error) return <ErrorBox message={error} retry={() => reload()} />;
  if (loading || !data || !draft) return <Skeleton className="h-96 rounded-xl" />;
  const set = (kind: string, path: string[], v: any) => setDraft((d: any) => {
    const n = structuredClone(d);
    let o = n[kind];
    path.slice(0, -1).forEach((p) => (o = o[p]));
    o[path[path.length - 1]] = v;
    return n;
  });
  const save = (kind: string) => run(kind, () => api(`/rules/${kind}`, { method: "PUT", json: { definition: draft[kind], note: notes[kind] || "" } }),
    (r: any) => `Published ${kind.replace("_", " ")} v${r.version}`).then((r: any) => { if (r) { setImpact({ kind, ...r }); setNotes((n) => ({ ...n, [kind]: "" })); reload(true); } });
  const common = (kind: string) => ({ kind, rules: data[kind], editable, busy: busy === kind, note: notes[kind] ?? "", setNote: (s: string) => setNotes((n) => ({ ...n, [kind]: s })), onSave: () => save(kind) });
  const ch = draft.channel;

  return (
    <>
      <PageHeader title="Rules" sub="Business rules are versioned. Publishing a change re-scores and re-routes open cases immediately, and every case remembers which version decided it."
        actions={!editable && <span className="chip bg-sunken text-muted py-1 px-2">Read-only for your role</span>} />
      {impact && (
        <div className="card p-4 mb-4 border-brand/30 bg-brand-soft/30 animate-rise text-[13.5px]">
          <b>{impact.kind.replace("_", " ")} v{impact.version} is live.</b>{" "}
          {impact.impact?.rerouted != null ? <>Re-routed {impact.impact.rerouted} case(s) (→ field {impact.impact.to?.FIELD ?? 0}, tele {impact.impact.to?.TELE ?? 0}, digital {impact.impact.to?.DIGITAL ?? 0}){impact.impact.auto_assigned ? `, auto-assigned ${impact.impact.auto_assigned}` : ""}; {impact.impact.new_defaults} newly classified as default.</> : "Applies to every contact attempt from now on."}
        </div>
      )}
      <div className="grid xl:grid-cols-2 gap-4">
        <Section {...common("channel")} title="Channel decision" sub="Who gets a field visit, a call, or a digital nudge">
          <div className="space-y-5">
            <div>
              <div className="flex justify-between text-[12.5px] mb-2"><span className="text-muted">Risk score bands</span><span className="num font-medium">Digital &lt; {ch.tele_score} ≤ Tele &lt; {ch.field_score} ≤ Field</span></div>
              <div className="relative h-3 rounded-full overflow-hidden flex">
                <div className="bg-digital/70" style={{ width: `${ch.tele_score}%` }} /><div className="bg-tele/70" style={{ width: `${ch.field_score - ch.tele_score}%` }} /><div className="bg-field/70 flex-1" />
              </div>
              <div className="grid grid-cols-2 gap-4 mt-3">
                <Field label={`Tele from score ${ch.tele_score}`}><input type="range" min={0} max={100} value={ch.tele_score} disabled={!editable} className="w-full accent-[rgb(var(--tele))]" onChange={(e) => set("channel", ["tele_score"], Math.min(Number(e.target.value), ch.field_score))} /></Field>
                <Field label={`Field from score ${ch.field_score}`}><input type="range" min={0} max={100} value={ch.field_score} disabled={!editable} className="w-full accent-[rgb(var(--field))]" onChange={(e) => set("channel", ["field_score"], Math.max(Number(e.target.value), ch.tele_score))} /></Field>
              </div>
            </div>
            <Num label="Always field visit when outstanding is at least" suffix="₹" step={10000} value={ch.field_outstanding} disabled={!editable} onChange={(v) => set("channel", ["field_outstanding"], v)} />
          </div>
        </Section>

        <Section {...common("default")} title="Default classification" sub="Safe expression, evaluated without eval(). Allowed fields are listed below."
          extra={<button className="btn-secondary" disabled={!!busy} onClick={() => run("test", () => api("/rules/default/test", { method: "POST", json: { expression: draft.default.expression } })).then((r) => r && setTest(r))}>
            {busy === "test" ? <Spinner /> : <FlaskConical size={15} />} Test</button>}>
          <input className="input font-mono" value={draft.default.expression} disabled={!editable} onChange={(e) => { set("default", ["expression"], e.target.value); setTest(null); }} />
          <div className="flex flex-wrap gap-1.5 mt-3">{Object.entries(data.fields).map(([k, v]) => <span key={k} className="kbd" title={v as string}>{k}</span>)}</div>
          {test && <div className="mt-3 text-[13px] animate-fade">Matches <b className="num">{test.matches}</b> of {test.of} open cases {test.sample.length > 0 && <span className="text-muted font-mono text-[12px]">· {test.sample.slice(0, 4).join(", ")}…</span>}</div>}
          <p className="text-[12px] text-muted mt-2">Operators: and, or, not, &gt; &gt;= &lt; &lt;= == !=, + − × ÷. Anything else (function calls, attributes, strings) is refused.</p>
        </Section>

        <Section {...common("contact_policy")} title="Contact policy" sub="RBI fair-practice: contact only in the allowed window, within frequency caps, never on opted-out channels">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Window opens"><input type="time" className="input" value={draft.contact_policy.window_start} disabled={!editable} onChange={(e) => set("contact_policy", ["window_start"], e.target.value)} /></Field>
            <Field label="Window closes"><input type="time" className="input" value={draft.contact_policy.window_end} disabled={!editable} onChange={(e) => set("contact_policy", ["window_end"], e.target.value)} /></Field>
          </div>
          <table className="table mt-4">
            <thead><tr><th>Channel</th><th>Per day</th><th>Per week</th></tr></thead>
            <tbody>{Object.entries(draft.contact_policy.caps).map(([k, v]: any) => (
              <tr key={k}><td className="uppercase text-[12px] font-medium">{k}</td>
                <td><input type="number" min={0} className="input h-8 w-20 num" value={v.day} disabled={!editable} onChange={(e) => set("contact_policy", ["caps", k, "day"], Number(e.target.value))} /></td>
                <td><input type="number" min={0} className="input h-8 w-20 num" value={v.week} disabled={!editable} onChange={(e) => set("contact_policy", ["caps", k, "week"], Number(e.target.value))} /></td></tr>
            ))}</tbody>
          </table>
          <label className="flex items-center gap-2 mt-3 text-[13px]"><input type="checkbox" className="accent-[rgb(var(--brand))]" checked={draft.contact_policy.pause_on_dispute} disabled={!editable} onChange={(e) => set("contact_policy", ["pause_on_dispute"], e.target.checked)} /> Pause all contact while a dispute is open</label>
        </Section>

        <Section {...common("priority")} title="Queue priority" sub="How the worklist is ordered. Weights must add up to 1.">
          <div className="grid grid-cols-3 gap-3">
            <Num label="Risk weight" step={0.05} value={draft.priority.w_risk} disabled={!editable} onChange={(v) => set("priority", ["w_risk"], v)} />
            <Num label="Amount weight" step={0.05} value={draft.priority.w_amount} disabled={!editable} onChange={(v) => set("priority", ["w_amount"], v)} />
            <Num label="DPD weight" step={0.05} value={draft.priority.w_dpd} disabled={!editable} onChange={(v) => set("priority", ["w_dpd"], v)} />
          </div>
          <div className="text-[12.5px] mt-2 num">Sum: <b className={clsx(Math.abs(draft.priority.w_risk + draft.priority.w_amount + draft.priority.w_dpd - 1) > 0.01 ? "text-bad" : "text-ok")}>{(draft.priority.w_risk + draft.priority.w_amount + draft.priority.w_dpd).toFixed(2)}</b></div>
        </Section>

        <Section {...common("scoring")} title="Risk scorecard" sub="Points per factor. The score is capped to 0–100 and every point is shown to users as a reason.">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {draft.scoring.dpd_points.map((b: any, i: number) => (
              <Num key={i} label={`DPD ${b.min}${b.max ? `–${b.max}` : "+"}`} value={b.points} disabled={!editable} onChange={(v) => set("scoring", ["dpd_points", String(i), "points"], v)} />
            ))}
            <Num label="Per missed EMI" value={draft.scoring.missed_emi_points} disabled={!editable} onChange={(v) => set("scoring", ["missed_emi_points"], v)} />
            <Num label="Per broken promise" value={draft.scoring.broken_ptp_points} disabled={!editable} onChange={(v) => set("scoring", ["broken_ptp_points"], v)} />
            <Num label="Unreachable streak" value={draft.scoring.unreachable_points} disabled={!editable} onChange={(v) => set("scoring", ["unreachable_points"], v)} />
            <Num label="Unwilling to pay" value={draft.scoring.willful_points} disabled={!editable} onChange={(v) => set("scoring", ["willful_points"], v)} />
            <Num label="Recent part-payment" value={draft.scoring.recent_payment_points} disabled={!editable} onChange={(v) => set("scoring", ["recent_payment_points"], v)} />
            <Num label="Kept last promise" value={draft.scoring.kept_ptp_points} disabled={!editable} onChange={(v) => set("scoring", ["kept_ptp_points"], v)} />
          </div>
        </Section>

        <Card title="Cost model" sub="Used for cost per recovery on the dashboard (₹ per action)">
          <CostEditor costs={data.costs} editable={user?.role === "admin" || user?.role === "exec"} onSaved={() => reload(true)} />
        </Card>
      </div>
    </>
  );
}

function CostEditor({ costs, editable, onSaved }: { costs: any; editable: boolean; onSaved: () => void }) {
  const [c, setC] = useState(costs);
  const { busy, run } = useAction();
  return (
    <>
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {Object.keys(c).map((k) => <Num key={k} label={k === "visit" ? "Field visit" : k.toUpperCase()} step={0.05} suffix="₹" value={c[k]} disabled={!editable} onChange={(v) => setC({ ...c, [k]: v })} />)}
      </div>
      {editable && <button className="btn-secondary mt-4" disabled={!!busy} onClick={() => run("c", () => api("/settings/costs", { method: "PUT", json: c }), "Cost model saved").then(onSaved)}>{busy ? <Spinner /> : "Save costs"}</button>}
    </>
  );
}
