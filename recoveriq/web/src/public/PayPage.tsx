import clsx from "clsx";
import { BadgeCheck, CalendarDays, CheckCircle2, Clock, FileText, Lock, ShieldCheck, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Logo } from "../components/badges";
import { Spinner } from "../components/ui";
import { api } from "../lib/api";
import { dt, inr } from "../lib/format";

type L = "en" | "hi" | "mr";
const T: Record<L, Record<string, string>> = {
  en: { due: "Amount due", pay: "Pay securely", promise: "Can't pay today? Choose a date", promiseBtn: "Confirm my promise", paid: "Payment received", awaiting: "Waiting for confirmation from the payment gateway…", agent: "Your recovery officer", receipts: "Receipts", date: "Date", amount: "Amount", thanks: "Thank you. Your account is now regular.", promised: "Thank you, we've noted your promise.", notice: "Your details are used only to service this loan. Contact happens only between 8 AM and 7 PM. You can raise a dispute with your officer at any time." },
  hi: { due: "देय राशि", pay: "सुरक्षित भुगतान करें", promise: "आज भुगतान नहीं कर सकते? तारीख चुनें", promiseBtn: "वादा दर्ज करें", paid: "भुगतान प्राप्त हुआ", awaiting: "पेमेंट गेटवे से पुष्टि की प्रतीक्षा…", agent: "आपके वसूली अधिकारी", receipts: "रसीदें", date: "तारीख", amount: "राशि", thanks: "धन्यवाद। आपका खाता अब नियमित है।", promised: "धन्यवाद, आपका वादा दर्ज हो गया है।", notice: "आपकी जानकारी केवल इस ऋण की सेवा के लिए उपयोग होती है। संपर्क केवल सुबह 8 से शाम 7 बजे के बीच होता है।" },
  mr: { due: "देय रक्कम", pay: "सुरक्षित भरणा करा", promise: "आज भरू शकत नाही? तारीख निवडा", promiseBtn: "वचन नोंदवा", paid: "भरणा मिळाला", awaiting: "पेमेंट गेटवेच्या पुष्टीची वाट पाहत आहोत…", agent: "तुमचे वसुली अधिकारी", receipts: "पावत्या", date: "तारीख", amount: "रक्कम", thanks: "धन्यवाद. तुमचे खाते आता नियमित आहे.", promised: "धन्यवाद, तुमचे वचन नोंदवले आहे.", notice: "तुमची माहिती फक्त या कर्जासाठी वापरली जाते. संपर्क फक्त सकाळी 8 ते संध्याकाळी 7 दरम्यान होतो." },
};

