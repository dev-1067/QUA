import clsx from "clsx";
import { CheckCircle2, Download, FileSpreadsheet, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { Card, Empty, PageHeader, Spinner, useToast } from "../components/ui";
import { ApiError, openFile, session } from "../lib/api";
import { dt, num } from "../lib/format";
import { useApi } from "../lib/hooks";

const COLS = ["account_no*", "borrower_name*", "phone*", "email", "address", "pincode*", "city", "state", "lat", "lng", "loan_type", "principal",
  "emi_amount*", "outstanding*", "dpd*", "missed_emis", "last_payment_date", "preferred_language"];

export default function Intake() {
  const { data: jobs, reload } = useApi<any[]>("/intake/jobs");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const input = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const upload = async (file?: File | null) => {
    if (!file) return;
    setBusy(true);
    setResult(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const s = session.get();
      const r = await fetch("/api/v1/intake/upload", { method: "POST", body: fd, headers: s ? { Authorization: `Bearer ${s.access_token}` } : {} });
      const body = await r.json().catch(() => null);
      if (!r.ok) throw new ApiError(r.status, body?.detail ?? "Upload failed");
      setResult(body);
      toast({ kind: "ok", title: `Imported ${file.name}`, body: `${body.created} created · ${body.updated} updated · ${body.unchanged} unchanged · ${body.rejected} rejected` });
      reload(true);
    } catch (e: any) {
      toast({ kind: "err", title: "Upload failed", body: e.message });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  };

  return (
    <>
      <PageHeader title="Case intake" sub="Upload the overdue export from your core lending system. Each account number maps to exactly one case, so re-uploading a file updates cases and never duplicates them."
        actions={<button className="btn-secondary" onClick={() => openFile("/intake/sample.csv")}><Download size={15} /> Sample CSV</button>} />

      <div className="grid lg:grid-cols-[1fr_360px] gap-4">
        <div className="space-y-4">
          <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files?.[0]); }}
            onClick={() => !busy && input.current?.click()}
            className={clsx("card border-dashed border-2 cursor-pointer transition-all px-6 py-12 text-center",
              drag ? "border-brand bg-brand-soft/50 scale-[1.005]" : "border-line-strong hover:border-brand/50 hover:bg-sunken/40")}>
            <input ref={input} type="file" accept=".csv,.xlsx" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
            <div className="mx-auto h-12 w-12 rounded-xl bg-brand-soft text-brand flex items-center justify-center">
              {busy ? <Spinner size={22} /> : <UploadCloud size={22} />}
            </div>
            <div className="mt-4 text-[15px] font-medium">{busy ? "Validating, de-duplicating and scoring…" : "Drop a CSV or Excel file here"}</div>
            <div className="text-[13px] text-muted mt-1">or click to choose · up to 15 MB · rows are validated one by one</div>
          </div>

          {result && (
            <Card title={<span className="flex items-center gap-2"><CheckCircle2 size={16} className="text-ok" /> {result.filename}</span>} sub={`Processed ${num(result.total_rows)} rows`}>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 stagger">
                {[["Created", result.created, "text-ok"], ["Updated", result.updated, "text-info"], ["Unchanged", result.unchanged, "text-muted"], ["Rejected", result.rejected, "text-bad"]].map(([k, v, t]) => (
                  <div key={k as string} className="rounded-lg bg-sunken/60 px-3 py-2.5">
                    <div className="label">{k}</div><div className={clsx("text-[22px] font-semibold num", t as string)}>{v}</div>
                  </div>
                ))}
              </div>
              {result.created === 0 && result.unchanged > 0 && (
                <p className="mt-3 text-[13px] text-ok">No duplicates created: every account already had its case.</p>
              )}
              {result.errors?.length > 0 && (
                <div className="mt-4">
                  <div className="label mb-2">Rejected rows</div>
                  <div className="rounded-lg border border-line divide-y divide-line max-h-56 overflow-y-auto">
                    {result.errors.map((e: any) => (
                      <div key={e.row} className="px-3 py-2 text-[12.5px]"><span className="font-mono text-muted">row {e.row}</span> {e.account_no && <span className="font-mono">· {e.account_no}</span>} <span className="text-bad">· {e.errors.join("; ")}</span></div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          )}

          <Card title="Import history" pad={false}>
            {!jobs?.length ? <Empty icon={<FileSpreadsheet size={18} />} title="No uploads yet" body="The seeded portfolio was loaded by the system at start-up." /> : (
              <div className="overflow-x-auto"><table className="table">
                <thead><tr><th>File</th><th>When</th><th className="text-right">Rows</th><th className="text-right">Created</th><th className="text-right">Updated</th><th className="text-right">Unchanged</th><th className="text-right">Rejected</th></tr></thead>
                <tbody>{jobs.map((j) => (
                  <tr key={j.id}><td className="font-medium">{j.filename}</td><td className="text-muted whitespace-nowrap">{dt(j.created_at)}</td>
                    <td className="text-right num">{j.total_rows}</td><td className="text-right num text-ok">{j.created}</td><td className="text-right num">{j.updated}</td>
                    <td className="text-right num text-muted">{j.unchanged}</td><td className="text-right num text-bad">{j.rejected}</td></tr>))}
                </tbody></table></div>
            )}
          </Card>
        </div>

        <Card title="File format" sub="Header row required. * marks mandatory columns.">
          <div className="flex flex-wrap gap-1.5">
            {COLS.map((c) => <span key={c} className={clsx("kbd", c.endsWith("*") && "text-ink border-line-strong")}>{c}</span>)}
          </div>
          <ul className="mt-4 space-y-2 text-[12.5px] text-muted leading-5 list-disc pl-4">
            <li>Phones are normalised to +91 format; invalid numbers are rejected with the row number.</li>
            <li>loan_type: personal, two_wheeler, gold, msme, consumer_durable.</li>
            <li>Missing lat/lng are approximated from the branch and flagged.</li>
            <li>Rows are routed to the branch by pincode, scored, sent to a channel and auto-allocated.</li>
            <li>Names, phones, emails and addresses are encrypted at rest (AES-GCM).</li>
          </ul>
        </Card>
      </div>
    </>
  );
}
