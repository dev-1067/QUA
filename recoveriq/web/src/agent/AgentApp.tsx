import clsx from "clsx";
import {
  AlertTriangle, ArrowLeft, CalendarCheck, ChevronRight, CloudOff, FileWarning, IndianRupee, LogOut, MapPin, MapPinned,
  MessageSquarePlus, MoreVertical, Navigation, Phone, RefreshCw, Search, Wifi, WifiOff,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { BucketPill, Logo, StatusPill } from "../components/badges";
import { PayLinkCard } from "../components/PayLink";
import { Field, Modal, Spinner, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ago, dateOnly, inr, LANG, LOAN, uuid } from "../lib/format";
import { useLive, useNow } from "../lib/hooks";
import { clearAgentData, enqueue, flush, patchLocal, simOffline, useOnline, useStore, type Op } from "./store";
import { VoiceCapture } from "./Voice";

const OUTCOMES: [string, string][] = [
  ["met_borrower", "Met borrower"], ["promise_taken", "Promise taken"], ["payment_link_shared", "Payment link shared"],
  ["not_home", "Not at home"], ["door_locked", "House locked"], ["shifted", "Shifted"], ["refused", "Refused"], ["wrong_address", "Wrong address"],
];
const CALL: [string, string][] = [["connected", "Connected"], ["no_answer", "No answer"], ["switched_off", "Switched off"], ["callback_requested", "Callback requested"], ["wrong_number", "Wrong number"]];
const DISPUTES: [string, string][] = [["already_paid", "Already paid"], ["wrong_amount", "Wrong amount"], ["fraud_claim", "Fraud / not my loan"], ["service_issue", "Service issue"], ["harassment_complaint", "Harassment complaint"]];

function useSync() {
  const online = useOnline();
  const toast = useToast();
  const [syncing, setSyncing] = useState(false);
  const run = async (manual = false) => {
    if (!online) { if (manual) toast({ kind: "warn", title: "You're offline", body: "Actions are saved on this phone and will sync when you reconnect." }); return; }
    setSyncing(true);
    const r = await flush();
    setSyncing(false);
    if (r.error && manual) toast({ kind: "err", title: "Sync failed", body: r.error });
    else if (r.applied + r.duplicates > 0) toast({ kind: "ok", title: `Synced ${r.applied + r.duplicates} action(s)`, body: r.duplicates ? `${r.duplicates} were already on the server and were not repeated` : undefined });
    else if (manual) toast({ kind: "info", title: "Worklist is up to date" });
    if (r.rejected) toast({ kind: "warn", title: `${r.rejected} action(s) were rejected`, body: "Open the outbox to see why." });
  };
  useEffect(() => { if (online) run(); }, [online]); // eslint-disable-line
  useEffect(() => { const t = setInterval(() => online && flush(), 20000); return () => clearInterval(t); }, [online]);
  useLive((e) => { if (online && ["case.assigned", "case.unassigned", "case.updated", "payment.confirmed", "case.rerouted", "ptp.broken"].includes(e.type)) flush(); });
  return { online, syncing, run };
}

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#e9e7e1] dark:bg-[#070b0a] sm:py-6">
      <div className="mx-auto max-w-[440px] min-h-screen sm:min-h-[calc(100vh-48px)] bg-canvas sm:rounded-[28px] sm:shadow-pop sm:ring-1 sm:ring-black/5 overflow-hidden relative flex flex-col">
        {children}
      </div>
    </div>
  );
}

function TopBar({ title, back, right }: { title: ReactNode; back?: () => void; right?: ReactNode }) {
  return (
    <header className="sidebar-surface text-side-text px-4 pt-[max(env(safe-area-inset-top),12px)] pb-3 sticky top-0 z-20">
      <div className="flex items-center gap-2 h-10">
        {back ? <button onClick={back} className="h-9 w-9 -ml-1.5 rounded-full flex items-center justify-center hover:bg-white/10" aria-label="Back"><ArrowLeft size={19} /></button> : null}
        <div className="flex-1 min-w-0">{title}</div>
        {right}
      </div>
    </header>
  );
}

