import clsx from "clsx";
import { AlertTriangle, CheckCircle2, Info, Loader2, X, XCircle } from "lucide-react";
import {
  createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode,
} from "react";
import { createPortal } from "react-dom";

/* ------------------------------------------------------------------ toast */
type Toast = { id: number; kind: "ok" | "err" | "info" | "warn"; title: string; body?: string };
const ToastCtx = createContext<(t: Omit<Toast, "id">) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((t: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs.slice(-3), { ...t, id }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), t.kind === "err" ? 6500 : 4200);
  }, []);
  const icon = { ok: CheckCircle2, err: XCircle, info: Info, warn: AlertTriangle };
  const tone = { ok: "text-ok", err: "text-bad", info: "text-info", warn: "text-warn" };
  return (
    <ToastCtx.Provider value={push}>
      {children}
      {createPortal(
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[2000] flex flex-col gap-2 w-[min(420px,calc(100vw-32px))] pointer-events-none">
          {items.map((t) => {
            const I = icon[t.kind];
            return (
              <div key={t.id} className="pointer-events-auto animate-rise flex gap-3 items-start rounded-xl bg-[#17201d] text-[#eef2ef] px-4 py-3 shadow-pop ring-1 ring-black/10">
                <I size={18} className={clsx("mt-0.5 shrink-0", tone[t.kind], "brightness-150")} />
                <div className="min-w-0">
                  <div className="text-[13.5px] font-medium leading-5">{t.title}</div>
                  {t.body && <div className="text-[12.5px] text-white/65 mt-0.5 leading-5 break-words">{t.body}</div>}
                </div>
              </div>
            );
          })}
        </div>,
        document.body,
      )}
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

/* ------------------------------------------------------------------ async button */
export function useAction() {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const run = useCallback(async <T,>(key: string, fn: () => Promise<T>, ok?: string | ((r: T) => string | null)) => {
    setBusy(key);
    try {
      const r = await fn();
      const msg = typeof ok === "function" ? ok(r) : ok;
      if (msg) toast({ kind: "ok", title: msg });
      return r;
    } catch (e: any) {
      toast({ kind: "err", title: "That didn't work", body: e.message });
      return undefined;
    } finally {
      setBusy(null);
    }
  }, [toast]);
  return { busy, run };
}

export function Spinner({ size = 15, className }: { size?: number; className?: string }) {
  return <Loader2 size={size} className={clsx("animate-spin", className)} />;
}

/* ------------------------------------------------------------------ layout pieces */
export function PageHeader({ title, sub, actions, crumb }: { title: ReactNode; sub?: ReactNode; actions?: ReactNode; crumb?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
      <div className="min-w-0">
        {crumb && <div className="text-[12.5px] text-muted mb-1.5">{crumb}</div>}
        <h1 className="text-[22px] font-semibold leading-tight text-ink">{title}</h1>
        {sub && <p className="text-[13.5px] text-muted mt-1 max-w-2xl">{sub}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Card({ title, sub, actions, children, className, pad = true }: {
  title?: ReactNode; sub?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; pad?: boolean;
}) {
  return (
    <section className={clsx("card", className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 px-5 pt-4 pb-3">
          <div className="min-w-0">
            {title && <h2 className="text-[14px] font-semibold text-ink">{title}</h2>}
            {sub && <p className="text-[12.5px] text-muted mt-0.5">{sub}</p>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </header>
      )}
      <div className={clsx(pad && (title ? "px-5 pb-5" : "p-5"))}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, hint, tone, icon }: { label: string; value: ReactNode; hint?: ReactNode; tone?: string; icon?: ReactNode }) {
  return (
    <div className="card px-4 py-3.5 min-w-0">
      <div className="flex items-center justify-between gap-2">
        <span className="label truncate">{label}</span>
        {icon && <span className="text-faint">{icon}</span>}
      </div>
      <div className={clsx("mt-1.5 text-[22px] font-semibold num tracking-tight leading-7", tone)}>{value}</div>
      {hint && <div className="text-[12px] text-muted mt-0.5 truncate">{hint}</div>}
    </div>
  );
}

export function Empty({ icon, title, body, action }: { icon?: ReactNode; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      {icon && <div className="h-11 w-11 rounded-full bg-sunken flex items-center justify-center text-muted mb-3">{icon}</div>}
      <div className="text-[14px] font-medium">{title}</div>
      {body && <div className="text-[13px] text-muted mt-1 max-w-sm">{body}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBox({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="card p-5 flex items-center gap-3 border-bad/30">
      <XCircle className="text-bad shrink-0" size={18} />
      <div className="text-[13px] flex-1">{message}</div>
      {retry && <button className="btn-secondary btn-sm" onClick={retry}>Try again</button>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton", className)} />;
}

export function Tabs<T extends string>({ value, onChange, items }: { value: T; onChange: (v: T) => void; items: { id: T; label: ReactNode; count?: number }[] }) {
  return (
    <div className="flex gap-1 border-b border-line overflow-x-auto">
      {items.map((it) => (
        <button key={it.id} onClick={() => onChange(it.id)}
          className={clsx("relative px-3 py-2.5 text-[13px] font-medium whitespace-nowrap transition-colors",
            value === it.id ? "text-ink" : "text-muted hover:text-ink")}>
          {it.label}
          {it.count != null && <span className="ml-1.5 text-[11px] text-faint num">{it.count}</span>}
          {value === it.id && <span className="absolute left-2 right-2 -bottom-px h-[2px] rounded-full bg-brand" />}
        </button>
      ))}
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, items, size = "md" }: {
  value: T; onChange: (v: T) => void; items: { id: T; label: ReactNode }[]; size?: "sm" | "md";
}) {
  return (
    <div className="inline-flex p-0.5 rounded-lg bg-sunken border border-line">
      {items.map((it) => (
        <button key={it.id} onClick={() => onChange(it.id)}
          className={clsx("rounded-md font-medium transition-all", size === "sm" ? "px-2 py-1 text-[12px]" : "px-3 py-1.5 text-[12.5px]",
            value === it.id ? "bg-surface text-ink shadow-sm ring-1 ring-line" : "text-muted hover:text-ink")}>
          {it.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ overlays */
export function Modal({ open, onClose, title, sub, children, footer, width = 480 }: {
  open: boolean; onClose: () => void; title: ReactNode; sub?: ReactNode; children: ReactNode; footer?: ReactNode; width?: number;
}) {
  useEffect(() => {
    if (!open) return;
    const fn = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, [open, onClose]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[1500] flex items-end sm:items-center justify-center p-0 sm:p-6">
      <div className="absolute inset-0 bg-[#0b1210]/45 backdrop-blur-[2px] animate-fade" onClick={onClose} />
      <div className="relative w-full bg-surface sm:rounded-2xl rounded-t-2xl shadow-pop border border-line animate-rise max-h-[92vh] flex flex-col"
        style={{ maxWidth: width }} role="dialog" aria-modal>
        <div className="flex items-start justify-between gap-4 px-5 pt-5 pb-3">
          <div>
            <h3 className="text-[16px] font-semibold">{title}</h3>
            {sub && <p className="text-[13px] text-muted mt-1">{sub}</p>}
          </div>
          <button className="btn-ghost h-8 w-8 px-0 -mr-1.5 -mt-1" onClick={onClose} aria-label="Close"><X size={17} /></button>
        </div>
        <div className="px-5 pb-5 overflow-y-auto">{children}</div>
        {footer && <div className="px-5 py-3.5 border-t border-line flex justify-end gap-2 bg-sunken/40 sm:rounded-b-2xl">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}

export function Drawer({ open, onClose, title, children, width = 520 }: {
  open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; width?: number;
}) {
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[1400]">
      <div className="absolute inset-0 bg-[#0b1210]/35 animate-fade" onClick={onClose} />
      <aside className="absolute right-0 top-0 bottom-0 bg-surface border-l border-line shadow-pop animate-slideIn flex flex-col w-full" style={{ maxWidth: width }}>
        <div className="flex items-center justify-between px-5 h-14 border-b border-line shrink-0">
          <div className="font-semibold text-[15px]">{title}</div>
          <button className="btn-ghost h-8 w-8 px-0" onClick={onClose} aria-label="Close"><X size={17} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </aside>
    </div>,
    document.body,
  );
}

export function Field({ label, hint, children, error, group }: { label: string; hint?: ReactNode; children: ReactNode; error?: string | null; group?: boolean }) {
  // button groups must not sit inside a <label> (the label would forward clicks to the first button)
  const Tag = group ? "div" : "label";
  return (
    <Tag className="block">
      <span className="block text-[12.5px] font-medium text-ink mb-1.5">{label}</span>
      {children}
      {error ? <span className="block text-[12px] text-bad mt-1">{error}</span> : hint ? <span className="block text-[12px] text-muted mt-1">{hint}</span> : null}
    </Tag>
  );
}

/* ------------------------------------------------------------------ count-up number */
export function CountUp({ value, format = (v: number) => v.toFixed(0), ms = 700 }: { value: number; format?: (v: number) => string; ms?: number }) {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    const start = performance.now();
    const a = from.current;
    let raf = 0;
    const step = (t: number) => {
      const p = Math.min(1, (t - start) / ms);
      const e = 1 - Math.pow(1 - p, 3);
      setShown(a + (value - a) * e);
      if (p < 1) raf = requestAnimationFrame(step);
      else from.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return <>{format(shown)}</>;
}
