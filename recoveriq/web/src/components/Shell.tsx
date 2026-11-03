import clsx from "clsx";
import {
  Activity, Bell, BookCheck, Brain, ChevronsUpDown, Clock3, CreditCard, FileUp, Gavel, Inbox, LayoutDashboard, ListChecks,
  LogOut, Map as MapIcon, Menu, Monitor, Moon, Scale, ScrollText, ShieldCheck, SlidersHorizontal, Smartphone, Sun, Trophy,
  Users, X, Smile,
} from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { can, useAuth } from "../lib/auth";
import { useApi, useLive, useLiveStatus } from "../lib/hooks";
import { useTheme, type ThemePref } from "../lib/theme";
import { Logo } from "./badges";
import { phoneUrl, QrImage } from "./PayLink";
import { Modal } from "./ui";
import { useAction, useToast } from "./ui";

type Item = { to: string; label: string; icon: any; show?: (u: any) => boolean; badge?: string };
const NAV: { group: string; items: Item[] }[] = [
  { group: "Overview", items: [{ to: "/app", label: "Dashboard", icon: LayoutDashboard }] },
  {
    group: "Collections", items: [
      { to: "/app/cases", label: "Case queue", icon: ListChecks },
      { to: "/app/promises", label: "Promises & escalations", icon: BookCheck },
      { to: "/app/disputes", label: "Disputes", icon: Gavel },
      { to: "/app/intake", label: "Case intake", icon: FileUp, show: can.intake },
    ],
  },
  {
    group: "Field", items: [
      { to: "/app/allocation", label: "Allocation", icon: Users },
      { to: "/app/field", label: "Live field map", icon: MapIcon },
      { to: "/app/leaderboard", label: "Leaderboard", icon: Trophy },
    ],
  },
  {
    group: "Money & contact", items: [
      { to: "/app/payments", label: "Payments & webhooks", icon: CreditCard },
      { to: "/app/notifications", label: "Message outbox", icon: Inbox },
    ],
  },
  {
    group: "Insight", items: [
      { to: "/app/sentiment", label: "Sentiment map", icon: Smile },
      { to: "/app/models", label: "Learning loop", icon: Brain, show: can.models },
    ],
  },
  {
    group: "Governance", items: [
      { to: "/app/rules", label: "Rules", icon: SlidersHorizontal },
      { to: "/app/compliance", label: "Compliance", icon: Scale, show: can.compliance },
      { to: "/app/audit", label: "Audit trail", icon: ScrollText, show: can.audit },
    ],
  },
];

function ThemeSwitch() {
  const [pref, setPref] = useTheme();
  const opts: { id: ThemePref; icon: any; label: string }[] = [
    { id: "light", icon: Sun, label: "Light" }, { id: "system", icon: Monitor, label: "System" }, { id: "dark", icon: Moon, label: "Dark" },
  ];
  return (
    <div className="flex p-0.5 rounded-lg bg-sunken border border-line">
      {opts.map((o) => (
        <button key={o.id} onClick={() => setPref(o.id)} title={o.label} aria-label={o.label}
          className={clsx("h-7 w-7 rounded-md flex items-center justify-center transition",
            pref === o.id ? "bg-surface text-ink shadow-sm ring-1 ring-line" : "text-faint hover:text-ink")}>
          <o.icon size={14} />
        </button>
      ))}
    </div>
  );
}