function NetPill({ online, pending, syncing, onSync }: { online: boolean; pending: number; syncing: boolean; onSync: () => void }) {
  return (
    <button onClick={onSync} className={clsx("h-8 px-2.5 rounded-full text-[12px] font-medium flex items-center gap-1.5 transition",
      online ? "bg-white/10 text-white" : "bg-[#f59e0b] text-[#2a1a00]")}>
      {syncing ? <Spinner size={13} /> : online ? <Wifi size={13} /> : <WifiOff size={13} />}
      {online ? (pending ? `${pending} to sync` : "Synced") : `Offline${pending ? ` · ${pending} saved` : ""}`}
    </button>
  );
}

/* ------------------------------------------------------------------ worklist */
function Worklist() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const { items, outbox, stats, lastSync, ready } = useStore();
  const { online, syncing, run } = useSync();
  const [q, setQ] = useState("");
  const [f, setF] = useState<"all" | "ptp" | "FIELD" | "TELE">("all");
  const [menu, setMenu] = useState(false);
  const [sim, setSim] = useState(simOffline.get());
  const now = useNow(30000);
  const pendingFor = useMemo(() => outbox.reduce((m: Record<string, number>, o) => ({ ...m, [o.case_id]: (m[o.case_id] || 0) + 1 }), {}), [outbox]);
  const today = new Date().toISOString().slice(0, 10);
  const shown = items.filter((c) => {
    if (q && !`${c.account_no} ${c.borrower_name} ${c.address}`.toLowerCase().includes(q.toLowerCase())) return false;
    if (f === "ptp") return c.ptp && c.ptp.date <= today;
    if (f === "FIELD" || f === "TELE") return c.channel === f;
    return true;
  });
  const pending = outbox.filter((o) => o.status === "pending").length;
  const rejected = outbox.filter((o) => o.status === "rejected");

  return (
    <>
      <TopBar title={<Logo dark size={24} />} right={<>
        <NetPill online={online} pending={pending} syncing={syncing} onSync={() => run(true)} />
        <button onClick={() => setMenu((m) => !m)} className="h-9 w-9 rounded-full flex items-center justify-center hover:bg-white/10" aria-label="Menu"><MoreVertical size={18} /></button>
      </>} />
      {menu && (
        <div className="absolute right-3 top-[60px] z-30 card shadow-pop p-1.5 w-64 animate-rise">
          <div className="px-3 py-2 border-b border-line mb-1"><div className="text-[13px] font-medium">{user?.name}</div><div className="text-[12px] text-muted">{user?.branch} · field agent</div></div>
          <label className="flex items-center justify-between gap-2 px-3 h-10 rounded-md hover:bg-sunken text-[13px] cursor-pointer">
            <span className="flex items-center gap-2"><CloudOff size={15} /> Simulate no network</span>
            <input type="checkbox" className="accent-[rgb(var(--brand))]" checked={sim} onChange={(e) => { simOffline.set(e.target.checked); setSim(e.target.checked); }} />
          </label>
          <button className="w-full flex items-center gap-2 px-3 h-10 rounded-md hover:bg-sunken text-[13px] text-bad"
            onClick={async () => { if (pending && !confirm(`${pending} action(s) have not synced and will be lost. Sign out anyway?`)) return; await clearAgentData(); logout(); nav("/login"); }}>
            <LogOut size={15} /> Sign out</button>
        </div>
      )}
      {!online && (
        <div className="bg-[#fef3c7] text-[#78350f] dark:bg-[#3a2a07] dark:text-[#fcd34d] px-4 py-2.5 text-[12.5px] flex items-start gap-2 animate-fade">
          <WifiOff size={15} className="mt-0.5 shrink-0" />
          <span>No network. You can keep checking in, taking notes and promises. Everything syncs automatically when you're back online. Payments need a connection.</span>
        </div>
      )}
      <div className="flex-1 overflow-y-auto pb-8" onClick={() => menu && setMenu(false)}>
        <div className="px-4 pt-4">
          <div className="text-[13px] text-muted">{new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}</div>
          <h1 className="text-[21px] font-semibold tracking-tight">Today's worklist</h1>
          <div className="grid grid-cols-4 gap-2 mt-3">
            {[["Open", stats?.open ?? items.length], ["Visits", stats?.visits_today ?? 0], ["Verified", stats?.verified_today ?? 0], ["Collected", stats ? `₹${Math.round(stats.collected_today / 1000)}k` : "—"]].map(([k, v]) => (
              <div key={k as string} className="card px-2.5 py-2"><div className="text-[10.5px] text-muted uppercase tracking-wide font-semibold">{k}</div><div className="text-[17px] font-semibold num mt-0.5">{v}</div></div>
            ))}
          </div>
          <div className="relative mt-3">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
            <input className="input pl-9 h-10" placeholder="Search name, account or area" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div className="flex gap-1.5 mt-2.5 overflow-x-auto pb-1">
            {([["all", "All"], ["ptp", "Promises due"], ["FIELD", "Visits"], ["TELE", "Calls"]] as const).map(([id, l]) => (
              <button key={id} onClick={() => setF(id)} className={clsx("h-8 px-3 rounded-full text-[12.5px] font-medium border whitespace-nowrap transition",
                f === id ? "bg-ink text-canvas border-ink" : "bg-surface border-line text-muted")}>{l}</button>
            ))}
          </div>
          {rejected.length > 0 && (
            <div className="mt-3 rounded-xl border border-bad/30 bg-bad/[0.05] p-3 text-[12.5px]">
              <div className="font-medium text-bad flex items-center gap-1.5"><FileWarning size={14} /> {rejected.length} action(s) rejected by the server</div>
              {rejected.slice(0, 3).map((o) => <div key={o.client_id} className="text-muted mt-1">{o.label}: {o.error}</div>)}
            </div>
          )}
        </div>
        <ul className="px-4 mt-3 space-y-2.5">
          {!ready && <li className="skeleton h-28 rounded-xl" />}
          {ready && items.length === 0 && (
            <li className="card p-6 text-center text-[13px] text-muted">{online ? "No cases assigned to you yet." : "No saved worklist on this phone yet. Connect once to download it."}</li>
          )}
          {shown.map((c, i) => (
            <li key={c.id} onClick={() => nav(`/agent/case/${c.id}`)} className="card p-3.5 active:scale-[0.99] transition cursor-pointer animate-rise" style={{ animationDelay: `${Math.min(i, 8) * 25}ms` }}>
              <div className="flex items-start gap-3">
                <div className="h-8 w-8 rounded-lg bg-sunken text-[12px] font-semibold num flex items-center justify-center shrink-0 text-muted">{items.indexOf(c) + 1}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <div className="font-semibold text-[14.5px] truncate">{c.borrower_name}</div>
                    <div className="text-[14px] font-semibold num shrink-0">{inr(c.amount_due)}</div>
                  </div>
                  <div className="text-[12.5px] text-muted truncate mt-0.5 flex items-center gap-1"><MapPin size={12} className="shrink-0" />{c.address}</div>
                  <div className="flex flex-wrap items-center gap-1.5 mt-2">
                    <StatusPill status={c.status} />
                    <BucketPill bucket={c.dpd_bucket} dpd={c.dpd} />
                    <span className="chip bg-sunken text-muted">{c.distance_km} km</span>
                    {c.ptp && <span className={clsx("chip", c.ptp.date <= today ? "bg-warn/10 text-warn" : "bg-info/10 text-info")}><CalendarCheck size={11} /> {inr(c.ptp.amount)} · {dateOnly(c.ptp.date)}</span>}
                    {pendingFor[c.id] && <span className="chip bg-[#f59e0b]/15 text-[#b45309] dark:text-[#fbbf24]">{pendingFor[c.id]} unsynced</span>}
                  </div>
                  {c.top_reason && <div className="text-[12px] text-faint mt-1.5 truncate">Why first: {c.top_reason}</div>}
                </div>
              </div>
            </li>
          ))}
        </ul>
        <div className="text-center text-[11.5px] text-faint mt-5">{lastSync ? `Last synced ${ago(lastSync, now)}` : "Not synced yet"} · <button className="underline" onClick={() => run(true)}>sync now</button></div>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ case screen */
function Sheet({ title, children, footer, onClose }: { title: string; children: ReactNode; footer: ReactNode; onClose: () => void }) {
  return <Modal open onClose={onClose} title={title} footer={footer}>{children}</Modal>;
}

type SheetId = null | "checkin" | "call" | "note" | "ptp" | "pay" | "dispute" | "outbox";

function CaseScreen() {
  const { id } = useParams();
  const nav = useNavigate();
  const toast = useToast();
  const { user } = useAuth();
  const { items, outbox } = useStore();
  const { online, syncing, run } = useSync();
  const c = items.find((x) => x.id === id);
  const [sheet, setSheet] = useState<SheetId>(null);
  const [busy, setBusy] = useState(false);
  // form state
  const [src, setSrc] = useState<"device" | "demo">("device");
  const [outcome, setOutcome] = useState("met_borrower");
  const [remarks, setRemarks] = useState("");
  const [callOutcome, setCallOutcome] = useState("connected");
  const [lang, setLang] = useState("hi");
  const [noteText, setNoteText] = useState("");
  const [audio, setAudio] = useState<Blob | null>(null);
  const [amount, setAmount] = useState("");
  const [pdate, setPdate] = useState(new Date(Date.now() + 3 * 864e5).toISOString().slice(0, 10));
  const [dcat, setDcat] = useState("already_paid");
  const [link, setLink] = useState<any>(null);

  useEffect(() => { if (c) setLang(c.language ?? "hi"); }, [c?.id]); // eslint-disable-line
  if (!c) return <><TopBar title="Case" back={() => nav("/agent")} /><div className="p-6 text-center text-muted text-[13px]">This case is no longer on your worklist.</div></>;

  const queued = outbox.filter((o) => o.case_id === c.id);
  const done = (msg: string) => { toast({ kind: "ok", title: msg, body: online ? undefined : "Saved on this phone · will sync when online" }); setSheet(null); setRemarks(""); };
  const op = (type: Op["type"], data: any, label: string, extra: Partial<Op> = {}) =>
    enqueue({ client_id: uuid(), type, case_id: c.id, data: { ...data, device_ts: new Date().toISOString() }, label, ...extra });

  const checkIn = async () => {
    setBusy(true);
    try {
      let lat: number, lng: number, acc: number;
      if (src === "demo") {
        const ang = Math.random() * Math.PI * 2, d = 25 + Math.random() * 60;
        lat = c.lat + (d / 111000) * Math.cos(ang); lng = c.lng + (d / (111000 * Math.cos((c.lat * Math.PI) / 180))) * Math.sin(ang); acc = 8 + Math.random() * 10;
      } else {
        const pos = await new Promise<GeolocationPosition>((res, rej) => navigator.geolocation.getCurrentPosition(res, rej, { enableHighAccuracy: true, timeout: 12000, maximumAge: 0 }));
        lat = pos.coords.latitude; lng = pos.coords.longitude; acc = pos.coords.accuracy;
      }
      await op("visit", { lat, lng, accuracy_m: acc, outcome, remarks, location_source: src }, `Check-in · ${c.account_no}`);
      await patchLocal(c.id, { _last_checkin: new Date().toISOString() });
      done("Check-in saved with GPS and time");
    } catch (e: any) {
      toast({ kind: "err", title: "Couldn't get your location", body: e?.code === 1 ? "Location permission was denied. Allow it, or use the demo location." : "GPS timed out. Move to open sky or try again." });
    } finally { setBusy(false); }
  };

  const actions = [
    { id: "checkin", label: "Check in", icon: MapPinned, tone: "bg-field/10 text-field" },
    { id: "call", label: "Call", icon: Phone, tone: "bg-tele/10 text-tele" },
    { id: "note", label: "Voice note", icon: MessageSquarePlus, tone: "bg-digital/10 text-digital" },
    { id: "ptp", label: "Promise", icon: CalendarCheck, tone: "bg-info/10 text-info" },
    { id: "pay", label: "Collect", icon: IndianRupee, tone: "bg-ok/10 text-ok" },
    { id: "dispute", label: "Dispute", icon: AlertTriangle, tone: "bg-warn/10 text-warn" },
  ] as const;

  return (
    <>
      <TopBar back={() => nav("/agent")} title={<div className="leading-tight"><div className="text-[15px] font-semibold text-white truncate">{c.borrower_name}</div><div className="text-[12px] text-side-muted font-mono">{c.account_no}</div></div>}
        right={<NetPill online={online} pending={outbox.filter((o) => o.status === "pending").length} syncing={syncing} onSync={() => run(true)} />} />
      <div className="flex-1 overflow-y-auto pb-10">
        <div className="p-4 space-y-3">
          <div className="card p-4">
            <div className="flex items-baseline justify-between">
              <div><div className="label">Overdue</div><div className="text-[26px] font-semibold num tracking-tight">{inr(c.amount_due)}</div></div>
              <div className="text-right"><div className="label">EMI</div><div className="text-[15px] font-medium num">{inr(c.emi_amount)}</div></div>
            </div>
            <div className="flex flex-wrap gap-1.5 mt-2"><StatusPill status={c.status} /><BucketPill bucket={c.dpd_bucket} dpd={c.dpd} /><span className="chip bg-sunken text-muted">{LOAN[c.loan_type]}</span><span className="chip bg-sunken text-muted">{LANG[c.language]}</span></div>
            <div className="mt-3 pt-3 border-t border-line text-[13px] space-y-1.5">
              <div className="flex gap-2"><MapPin size={14} className="text-muted mt-0.5 shrink-0" />{c.address}</div>
              <a className="flex gap-2 text-brand" href={`https://www.google.com/maps/dir/?api=1&destination=${c.lat},${c.lng}`} target="_blank" rel="noreferrer"><Navigation size={14} className="mt-0.5" /> Directions · {c.distance_km} km from base</a>
            </div>
            {c.reasons?.length > 0 && (
              <div className="mt-3 pt-3 border-t border-line">
                <div className="label mb-1.5">Why this is on top · risk {c.risk_score}</div>
                {c.reasons.map((r: any) => <div key={r.code} className="flex justify-between text-[12.5px]"><span>{r.label}</span><span className={r.points > 0 ? "text-bad num" : "text-ok num"}>{r.points > 0 ? "+" : ""}{r.points}</span></div>)}
              </div>
            )}
            {c.ptp && <div className="mt-3 rounded-lg bg-info/10 text-info px-3 py-2 text-[12.5px]">Promise: {inr(c.ptp.amount)} by {dateOnly(c.ptp.date)}</div>}
          </div>

          <div className="grid grid-cols-3 gap-2">
            {actions.map((a) => (
              <button key={a.id} onClick={() => { setLink(null); setSheet(a.id); }} disabled={["PAID", "CLOSED"].includes(c.status) && a.id !== "note"}
                className="card py-3.5 flex flex-col items-center gap-1.5 active:scale-95 transition disabled:opacity-40">
                <span className={clsx("h-10 w-10 rounded-full flex items-center justify-center", a.tone)}><a.icon size={18} /></span>
                <span className="text-[12.5px] font-medium">{a.label}</span>
              </button>
            ))}
          </div>

          {queued.length > 0 && (
            <button onClick={() => setSheet("outbox")} className="w-full card p-3 flex items-center justify-between text-[13px]">
              <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-[#f59e0b]" /> {queued.length} action(s) waiting to sync</span><ChevronRight size={15} className="text-faint" />
            </button>
          )}
          <p className="text-[11.5px] text-faint text-center px-6">Signed in as {user?.name}. Every action is stamped with your GPS, device time and server time.</p>
        </div>
      </div>

      {sheet === "checkin" && (
        <Sheet onClose={() => setSheet(null)} title="Check in at this address" footer={<><button className="btn-ghost" onClick={() => setSheet(null)}>Cancel</button><button className="btn-primary" disabled={busy} onClick={checkIn}>{busy ? <Spinner /> : "Save check-in"}</button></>}>
          <div className="space-y-3">
            <Field group label="Location source" hint={src === "demo" ? "Demo only: places you 25–85 m from the borrower so the GPS check can be shown from a laptop. Recorded as demo GPS." : "Uses this phone's GPS. Must be within 300 m of the address to verify."}>
              <div className="grid grid-cols-2 gap-2">
                {([["device", "Device GPS"], ["demo", "Demo location"]] as const).map(([k, l]) => (
                  <button key={k} onClick={() => setSrc(k)} className={clsx("h-10 rounded-lg border text-[13px] font-medium", src === k ? "border-brand bg-brand-soft/50 text-brand-ink" : "border-line")}>{l}</button>
                ))}
              </div>
            </Field>
            <Field label="Outcome"><select className="select" value={outcome} onChange={(e) => setOutcome(e.target.value)}>{OUTCOMES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            <Field label="Remarks (optional)"><textarea className="input" rows={2} value={remarks} onChange={(e) => setRemarks(e.target.value)} /></Field>
          </div>
        </Sheet>
      )}
      {sheet === "call" && (
        <Sheet onClose={() => setSheet(null)} title="Log a call" footer={<><button className="btn-ghost" onClick={() => setSheet(null)}>Cancel</button>
          <button className="btn-primary" onClick={async () => { await op("call", { outcome: callOutcome, remarks }, `Call · ${c.account_no}`); done("Call logged"); }}>Save call</button></>}>
          <a href={`tel:${c.phone_for_call}`} className="btn-secondary w-full h-11 mb-3"><Phone size={16} /> Dial {c.phone}</a>
          <p className="text-[12px] text-muted mb-3">Calls are only allowed 8 AM – 7 PM. A call logged outside the window is recorded as blocked.</p>
          <Field label="Outcome"><select className="select" value={callOutcome} onChange={(e) => setCallOutcome(e.target.value)}>{CALL.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <div className="mt-3"><Field label="Remarks (optional)"><textarea className="input" rows={2} value={remarks} onChange={(e) => setRemarks(e.target.value)} /></Field></div>
        </Sheet>
      )}
      {sheet === "note" && (
        <Sheet onClose={() => setSheet(null)} title="Borrower note" footer={<><button className="btn-ghost" onClick={() => setSheet(null)}>Cancel</button>
          <button className="btn-primary" disabled={!noteText.trim()} onClick={async () => {
            await op("note", { text: noteText.trim(), language: lang, source: audio ? "voice" : "typed" }, `Note · ${c.account_no}`, { audio });
            setNoteText(""); setAudio(null); done("Note saved");
          }}>Save note</button></>}>
          <Field group label="Language">
            <div className="grid grid-cols-3 gap-2">
              {(["hi", "mr", "en"] as const).map((l) => <button key={l} onClick={() => setLang(l)} className={clsx("h-9 rounded-lg border text-[13px] font-medium", lang === l ? "border-brand bg-brand-soft/50 text-brand-ink" : "border-line")}>{LANG[l]}</button>)}
            </div>
          </Field>
          <div className="mt-4"><VoiceCapture language={lang} text={noteText} setText={setNoteText} onAudio={setAudio} /></div>
          {audio && <div className="mt-2 text-[12px] text-ok">Recording attached ({Math.round(audio.size / 1024)} KB)</div>}
          <div className="mt-3"><Field label="Transcript (edit before saving)" hint="Sentiment and reason are detected on the server. With no network the note waits on this phone.">
            <textarea className="input" rows={4} value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder={lang === "mr" ? "उदा. पगार आल्यावर पूर्ण हप्ता भरेन" : lang === "hi" ? "जैसे: सैलरी आते ही किस्त भर दूंगा" : "e.g. Will pay after salary on the 10th"} />
          </Field></div>
        </Sheet>
      )}
      {sheet === "ptp" && (
        <Sheet onClose={() => setSheet(null)} title="Record a promise to pay" footer={<><button className="btn-ghost" onClick={() => setSheet(null)}>Cancel</button>
          <button className="btn-primary" disabled={!Number(amount)} onClick={async () => {
            await op("ptp", { amount: Number(amount), promised_date: pdate }, `Promise · ${c.account_no}`);
            await patchLocal(c.id, { ptp: { amount: Number(amount), date: pdate }, status: "PTP" });
            setAmount(""); done("Promise recorded");
          }}>Save promise</button></>}>
          <div className="space-y-3">
            <Field label="Amount" hint={`Overdue ${inr(c.amount_due)}`}><input className="input num" type="number" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={String(Math.round(c.amount_due))} /></Field>
            <Field label="Promised date" hint="If unpaid one day after this date, the promise breaks and the case moves on automatically."><input className="input" type="date" value={pdate} min={new Date().toISOString().slice(0, 10)} onChange={(e) => setPdate(e.target.value)} /></Field>
          </div>
        </Sheet>
      )}
      {sheet === "pay" && (
        <Sheet onClose={() => setSheet(null)} title="Collect payment" footer={<button className="btn-ghost" onClick={() => setSheet(null)}>Close</button>}>
          {!online ? (
            <div className="text-[13px] rounded-lg bg-warn/10 text-warn p-3">Payments need a connection. The case is marked paid only after the payment gateway confirms, so nothing is recorded offline.</div>
          ) : link ? <PayLinkCard link={link} /> : (
            <>
              <Field label="Amount to collect"><input className="input num" type="number" value={amount} placeholder={String(Math.round(c.amount_due || c.emi_amount))} onChange={(e) => setAmount(e.target.value)} /></Field>
              <button className="btn-primary w-full mt-3 h-10" disabled={busy} onClick={async () => {
                setBusy(true);
                try { setLink(await api(`/cases/${c.id}/payment-link`, { method: "POST", json: { amount: amount ? Number(amount) : null } })); }
                catch (e: any) { toast({ kind: "err", title: "Couldn't create the link", body: e.message }); }
                finally { setBusy(false); }
              }}>{busy ? <Spinner /> : "Show UPI QR & link"}</button>
              <p className="text-[12px] text-muted mt-2">The borrower scans and pays on their own phone. You'll see the case turn Paid when the gateway confirms.</p>
            </>
          )}
        </Sheet>
      )}
      {sheet === "dispute" && (
        <Sheet onClose={() => setSheet(null)} title="Raise a dispute" footer={<><button className="btn-ghost" onClick={() => setSheet(null)}>Cancel</button>
          <button className="btn-primary" onClick={async () => { await op("dispute", { category: dcat, description: remarks }, `Dispute · ${c.account_no}`); await patchLocal(c.id, { status: "DISPUTED" }); done("Dispute raised · contact paused"); }}>Raise dispute</button></>}>
          <Field label="Category"><select className="select" value={dcat} onChange={(e) => setDcat(e.target.value)}>{DISPUTES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <div className="mt-3"><Field label="What did the borrower say?"><textarea className="input" rows={3} value={remarks} onChange={(e) => setRemarks(e.target.value)} /></Field></div>
        </Sheet>
      )}
      {sheet === "outbox" && (
        <Sheet onClose={() => setSheet(null)} title="Waiting to sync" footer={<><button className="btn-ghost" onClick={() => setSheet(null)}>Close</button><button className="btn-primary" disabled={!online} onClick={() => run(true)}><RefreshCw size={14} /> Sync now</button></>}>
          <ul className="divide-y divide-line">
            {queued.map((o) => (
              <li key={o.client_id} className="py-2.5 text-[13px]">
                <div className="flex justify-between"><span className="font-medium">{o.label}</span><span className={o.status === "rejected" ? "text-bad" : "text-muted"}>{o.status}</span></div>
                <div className="text-[11.5px] text-faint font-mono">{o.client_id.slice(0, 8)} · {new Date(o.created_at).toLocaleTimeString("en-IN")}</div>
                {o.error && <div className="text-[12px] text-bad mt-0.5">{o.error}</div>}
              </li>
            ))}
          </ul>
        </Sheet>
      )}
    </>
  );
}

export default function AgentApp() {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login?next=/agent" replace />;
  if (user.role !== "agent") {
    return (
      <Frame>
        <TopBar title={<Logo dark size={24} />} />
        <div className="p-6 text-center">
          <div className="text-[15px] font-medium mt-6">The field app is for agents</div>
          <p className="text-[13px] text-muted mt-1">You're signed in as {user.role_label}. Sign in as an agent (agent@recoveriq.in) to try it.</p>
          <a href="/app" className="btn-primary mt-5">Go to the console</a>
        </div>
      </Frame>
    );
  }
  return (
    <Frame>
      <Routes>
        <Route index element={<Worklist />} />
        <Route path="case/:id" element={<CaseScreen />} />
        <Route path="*" element={<Navigate to="/agent" replace />} />
      </Routes>
    </Frame>
  );
}
