import clsx from "clsx";
import {
  ArrowLeft, Ban, Building2, Eye, FileText, Link2, Lock, Mail, MessageCircle, MessageSquareText, MicVocal, Phone, RefreshCw, Route,
  ShieldAlert, Sparkles, UserRoundCog,
} from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BucketPill, ChannelPill, RiskBar, SentimentPill, StatusPill, VerificationPill } from "../components/badges";
import { CaseMap } from "../components/MiniMap";
import { PayLinkCard } from "../components/PayLink";
import { Card, Empty, ErrorBox, Field, Modal, Segmented, Skeleton, Spinner, Tabs, useAction } from "../components/ui";
import { api, openFile, session } from "../lib/api";
import { useAuth } from "../lib/auth";
import { dateOnly, dt, inr, LANG, LOAN, pct, titleCase } from "../lib/format";
import { useApi, useLive } from "../lib/hooks";

const EVENT_DOT: Record<string, string> = {
  payment: "bg-ok", status: "bg-ink", visit: "bg-field", call: "bg-tele", nudge: "bg-digital", ptp: "bg-info", note: "bg-tele",
  policy_block: "bg-warn", dispute: "bg-warn", assignment: "bg-faint", routing: "bg-brand", intake: "bg-faint", pii: "bg-bad",
  payment_link: "bg-ok", payment_failed: "bg-bad", score: "bg-faint", default: "bg-bad",
};

