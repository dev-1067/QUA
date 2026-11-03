import Dexie, { type Table } from "dexie";
import { useEffect, useState } from "react";
import { api, session } from "../lib/api";

export type Op = {
  client_id: string; type: "visit" | "call" | "note" | "ptp" | "dispute"; case_id: string; data: any;
  created_at: string; status: "pending" | "rejected"; error?: string; audio?: Blob | null; label: string;
};

class AgentDB extends Dexie {
  worklist!: Table<any, string>;
  outbox!: Table<Op, string>;
  meta!: Table<{ key: string; value: any }, string>;
  constructor() {
    super("riq-agent");
    this.version(1).stores({ worklist: "id", outbox: "client_id, created_at", meta: "key" });
  }
}
export const db = new AgentDB();

const SIM = "riq-sim-offline";
export const simOffline = {
  get: () => { try { return localStorage.getItem(SIM) === "1"; } catch { return false; } },
  set: (v: boolean) => { try { localStorage.setItem(SIM, v ? "1" : "0"); } catch { /* ignore */ } window.dispatchEvent(new Event("riq-net")); },
};
export const isOnline = () => navigator.onLine && !simOffline.get();

export function useOnline() {
  const [on, setOn] = useState(isOnline());
  useEffect(() => {
    const f = () => setOn(isOnline());
    window.addEventListener("online", f); window.addEventListener("offline", f); window.addEventListener("riq-net", f);
    return () => { window.removeEventListener("online", f); window.removeEventListener("offline", f); window.removeEventListener("riq-net", f); };
  }, []);
  return on;
}

const bus = new EventTarget();
export const onStoreChange = (fn: () => void) => { bus.addEventListener("change", fn); return () => bus.removeEventListener("change", fn); };
const changed = () => bus.dispatchEvent(new Event("change"));

export async function enqueue(op: Omit<Op, "created_at" | "status">) {
  await db.outbox.put({ ...op, created_at: new Date().toISOString(), status: "pending" });
  changed();
  if (isOnline()) flush().catch(() => {});
}

let flushing: Promise<SyncResult> | null = null;
export type SyncResult = { applied: number; duplicates: number; rejected: number; pulled: boolean; error?: string };

export function flush(): Promise<SyncResult> {
  flushing ??= (async () => {
    const res: SyncResult = { applied: 0, duplicates: 0, rejected: 0, pulled: false };
    if (!isOnline() || !session.get()) return res;
    try {
      const ops = (await db.outbox.toArray()).filter((o) => o.status === "pending")
        .sort((a, b) => a.created_at.localeCompare(b.created_at));
      // voice notes go through the multipart endpoint (same client_id → idempotent)
      for (const op of ops.filter((o) => o.type === "note" && o.audio)) {
        const fd = new FormData();
        fd.append("client_id", op.client_id); fd.append("text", op.data.text); fd.append("language", op.data.language);
        fd.append("device_ts", op.data.device_ts); fd.append("audio", op.audio!, "note.webm");
        const s = session.get();
        const r = await fetch(`/api/v1/cases/${op.case_id}/notes/audio`, { method: "POST", body: fd, headers: s ? { Authorization: `Bearer ${s.access_token}` } : {} });
        if (r.ok) { await db.outbox.delete(op.client_id); res.applied++; }
        else if (r.status >= 400 && r.status < 500 && r.status !== 401) {
          const b = await r.json().catch(() => null);
          await db.outbox.update(op.client_id, { status: "rejected", error: b?.detail ?? `HTTP ${r.status}` }); res.rejected++;
        }
      }
      const rest = ops.filter((o) => !(o.type === "note" && o.audio));
      if (rest.length) {
        const out = await api<any>("/sync/push", { method: "POST", json: { ops: rest.map((o) => ({ client_id: o.client_id, type: o.type, case_id: o.case_id, data: o.data })) } });
        for (const r of out.results) {
          if (r.status === "applied" || r.status === "duplicate") {
            await db.outbox.delete(r.client_id);
            r.status === "applied" ? res.applied++ : res.duplicates++;
          } else {
            await db.outbox.update(r.client_id, { status: "rejected", error: r.error });
            res.rejected++;
          }
        }
      }
      const wl = await api<any>("/agent/worklist");
      await db.transaction("rw", db.worklist, db.meta, async () => {
        await db.worklist.clear();
        await db.worklist.bulkPut(wl.items);
        await db.meta.put({ key: "stats", value: wl.stats });
        await db.meta.put({ key: "last_sync", value: new Date().toISOString() });
      });
      res.pulled = true;
    } catch (e: any) {
      res.error = e.message;
    } finally {
      changed();
    }
    return res;
  })().finally(() => { setTimeout(() => (flushing = null), 0); });
  return flushing;
}

export function useStore() {
  const [state, setState] = useState<{ items: any[]; outbox: Op[]; stats: any; lastSync: string | null; ready: boolean }>({ items: [], outbox: [], stats: null, lastSync: null, ready: false });
  useEffect(() => {
    const load = async () => {
      const [items, outbox, stats, last] = await Promise.all([db.worklist.toArray(), db.outbox.toArray(), db.meta.get("stats"), db.meta.get("last_sync")]);
      items.sort((a, b) => b.priority - a.priority);
      setState({ items, outbox: outbox.sort((a, b) => a.created_at.localeCompare(b.created_at)), stats: stats?.value ?? null, lastSync: last?.value ?? null, ready: true });
    };
    load();
    return onStoreChange(load);
  }, []);
  return state;
}

export async function patchLocal(id: string, patch: any) {
  await db.worklist.update(id, patch);
  changed();
}

export async function clearAgentData() {
  await Promise.all([db.worklist.clear(), db.outbox.clear(), db.meta.clear()]);
  changed();
}