export default function PayPage() {
  const { token } = useParams();
  const [params] = useSearchParams();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [lang, setLangState] = useState<L>(() => {
    try { return (localStorage.getItem("riq-pay-lang") as L) || "en"; } catch { return "en"; }
  });
  const chosen = (() => { try { return !!localStorage.getItem("riq-pay-lang"); } catch { return false; } })();
  const setLang = (l: L) => { setLangState(l); try { localStorage.setItem("riq-pay-lang", l); } catch { /* ignore */ } };
  const [busy, setBusy] = useState(false);
  const [amt, setAmt] = useState("");
  const [date, setDate] = useState(new Date(Date.now() + 3 * 864e5).toISOString().slice(0, 10));
  const [promised, setPromised] = useState(false);
  const fromGateway = params.get("from") === "gateway";

  const load = () => api(`/public/pay/${token}`, { auth: false }).then((x) => { setD(x); setErr(null); }).catch((e) => setErr(e.message));
  useEffect(() => { load().then(() => {}); }, [token]); // eslint-disable-line
  // default to the borrower's preferred language unless they already picked one on this device
  useEffect(() => { if (d && !chosen) setLangState((["en", "hi", "mr"].includes(d.language) ? d.language : "en") as L); }, [d?.language]); // eslint-disable-line
  const waiting = d && d.case_status === "PAYMENT_PENDING";
  useEffect(() => { if (!waiting) return; const t = setInterval(load, 2000); return () => clearInterval(t); }, [waiting]); // eslint-disable-line

  const t = T[lang];
  if (err) return <Shell><div className="card p-6 text-center"><div className="font-medium">This link can't be opened</div><div className="text-[13px] text-muted mt-1">{err}</div></div></Shell>;
  if (!d) return <Shell><div className="flex justify-center py-20"><Spinner size={22} /></div></Shell>;
  const settled = d.remaining <= 0 || ["PAID", "CLOSED"].includes(d.case_status);

  return (
    <Shell lang={lang} setLang={setLang} lender={d.lender}>
      <div className="card overflow-hidden animate-rise">
        <div className="p-5">
          <div className="flex items-center justify-between text-[12.5px] text-muted">
            <span>{d.borrower} · {d.account}</span><span className="flex items-center gap-1"><Lock size={12} /> Secure link</span>
          </div>
          {settled ? (
            <div className="text-center py-6 animate-rise">
              <div className="mx-auto h-14 w-14 rounded-full bg-ok/10 text-ok flex items-center justify-center"><CheckCircle2 size={30} /></div>
              <div className="text-[20px] font-semibold mt-3">{t.paid}</div>
              <div className="text-[13.5px] text-muted mt-1">{d.case_status === "PAID" || d.case_status === "CLOSED" ? t.thanks : ""}</div>
            </div>
          ) : (
            <>
              <div className="label mt-4">{t.due}</div>
              <div className="text-[34px] font-semibold num tracking-tight">{inr(d.remaining, 2)}</div>
              {d.amount_paid > 0 && <div className="text-[12.5px] text-ok">{inr(d.amount_paid)} already received on this link</div>}
              {waiting ? (
                <div className="mt-5 rounded-xl bg-warn/10 text-warn p-4 flex items-center gap-3 text-[13.5px]"><Spinner /> {t.awaiting}</div>
              ) : (
                <button className="btn-primary w-full h-12 text-[15px] mt-5" disabled={busy || d.expired}
                  onClick={async () => {
                    setBusy(true);
                    try {
                      const r = await api(`/public/pay/${token}/checkout`, { method: "POST", auth: false });
                      if (r.checkout_url.startsWith("http")) window.location.href = r.checkout_url; else window.location.assign(r.checkout_url);
                    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
                  }}>{busy ? <Spinner /> : <><ShieldCheck size={18} /> {t.pay}</>}</button>
              )}
              {d.expired && <div className="text-[12.5px] text-bad mt-2">This link has expired. Ask your officer for a new one.</div>}
              <div className="flex items-center justify-center gap-3 mt-3 text-[11.5px] text-faint"><span>UPI</span>·<span>Cards</span>·<span>Netbanking</span>·<span className="capitalize">{d.gateway} (test)</span></div>
            </>
          )}
        </div>
        {d.agent && (
          <div className="px-5 py-3.5 bg-sunken/60 border-t border-line flex items-center gap-3 text-[13px]">
            <span className="h-9 w-9 rounded-full bg-brand-soft text-brand-ink flex items-center justify-center"><UserRound size={17} /></span>
            <div className="flex-1"><div className="text-[11.5px] text-muted">{t.agent}</div><div className="font-medium">{d.agent.name} <span className="text-muted font-normal">· ID {d.agent.id}</span></div></div>
            <BadgeCheck size={18} className="text-ok" />
          </div>
        )}
      </div>

      {d.can_promise && !settled && !waiting && (
        <div className="card p-5 mt-4 animate-rise">
          {promised ? <div className="text-[14px] text-ok flex items-center gap-2"><CheckCircle2 size={18} /> {t.promised}</div> : (
            <>
              <div className="font-medium text-[14px] flex items-center gap-2"><CalendarDays size={16} className="text-brand" /> {t.promise}</div>
              <div className="grid grid-cols-2 gap-2 mt-3">
                <label><span className="text-[12px] text-muted">{t.amount}</span><input className="input num mt-1" type="number" value={amt} onChange={(e) => setAmt(e.target.value)} placeholder={String(Math.round(d.remaining))} /></label>
                <label><span className="text-[12px] text-muted">{t.date}</span><input className="input mt-1" type="date" value={date} min={new Date().toISOString().slice(0, 10)} onChange={(e) => setDate(e.target.value)} /></label>
              </div>
              <button className="btn-secondary w-full mt-3" disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try { await api(`/public/pay/${token}/promise`, { method: "POST", auth: false, json: { amount: Number(amt || d.remaining), promised_date: date } }); setPromised(true); load(); }
                  catch (e: any) { alert(e.message); } finally { setBusy(false); }
                }}>{t.promiseBtn}</button>
            </>
          )}
        </div>
      )}

      {d.receipts.length > 0 && (
        <div className="card p-5 mt-4 animate-rise">
          <div className="font-medium text-[14px] mb-2">{t.receipts}</div>
          {d.receipts.map((r: any) => (
            <a key={r.id} href={`/api/v1/public/pay/${token}/receipt/${r.id}.pdf`} target="_blank" rel="noreferrer"
              className="flex items-center justify-between py-2.5 border-b border-line last:border-0 text-[13px] hover:text-brand">
              <span className="flex items-center gap-2"><FileText size={15} /> {r.receipt_no}</span>
              <span className="text-right"><span className="num font-medium">{inr(r.amount, 2)}</span><span className="block text-[11.5px] text-muted">{dt(r.confirmed_at)}</span></span>
            </a>
          ))}
        </div>
      )}
      <p className="text-[11.5px] text-muted mt-5 leading-5 flex gap-2"><Clock size={13} className="shrink-0 mt-0.5" />{t.notice}</p>
    </Shell>
  );
}

function Shell({ children, lang, setLang, lender }: { children: React.ReactNode; lang?: L; setLang?: (l: L) => void; lender?: string }) {
  return (
    <div className="min-h-screen bg-canvas">
      <header className="sidebar-surface text-side-text">
        <div className="max-w-[460px] mx-auto px-5 h-14 flex items-center justify-between">
          <div><div className="text-[14px] font-semibold text-white">{lender?.replace(" (demo NBFC)", "") ?? "Loan repayment"}</div><div className="text-[11px] text-side-muted">Powered by RecoverIQ</div></div>
          {lang && setLang && (
            <div className="flex rounded-lg bg-white/10 p-0.5">
              {(["en", "hi", "mr"] as L[]).map((l) => (
                <button key={l} onClick={() => setLang(l)} className={clsx("px-2 h-7 rounded-md text-[12px]", lang === l ? "bg-white text-[#10201b] font-medium" : "text-white/70")}>
                  {{ en: "EN", hi: "हिं", mr: "मरा" }[l]}
                </button>
              ))}
            </div>
          )}
        </div>
      </header>
      <main className="max-w-[460px] mx-auto px-4 py-6">{children}</main>
      <footer className="max-w-[460px] mx-auto px-5 pb-8 text-[11px] text-faint flex items-center gap-2"><Logo size={16} /> Prototype · test-mode payments only</footer>
    </div>
  );
}