function AudioNote({ path }: { path: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  if (src) return <audio className="mt-2 w-full h-9" controls autoPlay src={src} />;
  return (
    <button className="btn-secondary btn-sm mt-2" disabled={loading} onClick={async () => {
      setLoading(true);
      try {
        const s = session.get();
        const r = await fetch(`/api/v1${path}`, { headers: s ? { Authorization: `Bearer ${s.access_token}` } : {} });
        if (r.ok) setSrc(URL.createObjectURL(await r.blob()));
      } finally { setLoading(false); }
    }}>{loading ? <Spinner size={13} /> : <MicVocal size={13} />} Play recording</button>
  );
}

function Reasons({ c }: { c: any }) {
  const max = Math.max(35, ...c.reasons.map((r: any) => Math.abs(r.points)));
  return (
    <div className="space-y-2.5">
      {c.reasons.length === 0 && <div className="text-[13px] text-muted">No risk factors: score is 0.</div>}
      {c.reasons.map((r: any) => (
        <div key={r.code} className="grid grid-cols-[1fr_auto] gap-x-3 items-center">
          <div className="text-[13px]">{r.label}</div>
          <div className={clsx("num text-[12.5px] font-semibold", r.points > 0 ? "text-bad" : "text-ok")}>{r.points > 0 ? "+" : ""}{r.points}</div>
          <div className="col-span-2 h-1 rounded-full bg-sunken mt-1 overflow-hidden">
            <div className={clsx("h-full rounded-full", r.points > 0 ? "bg-bad/70" : "bg-ok/70")} style={{ width: `${(Math.abs(r.points) / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function CaseDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const { data: c, error, loading, reload } = useApi<any>(`/cases/${id}`);
  const [tab, setTab] = useState<"timeline" | "visits" | "money" | "notes" | "contacts">("timeline");
  const { busy, run } = useAction();
  const [link, setLink] = useState<any>(null);
  const [linkAmount, setLinkAmount] = useState<string>("");
  const [nudgeCh, setNudgeCh] = useState<"sms" | "whatsapp" | "email">("sms");
  const [template, setTemplate] = useState("reminder");
  const [lastMsg, setLastMsg] = useState<string | null>(null);
  const [revealOpen, setRevealOpen] = useState(false);
  const [revealReason, setRevealReason] = useState("");
  const [pii, setPii] = useState<any>(null);
  const [reassignOpen, setReassignOpen] = useState(false);
  const [agentId, setAgentId] = useState("");
  const [why, setWhy] = useState("");
  const [chOpen, setChOpen] = useState(false);
  const [ch, setCh] = useState<"FIELD" | "TELE" | "DIGITAL" | "AUTO">("FIELD");

  useLive((e) => { if (e.case_id === id) reload(true); });

  if (error) return <ErrorBox message={error} retry={() => reload()} />;
  if (loading || !c) return <div className="space-y-4"><Skeleton className="h-24 rounded-xl" /><Skeleton className="h-96 rounded-xl" /></div>;

  const cured = ["PAID", "CLOSED"].includes(c.status);
  const policy = c.contact_policy;
  const nudge = () => run("nudge", () => api(`/cases/${id}/nudge`, { method: "POST", json: { channel: nudgeCh, template } }),
    (r: any) => (r.sent ? `${nudgeCh.toUpperCase()} delivered to the outbox` : null)).then((r: any) => {
    if (r && !r.sent) setLastMsg("BLOCKED: " + r.reason);
    else if (r) { setLastMsg(r.text); if (r.link) setLink(r.link); }
    reload(true);
  });

  return (
    <>
      <Link to="/app/cases" className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink mb-3"><ArrowLeft size={14} /> Case queue</Link>

      <div className="card p-5 mb-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-mono text-[19px] font-semibold tracking-tight">{c.account_no}</h1>
              <StatusPill status={c.status} />
              <ChannelPill channel={c.channel} override={c.channel_override} />
              <BucketPill bucket={c.dpd_bucket} dpd={c.dpd} />
              {c.is_default && <span className="chip bg-bad/10 text-bad">Default · rule v{c.default_rule_version}</span>}
            </div>
            <div className="mt-2 text-[14px] flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="font-medium">{pii?.name ?? c.borrower_name}</span>
              <span className="text-muted flex items-center gap-1"><Phone size={13} /> {pii?.phone ?? c.phone}</span>
              <span className="text-muted">{pii?.address ?? c.address}</span>
              <span className="text-muted">· prefers {LANG[c.language]}</span>
              {c.pii_masked && !pii && (
                <button className="chip bg-sunken text-muted hover:text-ink" onClick={() => setRevealOpen(true)}><Lock size={11} /> Masked · reveal</button>
              )}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <button className="btn-secondary btn-sm" onClick={() => run("rescore", () => api(`/cases/${id}/rescore`, { method: "POST" }), "Re-scored with current rules").then(() => reload(true))} disabled={!!busy}>
              {busy === "rescore" ? <Spinner size={14} /> : <RefreshCw size={14} />} Re-score
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mt-5 pt-4 border-t border-line">
          {[
            ["Overdue", inr(c.amount_due)], ["Outstanding", inr(c.outstanding)], ["EMI", inr(c.emi_amount)],
            ["Loan", LOAN[c.loan_type]], ["Collected", inr(c.collected_total)], ["Agent", c.agent_name ?? "Unassigned"],
          ].map(([k, v]) => (
            <div key={k}><div className="label">{k}</div><div className="mt-1 text-[14.5px] font-medium num truncate">{v}</div></div>
          ))}
        </div>
        {c.escalated_to && <div className="mt-4 text-[13px] rounded-lg bg-bad/[0.06] border border-bad/20 text-bad px-3 py-2 flex items-center gap-2"><ShieldAlert size={15} /> Escalated to {c.escalated_to} after {c.broken_ptp_count} broken promises</div>}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-4">
        <div className="space-y-4 min-w-0">
          <div className="grid md:grid-cols-2 gap-4">
            <Card title="Why this priority" sub={`Rule scorecard v${c.scoring_rule_version} · every point is a reason`}
              actions={<div className="text-right"><div className="text-[24px] font-semibold num leading-none">{c.risk_score}</div><div className="text-[11px] text-muted">risk / 100</div></div>}>
              <RiskBar score={c.risk_score} showValue={false} />
              <div className="mt-4"><Reasons c={c} /></div>
              <div className="mt-4 pt-3 border-t border-line text-[12px] text-muted">Queue priority <span className="num font-medium text-ink">{c.priority.toFixed(1)}</span> = 0.6 × risk + 0.3 × amount at stake + 0.1 × DPD</div>
            </Card>
            <Card title={<span className="flex items-center gap-1.5"><Sparkles size={14} className="text-brand" /> Self-cure model</span>}
              sub={`Model v${c.model_version ?? "—"} · exact per-feature attributions`}
              actions={<div className="text-right"><div className="text-[24px] font-semibold num leading-none text-digital">{pct(c.p_selfcure, 0)}</div><div className="text-[11px] text-muted">pays within 30 d</div></div>}>
              <ul className="space-y-2.5">
                {c.ml_reasons.map((r: any) => (
                  <li key={r.feature} className="flex items-center justify-between gap-3 text-[13px]">
                    <span>{r.label}</span>
                    <span className={clsx("chip", r.impact > 0 ? "bg-ok/10 text-ok" : "bg-bad/10 text-bad")}>{r.direction} chance · {r.impact > 0 ? "+" : ""}{r.impact.toFixed(2)}</span>
                  </li>
                ))}
                {!c.ml_reasons.length && <li className="text-[13px] text-muted">No strong drivers.</li>}
              </ul>
              <p className="mt-4 pt-3 border-t border-line text-[12px] text-muted leading-5">
                Logistic model trained on synthetic + recorded outcomes. Rule scorecard stays the source of the score; the model adds a second, explainable opinion.
              </p>
            </Card>
          </div>

          <Card pad={false}>
            <div className="px-3"><Tabs value={tab} onChange={setTab} items={[
              { id: "timeline", label: "Timeline", count: c.timeline.length }, { id: "visits", label: "Visits", count: c.visits.length },
              { id: "money", label: "Payments", count: c.payments.length + c.links.length }, { id: "notes", label: "Notes", count: c.notes.length },
              { id: "contacts", label: "Contacts", count: c.contacts.length },
            ]} /></div>
            <div className="p-5">
              {tab === "timeline" && (
                <ol className="relative">
                  {c.timeline.map((e: any, i: number) => (
                    <li key={e.id} className="relative pl-6 pb-4 last:pb-0 animate-fade">
                      {i < c.timeline.length - 1 && <span className="absolute left-[5px] top-3 bottom-0 w-px bg-line" />}
                      <span className={clsx("absolute left-0 top-1.5 h-[11px] w-[11px] rounded-full ring-[3px] ring-surface", EVENT_DOT[e.type] ?? "bg-faint")} />
                      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                        <span className="text-[13.5px] font-medium">{e.title}</span>
                        <span className="text-[12px] text-faint num">{dt(e.ts)}</span>
                      </div>
                      <div className="text-[12.5px] text-muted mt-0.5">
                        {e.actor}
                        {e.data?.reason && <> · {e.data.reason}</>}
                        {e.data?.why && <> · {e.data.why}</>}
                        {e.data?.text && <span className="block mt-1 text-ink/80 italic">“{e.data.text}”</span>}
                        {e.data?.synced_offline && <span className="chip bg-info/10 text-info ml-1">synced from offline</span>}
                      </div>
                    </li>
                  ))}
                </ol>
              )}
              {tab === "visits" && (
                <div className="space-y-4">
                  <CaseMap home={[c.lat, c.lng]} visits={c.visits} />
                  {c.visits.length === 0 ? <Empty title="No field visits yet" /> : (
                    <table className="table -mx-5 w-[calc(100%+40px)]">
                      <thead><tr><th>When</th><th>Agent</th><th>Outcome</th><th>Verification</th><th className="text-right">Distance</th><th className="text-right">Accuracy</th></tr></thead>
                      <tbody>{c.visits.map((v: any) => (
                        <tr key={v.id}>
                          <td className="whitespace-nowrap">{dt(v.device_ts)}{v.location_source === "demo" && <span className="chip bg-sunken text-muted ml-1">demo GPS</span>}</td>
                          <td>{v.agent}</td><td>{titleCase(v.outcome)}</td><td><VerificationPill v={v.verification} /></td>
                          <td className="text-right num">{v.distance_m < 1000 ? `${Math.round(v.distance_m)} m` : `${(v.distance_m / 1000).toFixed(2)} km`}</td>
                          <td className="text-right num text-muted">±{Math.round(v.accuracy_m)} m</td>
                        </tr>))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
              {tab === "money" && (
                <div className="space-y-5">
                  <div>
                    <div className="label mb-2">Confirmed payments</div>
                    {c.payments.length === 0 ? <div className="text-[13px] text-muted">No confirmed payments.</div> : c.payments.map((p: any) => (
                      <div key={p.id} className="flex items-center justify-between gap-3 py-2.5 border-b border-line last:border-0">
                        <div>
                          <div className="text-[13.5px] font-medium num">{inr(p.amount, 2)} <span className="text-muted font-normal">· {String(p.method).toUpperCase()}</span></div>
                          <div className="text-[12px] text-muted font-mono">{p.gateway_payment_id} · {p.receipt_no}</div>
                        </div>
                        <div className="text-right">
                          <span className={clsx("chip", p.source === "webhook" ? "bg-ok/10 text-ok" : "bg-info/10 text-info")}>{p.source === "webhook" ? "signed webhook" : "reconciliation"}</span>
                          <button className="block ml-auto mt-1 text-[12px] text-brand hover:underline" onClick={() => openFile(`/payments/${p.id}/receipt.pdf`)}>Receipt PDF</button>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div>
                    <div className="label mb-2">Payment links</div>
                    {c.links.length === 0 ? <div className="text-[13px] text-muted">No links created.</div> : c.links.map((l: any) => (
                      <div key={l.id} className="flex items-center justify-between py-2 border-b border-line last:border-0 text-[13px]">
                        <span className="num">{inr(l.amount)} <span className="text-muted">· paid {inr(l.amount_paid)}</span></span>
                        <span className="flex items-center gap-2"><span className="chip bg-sunken text-muted">{l.status}</span>
                          <a className="text-brand hover:underline" href={`/p/${l.token}`} target="_blank" rel="noreferrer">open</a></span>
                      </div>
                    ))}
                  </div>
                  <div>
                    <div className="label mb-2">Promises</div>
                    {c.promises.length === 0 ? <div className="text-[13px] text-muted">No promises recorded.</div> : c.promises.map((p: any) => (
                      <div key={p.id} className="flex items-center justify-between py-2 border-b border-line last:border-0 text-[13px]">
                        <span className="num">{inr(p.amount)} by {dateOnly(p.promised_date)} <span className="text-muted">· {p.channel}</span></span>
                        <span className={clsx("chip", { open: "bg-info/10 text-info", kept: "bg-ok/10 text-ok", broken: "bg-bad/10 text-bad" }[p.status as "open"] ?? "bg-sunken text-muted")}>{p.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {tab === "notes" && (c.notes.length === 0 ? <Empty icon={<MicVocal size={18} />} title="No borrower notes yet" body="Agents capture typed or voice notes from the field app." /> : (
                <div className="space-y-3">
                  {c.notes.map((n: any) => (
                    <div key={n.id} className="rounded-lg border border-line p-3.5">
                      <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
                        <span className="chip bg-sunken">{n.source === "voice" ? "🎙 voice" : "typed"} · {LANG[n.language] ?? n.language}</span>
                        <SentimentPill s={n.sentiment} /><span className="chip bg-sunken">{n.reason_label}</span>
                        <span className="ml-auto">{dt(n.captured_at)}</span>
                      </div>
                      <p className="mt-2 text-[14px] leading-6">{n.original_text}</p>
                      {n.english_text && n.language !== "en" && <p className="mt-1 text-[13px] text-muted leading-5">EN: {n.english_text}</p>}
                      {n.has_audio && <AudioNote path={`/cases/${id}/notes/${n.id}/audio`} />}
                      <div className="mt-1.5 text-[11px] text-faint">analysed by {n.analyzer}</div>
                    </div>
                  ))}
                </div>
              ))}
              {tab === "contacts" && (c.contacts.length === 0 ? <Empty title="No contact attempts" /> : (
                <table className="table -mx-5 w-[calc(100%+40px)]">
                  <thead><tr><th>When</th><th>Channel</th><th>Status</th><th>Detail</th></tr></thead>
                  <tbody>{c.contacts.map((x: any) => (
                    <tr key={x.id}>
                      <td className="whitespace-nowrap">{dt(x.ts)}</td><td className="uppercase text-[12px] font-medium">{x.channel}</td>
                      <td><span className={clsx("chip", x.status === "blocked" ? "bg-warn/10 text-warn" : "bg-ok/10 text-ok")}>{x.status}</span></td>
                      <td className="text-muted text-[12.5px] max-w-[420px]">{x.block_reason ?? x.body ?? "—"}</td>
                    </tr>))}
                  </tbody>
                </table>
              ))}
            </div>
          </Card>
        </div>

        {/* ------------------------------------------------ actions */}
        <div className="space-y-4">
          <Card title="Digital nudge" sub="Every message passes the Contact Policy Engine first">
            <div className="grid grid-cols-3 gap-1.5">
              {(["sms", "whatsapp", "email"] as const).map((k) => {
                const I = { sms: MessageSquareText, whatsapp: MessageCircle, email: Mail }[k];
                const ok = policy[k]?.allowed;
                return (
                  <button key={k} onClick={() => setNudgeCh(k)}
                    className={clsx("rounded-lg border px-2 py-2 text-left transition", nudgeCh === k ? "border-brand bg-brand-soft/50" : "border-line hover:bg-sunken")}>
                    <I size={15} className={nudgeCh === k ? "text-brand" : "text-muted"} />
                    <div className="text-[12.5px] font-medium mt-1">{{ sms: "SMS", whatsapp: "WhatsApp", email: "Email" }[k]}</div>
                    <div className={clsx("text-[11px]", ok ? "text-ok" : "text-warn")}>{ok ? "allowed now" : "blocked"}</div>
                  </button>
                );
              })}
            </div>
            {!policy[nudgeCh]?.allowed && <div className="mt-2 text-[12px] text-warn flex gap-1.5"><Ban size={13} className="mt-0.5 shrink-0" />{policy[nudgeCh]?.reason}</div>}
            <select className="select mt-3" value={template} onChange={(e) => setTemplate(e.target.value)}>
              <option value="reminder">Overdue reminder</option><option value="ptp_reminder">Promise reminder</option><option value="settlement_offer">Bring account to regular</option>
            </select>
            <button className="btn-primary w-full mt-3" disabled={!!busy || cured} onClick={nudge}>
              {busy === "nudge" ? <Spinner /> : <>Send {nudgeCh === "whatsapp" ? "WhatsApp" : nudgeCh.toUpperCase()} in {LANG[c.language]}</>}
            </button>
            <p className="text-[11.5px] text-muted mt-2">Attempts outside the window are still logged, with the reason. Try it after moving the demo clock to 8:30 PM.</p>
            {lastMsg && <div className={clsx("mt-3 rounded-lg p-3 text-[12.5px] leading-5 animate-rise", lastMsg.startsWith("BLOCKED") ? "bg-warn/10 text-warn" : "bg-sunken")}>{lastMsg}</div>}
          </Card>

          <Card title="Collect payment" sub="Case turns PAID only when the gateway confirms">
            {link && !cured ? <PayLinkCard link={link} /> : (
              <div className="flex gap-2">
                <input className="input" type="number" min={1} placeholder={`${Math.round(c.amount_due || c.emi_amount)}`} value={linkAmount} onChange={(e) => setLinkAmount(e.target.value)} />
                <button className="btn-primary shrink-0" disabled={!!busy || cured}
                  onClick={() => run("link", () => api(`/cases/${id}/payment-link`, { method: "POST", json: { amount: linkAmount ? Number(linkAmount) : null } }), "Payment link created").then((r) => { if (r) { setLink(r); reload(true); } })}>
                  {busy === "link" ? <Spinner /> : <><Link2 size={15} /> Create link</>}
                </button>
              </div>
            )}
            {cured && <p className="text-[12.5px] text-ok mt-2">This account is cured. No further collection.</p>}
          </Card>

          <Card title="Work allocation">
            <div className="space-y-2">
              <button className="btn-secondary w-full justify-start" disabled={cured} onClick={() => { setAgentId(c.candidate_agents?.[0]?.id ?? ""); setWhy(""); setReassignOpen(true); }}><UserRoundCog size={15} /> Reassign agent</button>
              <button className="btn-secondary w-full justify-start" disabled={cured} onClick={() => { setCh(c.channel ?? "FIELD"); setWhy(""); setChOpen(true); }}><Route size={15} /> Override channel</button>
              {c.pii_masked && <button className="btn-secondary w-full justify-start" onClick={() => setRevealOpen(true)}><Eye size={15} /> Reveal contact details</button>}
              <a className="btn-secondary w-full justify-start" href={`/app/audit?q=${c.account_no}`}><FileText size={15} /> Audit entries for this case</a>
            </div>
            <div className="mt-4 pt-3 border-t border-line text-[12px] text-muted space-y-1">
              <div>Channel rule v{c.channel_rule_version ?? "—"} · scoring v{c.scoring_rule_version} · model v{c.model_version}</div>
              <div>Case version {c.version} · last update {dt(c.updated_at)}</div>
            </div>
          </Card>
        </div>
      </div>

      <Modal open={revealOpen} onClose={() => setRevealOpen(false)} title="Reveal borrower contact details"
        sub="PII is masked by default. Your reason is written to the tamper-evident audit trail."
        footer={<><button className="btn-ghost" onClick={() => setRevealOpen(false)}>Cancel</button>
          <button className="btn-primary" disabled={revealReason.trim().length < 8 || !!busy}
            onClick={() => run("reveal", () => api(`/cases/${id}/reveal-pii`, { method: "POST", json: { reason: revealReason } }), "Revealed and logged").then((r) => { if (r) { setPii(r); setRevealOpen(false); setRevealReason(""); reload(true); } })}>
            {busy === "reveal" ? <Spinner /> : "Reveal"}</button></>}>
        <Field label="Reason (min 8 characters)" hint={`Logged as ${user?.name} · ${user?.role_label}`}>
          <textarea className="input" rows={3} value={revealReason} onChange={(e) => setRevealReason(e.target.value)} placeholder="e.g. Borrower called the branch to update their address" />
        </Field>
      </Modal>

      <Modal open={reassignOpen} onClose={() => setReassignOpen(false)} title="Reassign case" sub="Agents ranked by fit: 0.45 proximity + 0.30 bucket recovery + 0.25 spare capacity" width={560}
        footer={<><button className="btn-ghost" onClick={() => setReassignOpen(false)}>Cancel</button>
          <button className="btn-primary" disabled={!agentId || why.trim().length < 4 || !!busy}
            onClick={() => run("reassign", () => api(`/cases/${id}/reassign`, { method: "POST", json: { agent_id: agentId, reason: why } }), "Case reassigned").then((r) => { if (r) { setReassignOpen(false); reload(true); } })}>
            {busy === "reassign" ? <Spinner /> : "Reassign"}</button></>}>
        <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
          {(c.candidate_agents ?? []).map((a: any) => (
            <label key={a.id} className={clsx("flex items-center gap-3 rounded-lg border px-3 py-2.5 cursor-pointer transition", agentId === a.id ? "border-brand bg-brand-soft/40" : "border-line hover:bg-sunken")}>
              <input type="radio" name="agent" checked={agentId === a.id} onChange={() => setAgentId(a.id)} className="accent-[rgb(var(--brand))]" />
              <div className="flex-1 min-w-0">
                <div className="text-[13.5px] font-medium">{a.name} {a.id === c.agent_id && <span className="chip bg-sunken text-muted ml-1">current</span>}</div>
                <div className="text-[12px] text-muted">{a.detail.distance_km} km away · {pct(a.detail.bucket_performance, 0)} recovery in {c.dpd_bucket} · load {a.load}/{a.capacity}</div>
              </div>
              <div className="text-right"><div className="num font-semibold">{a.fit.toFixed(2)}</div><div className="text-[11px] text-muted">fit</div></div>
            </label>
          ))}
        </div>
        <div className="mt-4"><Field label="Reason"><input className="input" value={why} onChange={(e) => setWhy(e.target.value)} placeholder="e.g. Borrower speaks Marathi; agent lives nearby" /></Field></div>
      </Modal>

      <Modal open={chOpen} onClose={() => setChOpen(false)} title="Override channel" sub="Manual overrides are kept until you switch back to Auto, and are audited."
        footer={<><button className="btn-ghost" onClick={() => setChOpen(false)}>Cancel</button>
          <button className="btn-primary" disabled={why.trim().length < 4 || !!busy}
            onClick={() => run("ch", () => api(`/cases/${id}/channel`, { method: "POST", json: { channel: ch, reason: why } }), "Channel updated").then((r) => { if (r) { setChOpen(false); reload(true); } })}>
            {busy === "ch" ? <Spinner /> : "Apply"}</button></>}>
        <Segmented value={ch} onChange={setCh} items={[{ id: "FIELD", label: <span className="flex items-center gap-1"><Building2 size={13} />Field</span> }, { id: "TELE", label: "Tele" }, { id: "DIGITAL", label: "Digital" }, { id: "AUTO", label: "Auto (rules)" }]} />
        <div className="mt-4"><Field label="Reason"><input className="input" value={why} onChange={(e) => setWhy(e.target.value)} placeholder="e.g. Senior citizen, prefers a home visit" /></Field></div>
      </Modal>
    </>
  );
}
