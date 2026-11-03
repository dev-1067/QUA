import { Gavel } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, Empty, Field, Modal, PageHeader, Segmented, Skeleton, Spinner, Tabs, useAction } from "../components/ui";
import { api } from "../lib/api";
import { dt, inr, titleCase } from "../lib/format";
import { useApi } from "../lib/hooks";

export default function Disputes() {
  const [tab, setTab] = useState<"open" | "resolved" | "rejected">("open");
  const { data, loading, reload } = useApi<any[]>(`/disputes?status=${tab}`);
  const [sel, setSel] = useState<any>(null);
  const [outcome, setOutcome] = useState<"resolved" | "rejected">("resolved");
  const [text, setText] = useState("");
  const [adjust, setAdjust] = useState("");
  const { busy, run } = useAction();

  return (
    <>
      <PageHeader title="Disputes" sub="Raised from the field or the branch. Nudges pause automatically while a dispute is open, and each category routes to its owner queue." />
      <Card pad={false}>
        <div className="px-3"><Tabs value={tab} onChange={setTab} items={[{ id: "open", label: "Open" }, { id: "resolved", label: "Resolved" }, { id: "rejected", label: "Rejected" }]} /></div>
        {loading && !data ? <div className="p-5"><Skeleton className="h-32" /></div> : !data?.length ? <Empty icon={<Gavel size={18} />} title={`No ${tab} disputes`} /> : (
          <div className="divide-y divide-line">
            {data.map((d) => (
              <div key={d.id} className="px-5 py-4 flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 max-w-2xl">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link to={`/app/cases/${d.case_id}`} className="font-mono text-[13px] font-medium text-brand hover:underline">{d.account_no}</Link>
                    <span className="chip bg-warn/10 text-warn">{titleCase(d.category)}</span>
                    <span className="chip bg-sunken text-muted">queue: {d.owner_queue}</span>
                  </div>
                  <p className="text-[13.5px] mt-1.5">{d.description || <span className="text-muted">No description</span>}</p>
                  <div className="text-[12px] text-muted mt-1">{d.borrower} · raised by {d.raised_by ?? "—"} · {dt(d.created_at)} · overdue {inr(d.amount_due)}</div>
                  {d.resolution && <div className="text-[12.5px] mt-2 rounded-lg bg-sunken px-3 py-2"><span className="font-medium capitalize">{d.status}:</span> {d.resolution}</div>}
                </div>
                {tab === "open" && <button className="btn-secondary btn-sm" onClick={() => { setSel(d); setText(""); setAdjust(""); setOutcome("resolved"); }}>Resolve</button>}
              </div>
            ))}
          </div>
        )}
      </Card>
      <Modal open={!!sel} onClose={() => setSel(null)} title={`Close dispute · ${sel?.account_no ?? ""}`} sub="The case returns to its working channel and contact resumes."
        footer={<><button className="btn-ghost" onClick={() => setSel(null)}>Cancel</button>
          <button className="btn-primary" disabled={text.trim().length < 4 || !!busy}
            onClick={() => run("r", () => api(`/disputes/${sel.id}/resolve`, { method: "POST", json: { outcome, resolution: text, adjust_amount_due: adjust ? Number(adjust) : null } }), "Dispute closed").then((r) => { if (r) { setSel(null); reload(true); } })}>
            {busy ? <Spinner /> : "Close dispute"}</button></>}>
        <Segmented value={outcome} onChange={setOutcome} items={[{ id: "resolved", label: "Resolved in borrower's favour" }, { id: "rejected", label: "Rejected" }]} />
        <div className="space-y-3 mt-4">
          <Field label="Resolution note"><textarea className="input" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Cash receipt verified; ₹3,000 credited" /></Field>
          {outcome === "resolved" && <Field label="Correct overdue amount (optional)" hint={sel ? `Current overdue ${inr(sel.amount_due)}` : ""}><input className="input" type="number" min={0} value={adjust} onChange={(e) => setAdjust(e.target.value)} /></Field>}
        </div>
      </Modal>
    </>
  );
}