function DemoClock() {
  const { data, reload } = useApi<any>("/meta");
  const [open, setOpen] = useState(false);
  const { busy, run } = useAction();
  const ref = useRef<HTMLDivElement>(null);
  const [time, setTime] = useState("20:30");
  useLive((e) => { if (e.type === "clock.changed") reload(true); });
  useEffect(() => {
    const t = setInterval(() => reload(true), 30000);
    const fn = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", fn);
    return () => { clearInterval(t); document.removeEventListener("mousedown", fn); };
  }, [reload]);
  if (!data?.demo_mode) return null;
  const shifted = Math.abs(data.clock.offset_seconds) > 60;
  const act = (body: any, label: string) => run("clock", () => api("/clock", { method: "POST", json: body }),
    (r: any) => `${label}${r.promises_broken ? ` · ${r.promises_broken} promise(s) broke` : ""}`).then(() => reload(true));
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)}
        className={clsx("h-8 px-2.5 rounded-lg border text-[12.5px] flex items-center gap-1.5 transition num",
          shifted ? "border-warn/40 bg-warn/10 text-warn" : "border-line bg-surface text-muted hover:text-ink")}>
        <Clock3 size={14} />
        <span className="hidden md:inline">{data.clock.local}</span>
        <span className="md:hidden">{data.clock.local.split(", ")[1]}</span>
        {shifted && <span className="hidden lg:inline font-medium">· simulated</span>}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-[290px] card shadow-pop p-4 z-50 animate-rise">
          <div className="text-[13px] font-semibold">Business clock</div>
          <p className="text-[12px] text-muted mt-1 leading-5">
            Shift the clock to demo quiet hours and broken promises without waiting. Every rule reads this clock; changes are audited.
          </p>
          <div className="grid grid-cols-2 gap-2 mt-3">
            <button className="btn-secondary btn-sm" disabled={!!busy} onClick={() => act({ mode: "set_local_time", time: "11:00" }, "Clock set to 11:00")}>11:00 AM</button>
            <button className="btn-secondary btn-sm" disabled={!!busy} onClick={() => act({ mode: "set_local_time", time: "20:30" }, "Clock set to 8:30 PM")}>8:30 PM</button>
            <button className="btn-secondary btn-sm" disabled={!!busy} onClick={() => act({ mode: "advance_days", value: 1 }, "Advanced 1 day")}>+1 day</button>
            <button className="btn-secondary btn-sm" disabled={!!busy} onClick={() => act({ mode: "advance_days", value: 3 }, "Advanced 3 days")}>+3 days</button>
          </div>
          <div className="flex gap-2 mt-2">
            <input type="time" className="input h-8 text-[12.5px]" value={time} onChange={(e) => setTime(e.target.value)} />
            <button className="btn-secondary btn-sm" disabled={!!busy} onClick={() => act({ mode: "set_local_time", time }, `Clock set to ${time}`)}>Set</button>
          </div>
          <button className="btn-ghost btn-sm w-full mt-2" disabled={!!busy || !shifted} onClick={() => act({ mode: "reset" }, "Back to real time")}>Reset to real time</button>
        </div>
      )}
    </div>
  );
}

