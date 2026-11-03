import clsx from "clsx";
import { Building, CheckCircle2, CreditCard, FlaskConical, Lock, Smartphone, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Spinner } from "../components/ui";
import { api } from "../lib/api";
import { inr } from "../lib/format";

/** Hosted checkout of the built-in sandbox gateway. Deliberately styled as a separate party: the
 * lender's app never sees card/UPI details and only learns about the payment from the gateway's
 * signed webhook. */
export default function Checkout() {
  const { linkId } = useParams();
  const nav = useNavigate();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [method, setMethod] = useState<"upi" | "card" | "netbanking">("upi");
  const [amount, setAmount] = useState("");
  const [outcome, setOutcome] = useState<"success" | "failure">("success");
  const [delivery, setDelivery] = useState<"normal" | "drop">("normal");
  const [stage, setStage] = useState<"form" | "processing" | "done" | "failed">("form");
  const [res, setRes] = useState<any>(null);

  useEffect(() => { api(`/gateway/sandbox/${linkId}`, { auth: false }).then(setD).catch((e) => setErr(e.message)); }, [linkId]);

  const pay = async () => {
    setStage("processing");
    try {
      const r = await api(`/gateway/sandbox/${linkId}/pay`, { method: "POST", auth: false, json: { method, amount: amount ? Number(amount) : null, outcome, delivery } });
      setRes(r);
      await new Promise((ok) => setTimeout(ok, 1400));
      setStage(r.status === "captured" ? "done" : "failed");
      setTimeout(() => nav(`${r.return_url}?from=gateway`), r.status === "captured" ? 1600 : 2200);
    } catch (e: any) { setErr(e.message); setStage("form"); }
  };

  return (
    <div className="min-h-screen bg-[#eef1f6] dark:bg-[#0b0f17] flex items-start sm:items-center justify-center p-0 sm:p-6 text-[#0f172a] dark:text-[#e2e8f0]">
      <div className="w-full max-w-[420px] bg-white dark:bg-[#121826] sm:rounded-2xl shadow-[0_20px_60px_-20px_rgba(15,23,42,.35)] overflow-hidden">
        <div className="bg-[#1e3a8a] text-white px-5 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold tracking-tight"><span className="h-6 w-6 rounded-md bg-white/15 flex items-center justify-center text-[12px]">S</span> Sandbox Pay</div>
            <span className="text-[11px] rounded-full bg-[#fbbf24] text-[#422006] px-2 py-0.5 font-semibold">TEST MODE</span>
          </div>
          {d && <div className="mt-3"><div className="text-[12px] text-white/70">{d.merchant}</div><div className="text-[13px] text-white/90">{d.description}</div>
            <div className="text-[28px] font-semibold num mt-1">{inr(amount ? Number(amount) : d.remaining, 2)}</div></div>}
        </div>

        {err && <div className="m-5 text-[13px] text-[#b91c1c] bg-[#fef2f2] rounded-lg p-3">{err}</div>}
        {!d && !err && <div className="py-16 flex justify-center"><Spinner size={22} /></div>}

        {d && stage === "form" && (
          <div className="p-5">
            {d.remaining <= 0 ? <div className="text-[14px] text-center py-6">This link is fully paid.</div> : (
              <>
                <div className="grid grid-cols-3 gap-2">
                  {([["upi", "UPI", Smartphone], ["card", "Card", CreditCard], ["netbanking", "Netbanking", Building]] as const).map(([k, l, I]) => (
                    <button key={k} onClick={() => setMethod(k)} className={clsx("rounded-xl border py-2.5 flex flex-col items-center gap-1 text-[12.5px] font-medium transition",
                      method === k ? "border-[#1e3a8a] bg-[#eff6ff] text-[#1e3a8a] dark:bg-[#1e293b] dark:text-[#93c5fd] dark:border-[#3b82f6]" : "border-[#e2e8f0] dark:border-[#334155]")}><I size={17} />{l}</button>
                  ))}
                </div>
                <div className="mt-4 text-[13px]">
                  {method === "upi" && <label className="block"><span className="text-[12px] text-[#64748b]">UPI ID</span><input className="input mt-1" defaultValue="success@sandbox" /></label>}
                  {method === "card" && <div className="grid grid-cols-2 gap-2"><input className="input col-span-2 font-mono" defaultValue="4111 1111 1111 1111" /><input className="input" defaultValue="12/30" /><input className="input" defaultValue="123" /></div>}
                  {method === "netbanking" && <select className="select"><option>State Bank of India</option><option>HDFC Bank</option><option>Bank of Maharashtra</option><option>ICICI Bank</option></select>}
                  <p className="text-[11.5px] text-[#64748b] mt-1.5">Test credentials only. No real money moves.</p>
                </div>
                <label className="block mt-4"><span className="text-[12px] text-[#64748b]">Amount (part-payment allowed)</span>
                  <input className="input mt-1 num" type="number" min={1} max={d.remaining} placeholder={String(d.remaining)} value={amount} onChange={(e) => setAmount(e.target.value)} /></label>

                <div className="mt-4 rounded-xl border border-dashed border-[#cbd5e1] dark:border-[#334155] p-3">
                  <div className="text-[12px] font-semibold flex items-center gap-1.5 text-[#475569] dark:text-[#94a3b8]"><FlaskConical size={13} /> Sandbox controls</div>
                  <div className="grid grid-cols-2 gap-2 mt-2 text-[12.5px]">
                    <select className="select h-8 text-[12.5px]" value={outcome} onChange={(e) => setOutcome(e.target.value as any)}><option value="success">Payment succeeds</option><option value="failure">Bank declines</option></select>
                    <select className="select h-8 text-[12.5px]" value={delivery} onChange={(e) => setDelivery(e.target.value as any)}><option value="normal">Send webhook</option><option value="drop">Lose the webhook</option></select>
                  </div>
                  {delivery === "drop" && <p className="text-[11.5px] text-[#b45309] mt-1.5">The lender won't hear about this payment until its reconciliation job asks the gateway.</p>}
                </div>
                <button onClick={pay} className="w-full h-12 mt-5 rounded-xl bg-[#1e3a8a] hover:bg-[#1e40af] text-white font-semibold text-[15px] flex items-center justify-center gap-2 transition active:scale-[.99]">
                  <Lock size={16} /> Pay {inr(amount ? Number(amount) : d.remaining, 2)}
                </button>
              </>
            )}
          </div>
        )}
        {stage === "processing" && <div className="py-16 text-center"><Spinner size={26} className="text-[#1e3a8a] mx-auto" /><div className="mt-3 text-[14px]">Processing with your bank…</div></div>}
        {stage === "done" && (
          <div className="py-14 text-center px-6 animate-rise">
            <CheckCircle2 size={44} className="text-[#16a34a] mx-auto" />
            <div className="mt-3 text-[16px] font-semibold">Payment captured</div>
            <div className="text-[13px] text-[#64748b] mt-1">{delivery === "drop" ? "Webhook dropped (sandbox). The merchant will find it by reconciliation." : "Notifying the merchant with a signed webhook…"}</div>
            <div className="font-mono text-[11.5px] text-[#94a3b8] mt-3">{res?.payment_id}</div>
          </div>
        )}
        {stage === "failed" && (
          <div className="py-14 text-center px-6 animate-rise">
            <XCircle size={44} className="text-[#dc2626] mx-auto" />
            <div className="mt-3 text-[16px] font-semibold">Payment declined</div>
            <div className="text-[13px] text-[#64748b] mt-1">Nothing was charged. Returning to the merchant…</div>
          </div>
        )}
        <div className="px-5 py-3 border-t border-[#e2e8f0] dark:border-[#1e293b] text-[11px] text-[#94a3b8] flex items-center gap-1.5"><Lock size={11} /> Secured by Sandbox Pay · stands in for Razorpay in this prototype</div>
      </div>
    </div>
  );
}
