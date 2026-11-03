import clsx from "clsx";
import { ArrowRight, Eye, EyeOff, Lock } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "../components/badges";
import { Spinner } from "../components/ui";
import { useAuth } from "../lib/auth";

const DEMO = [
  { role: "Field agent", email: "agent@recoveriq.in", who: "Rahul Pawar · Mumbai" },
  { role: "Branch manager", email: "l2.mumbai@recoveriq.in", who: "Suresh Nair · L2" },
  { role: "Regional manager", email: "l1.west@recoveriq.in", who: "Neha Kulkarni · L1 West" },
  { role: "Executive", email: "exec@recoveriq.in", who: "Vikram Mehta · HQ" },
  { role: "Administrator", email: "admin@recoveriq.in", who: "Aditi Rao · Admin" },
];

export default function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) return <Navigate to={user.role === "agent" ? "/agent" : params.get("next") || "/app"} replace />;

  const submit = async (e?: React.FormEvent, creds?: { email: string; password: string }) => {
    e?.preventDefault();
    const c = creds ?? { email, password };
    if (!c.email || !c.password) { setError("Enter your email and password"); return; }
    setBusy(true);
    setError(null);
    try {
      const u = await login(c.email, c.password);
      nav(u.role === "agent" ? "/agent" : params.get("next") || "/app", { replace: true });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.05fr_1fr] bg-canvas">
      <aside className="hidden lg:flex sidebar-surface grain relative flex-col justify-between p-12 text-side-text overflow-hidden">
        <Logo dark size={32} />
        <div className="relative max-w-[480px]">
          <p className="text-[12px] uppercase tracking-[0.14em] text-[#5eead4]/80 font-semibold">Collections, done fairly</p>
          <h1 className="mt-4 text-[40px] leading-[1.08] font-semibold tracking-[-0.025em] text-white">
            One case.<br />One trail.<br /><span className="text-[#5eead4]">Full visibility.</span>
          </h1>
          <p className="mt-5 text-[15px] leading-7 text-side-text/70">
            Score every overdue account with reasons, send it to the right channel, let agents work offline,
            and mark a case paid only when the payment gateway confirms it.
          </p>
          <dl className="mt-10 grid grid-cols-3 gap-6 border-t border-white/10 pt-6">
            {[["18 / 18", "PS-01 requirements built"], ["0", "payments marked paid without the gateway"], ["8 AM–7 PM", "contact window, enforced in code"]].map(([k, v]) => (
              <div key={v}>
                <dt className="text-[20px] font-semibold text-white num">{k}</dt>
                <dd className="text-[12px] text-side-muted mt-1 leading-5">{v}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="relative text-[12px] text-side-muted">QUASAR 5.0 · PS-01 Fintech · prototype with synthetic data</div>
        <svg className="absolute -right-24 -bottom-24 opacity-[0.07]" width="520" height="520" viewBox="0 0 200 200" aria-hidden>
          {Array.from({ length: 9 }).map((_, i) => <circle key={i} cx="100" cy="100" r={12 + i * 11} fill="none" stroke="#fff" strokeWidth="0.6" />)}
        </svg>
      </aside>

      <main className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-[400px] animate-rise">
          <div className="lg:hidden mb-8"><Logo /></div>
          <h2 className="text-[24px] font-semibold tracking-tight">Sign in</h2>
          <p className="text-[13.5px] text-muted mt-1">Use your work email. Agents are taken straight to their worklist.</p>
          <form className="mt-7 space-y-4" onSubmit={submit}>
            <label className="block">
              <span className="block text-[12.5px] font-medium mb-1.5">Email</span>
              <input className="input h-10" type="email" autoComplete="username" value={email}
                onChange={(e) => setEmail(e.target.value)} placeholder="name@recoveriq.in" />
            </label>
            <label className="block">
              <span className="block text-[12.5px] font-medium mb-1.5">Password</span>
              <div className="relative">
                <input className="input h-10 pr-10" type={show ? "text" : "password"} autoComplete="current-password"
                  value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
                <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-2 top-1/2 -translate-y-1/2 text-faint hover:text-ink p-1" aria-label="Show password">
                  {show ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </label>
            {error && <div className="text-[13px] text-bad bg-bad/[0.07] border border-bad/20 rounded-lg px-3 py-2 animate-fade">{error}</div>}
            <button className="btn-primary w-full h-10 text-[14px]" disabled={busy}>
              {busy ? <Spinner /> : <>Sign in <ArrowRight size={16} /></>}
            </button>
          </form>

          <div className="mt-9">
            <div className="flex items-center gap-3 text-[11.5px] text-faint uppercase tracking-[0.08em] font-semibold">
              <span className="h-px flex-1 bg-line" /> Demo accounts <span className="h-px flex-1 bg-line" />
            </div>
            <div className="mt-3 grid gap-1.5">
              {DEMO.map((d) => (
                <button key={d.email} disabled={busy} onClick={() => { setEmail(d.email); setPassword("Demo@1234"); submit(undefined, { email: d.email, password: "Demo@1234" }); }}
                  className={clsx("group flex items-center justify-between text-left rounded-lg border border-line bg-surface px-3 py-2.5",
                    "hover:border-brand/40 hover:bg-brand-soft/40 transition")}>
                  <span>
                    <span className="block text-[13px] font-medium">{d.role}</span>
                    <span className="block text-[12px] text-muted">{d.who}</span>
                  </span>
                  <ArrowRight size={15} className="text-faint group-hover:text-brand group-hover:translate-x-0.5 transition" />
                </button>
              ))}
            </div>
            <p className="mt-3 text-[12px] text-muted flex items-center gap-1.5"><Lock size={12} /> Demo password for every account: <span className="kbd">Demo@1234</span></p>
          </div>
        </div>
      </main>
    </div>
  );
}