function LiveDot() {
  const on = useLiveStatus();
  return (
    <span className="hidden sm:flex items-center gap-1.5 text-[12px] text-muted" title={on ? "Live updates connected" : "Reconnecting…"}>
      <span className={clsx("h-2 w-2 rounded-full", on ? "bg-ok pulse-dot text-ok" : "bg-faint")} />
      {on ? "Live" : "Offline"}
    </span>
  );
}

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user } = useAuth();
  const { data: meta } = useApi<any>("/meta");
  const [qr, setQr] = useState(false);
  const phone = phoneUrl(meta, "/agent") ?? `${location.origin}/agent`;
  return (
    <div className="sidebar-surface grain relative h-full flex flex-col text-side-text">
      <div className="h-16 flex items-center px-5 shrink-0"><Logo dark /></div>
      <nav className="flex-1 overflow-y-auto px-3 pb-4">
        {NAV.map((g) => {
          const items = g.items.filter((i) => !i.show || i.show(user));
          if (!items.length) return null;
          return (
            <div key={g.group} className="mt-4 first:mt-1">
              <div className="px-2.5 mb-1 text-[10.5px] font-semibold uppercase tracking-[0.09em] text-side-muted/80">{g.group}</div>
              {items.map((i) => (
                <NavLink key={i.to} to={i.to} end={i.to === "/app"} onClick={onNavigate}
                  className={({ isActive }) => clsx(
                    "group flex items-center gap-2.5 px-2.5 h-9 rounded-lg text-[13px] transition-colors relative",
                    isActive ? "bg-white/[0.08] text-white" : "text-side-text/75 hover:text-white hover:bg-white/[0.05]")}>
                  {({ isActive }) => (
                    <>
                      {isActive && <span className="absolute -left-3 top-2 bottom-2 w-[3px] rounded-r bg-[#2dd4bf]" />}
                      <i.icon size={16} strokeWidth={1.9} className={isActive ? "text-[#5eead4]" : "text-side-muted group-hover:text-side-text"} />
                      {i.label}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          );
        })}
      </nav>
      <div className="m-3 rounded-xl bg-white/[0.06] ring-1 ring-white/[0.06] p-3 text-[12px] leading-5">
        <div className="flex items-center gap-2 text-white font-medium"><Smartphone size={14} className="text-[#5eead4]" /> Agent app</div>
        <p className="text-side-muted mt-1">Field agents sign in on their phone. It keeps working offline.</p>
        <div className="flex gap-3 mt-1.5">
          <a href="/agent" target="_blank" rel="noreferrer" className="text-[#5eead4] hover:underline">Open /agent ↗</a>
          <button onClick={() => setQr(true)} className="text-[#5eead4] hover:underline">Phone QR</button>
        </div>
      </div>
      <Modal open={qr} onClose={() => setQr(false)} title="Open the agent app on a phone" sub="Phone must be on the same Wi-Fi as this laptop." width={380}>
        <div className="flex flex-col items-center text-center">
          <QrImage url={phone} size={220} />
          <div className="font-mono text-[12px] mt-3 break-all text-ink">{phone}</div>
          {phone.startsWith("https://") && <p className="text-[12.5px] text-muted mt-2 leading-5">The certificate is self-signed for this laptop. On the phone tap <b>Advanced → Proceed</b> once; GPS and voice notes then work.</p>}
        </div>
      </Modal>
    </div>
  );
}

export function Shell() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [mobileNav, setMobileNav] = useState(false);
  const [menu, setMenu] = useState(false);
  const toast = useToast();
  useLive((e) => {
    if (e.type === "payment.confirmed") toast({ kind: "ok", title: `Payment confirmed · ${e.account_no}`, body: `₹${Number(e.amount).toLocaleString("en-IN")} · receipt ${e.receipt_no}` });
    if (e.type === "ptp.broken") toast({ kind: "warn", title: `Promise broken · ${e.account_no}`, body: "Next action applied automatically" });
  });
  useEffect(() => { setMobileNav(false); setMenu(false); }, [loc.pathname]);
  if (!user) return null;
  const initials = user.name.split(" ").map((p) => p[0]).slice(0, 2).join("");
  return (
    <div className="min-h-screen lg:pl-[248px]">
      <aside className="hidden lg:block fixed inset-y-0 left-0 w-[248px] z-30"><Sidebar /></aside>
      {mobileNav && (
        <div className="lg:hidden fixed inset-0 z-[1300]">
          <div className="absolute inset-0 bg-black/40 animate-fade" onClick={() => setMobileNav(false)} />
          <div className="absolute inset-y-0 left-0 w-[264px] animate-slideIn shadow-pop">
            <Sidebar onNavigate={() => setMobileNav(false)} />
            <button className="absolute top-4 right-3 text-side-text/70" onClick={() => setMobileNav(false)} aria-label="Close menu"><X size={18} /></button>
          </div>
        </div>
      )}
      <header className="sticky top-0 z-20 h-14 bg-canvas/85 backdrop-blur-md border-b border-line flex items-center gap-3 px-4 sm:px-6">
        <button className="lg:hidden btn-ghost h-8 w-8 px-0" onClick={() => setMobileNav(true)} aria-label="Menu"><Menu size={18} /></button>
        <div className="text-[13px] text-muted truncate hidden sm:block">
          <span className="text-ink font-medium">Sahyadri Finance</span>
          <span className="mx-2 text-faint">/</span>
          {user.branch ?? (user.role === "l1" ? "Region" : "All branches")}
        </div>
        <div className="flex-1" />
        <LiveDot />
        <DemoClock />
        <ThemeSwitch />
        <div className="relative">
          <button onClick={() => setMenu((m) => !m)} className="flex items-center gap-2 h-9 pl-1 pr-2 rounded-lg hover:bg-sunken transition">
            <span className="h-7 w-7 rounded-full bg-brand-soft text-brand-ink text-[11.5px] font-semibold flex items-center justify-center">{initials}</span>
            <span className="hidden md:block text-left leading-4">
              <span className="block text-[12.5px] font-medium">{user.name}</span>
              <span className="block text-[11px] text-muted">{user.role_label}</span>
            </span>
            <ChevronsUpDown size={14} className="text-faint" />
          </button>
          {menu && (
            <div className="absolute right-0 mt-2 w-56 card shadow-pop p-1.5 z-50 animate-rise">
              <div className="px-2.5 py-2 text-[12px] text-muted border-b border-line mb-1">{user.email}</div>
              <a className="flex items-center gap-2 px-2.5 h-8 rounded-md text-[13px] hover:bg-sunken" href="/api/docs" target="_blank" rel="noreferrer"><Activity size={14} /> API docs</a>
              <button className="w-full flex items-center gap-2 px-2.5 h-8 rounded-md text-[13px] hover:bg-sunken text-bad"
                onClick={() => { logout(); nav("/login"); }}><LogOut size={14} /> Sign out</button>
            </div>
          )}
        </div>
      </header>
      <main key={loc.pathname} className="page-enter px-4 sm:px-6 lg:px-8 py-6 max-w-[1320px] mx-auto">
        <Outlet />
      </main>
    </div>
  );
}

export function RoleGate({ allow, children }: { allow: (u: any) => boolean; children: ReactNode }) {
  const { user } = useAuth();
  if (!allow(user)) {
    return (
      <div className="card p-10 text-center">
        <ShieldCheck className="mx-auto text-muted" />
        <div className="mt-3 font-medium">Your role can't open this page</div>
        <p className="text-[13px] text-muted mt-1">Least-privilege access: ask an administrator if you need it.</p>
      </div>
    );
  }
  return <>{children}</>;
}

export { Bell };
