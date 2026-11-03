import { useCallback, useEffect, useRef, useState } from "react";
import { api, session } from "./api";

export function useApi<T = any>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const seq = useRef(0);
  const load = useCallback(async (quiet = false) => {
    if (!path) return;
    const id = ++seq.current;
    if (!quiet) setLoading(true);
    try {
      const d = await api<T>(path);
      if (id === seq.current) { setData(d); setError(null); }
    } catch (e: any) {
      if (id === seq.current) setError(e.message);
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, [path]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load, ...deps]);
  return { data, error, loading, reload: load, setData };
}

type Handler = (evt: any) => void;
const handlers = new Set<Handler>();
let socket: WebSocket | null = null;
let retry = 0;
let ping: number | undefined;
const statusListeners = new Set<(on: boolean) => void>();

function connect() {
  const s = session.get();
  if (!s || socket) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/api/v1/ws?token=${encodeURIComponent(s.access_token)}`);
  socket = ws;
  ws.onopen = () => {
    retry = 0;
    statusListeners.forEach((f) => f(true));
    ping = window.setInterval(() => ws.readyState === 1 && ws.send("ping"), 25000);
  };
  ws.onmessage = (m) => {
    try { const e = JSON.parse(m.data); if (e.type !== "pong") handlers.forEach((h) => h(e)); } catch { /* ignore */ }
  };
  ws.onclose = () => {
    socket = null;
    clearInterval(ping);
    statusListeners.forEach((f) => f(false));
    if (handlers.size && session.get()) setTimeout(connect, Math.min(15000, 1000 * 2 ** retry++));
  };
}

export function useLive(handler: Handler) {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const h: Handler = (e) => ref.current(e);
    handlers.add(h);
    connect();
    return () => { handlers.delete(h); };
  }, []);
}

export function useLiveStatus() {
  const [on, setOn] = useState(socket?.readyState === 1);
  useEffect(() => { statusListeners.add(setOn); return () => { statusListeners.delete(setOn); }; }, []);
  return on;
}

export function resetLive() {
  try { socket?.close(); } catch { /* ignore */ }
  socket = null;
}

export function useNow(ms = 30000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), ms); return () => clearInterval(t); }, [ms]);
  return now;
}

export function useDebounced<T>(value: T, ms = 300) {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}
