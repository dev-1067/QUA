import clsx from "clsx";
import { Ban, Mail, MessageCircle, MessageSquareText } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Card, Empty, PageHeader, Segmented, Skeleton } from "../components/ui";
import { useApi, useLive } from "../lib/hooks";

const ICON: Record<string, any> = { sms: MessageSquareText, whatsapp: MessageCircle, email: Mail };

export default function Notifications() {
  const [channel, setChannel] = useState<"" | "sms" | "whatsapp" | "email">("");
  const [status, setStatus] = useState<"" | "delivered" | "blocked">("");
  const q = new URLSearchParams({ limit: "120" });
  if (channel) q.set("channel", channel);
  if (status) q.set("status", status);
  const { data, loading, reload } = useApi<any[]>(`/notifications?${q}`);
  useLive((e) => { if (["contact.nudge", "contact.blocked"].includes(e.type)) reload(true); });

  return (
    <>
      <PageHeader title="Message outbox"
        sub="Every SMS, WhatsApp and email the system sends or refuses to send. Real bulk SMS in India needs TRAI DLT registration, so this prototype delivers to this outbox instead of a carrier, with the exact text the borrower would get."
        actions={<>
          <Segmented value={channel} onChange={setChannel} items={[{ id: "", label: "All" }, { id: "sms", label: "SMS" }, { id: "whatsapp", label: "WhatsApp" }, { id: "email", label: "Email" }]} />
          <Segmented value={status} onChange={setStatus} items={[{ id: "", label: "Any" }, { id: "delivered", label: "Delivered" }, { id: "blocked", label: "Blocked" }]} />
        </>} />
      <Card pad={false}>
        {loading && !data ? <div className="p-5"><Skeleton className="h-60" /></div> : !data?.length ? <Empty title="No messages match" /> : (
          <ul className="divide-y divide-line">
            {data.map((m) => {
              const I = ICON[m.channel] ?? MessageSquareText;
              const blocked = m.status === "blocked";
              return (
                <li key={m.id} className="px-5 py-3.5 flex gap-4">
                  <div className={clsx("h-9 w-9 rounded-full flex items-center justify-center shrink-0", blocked ? "bg-warn/10 text-warn" : "bg-digital/10 text-digital")}>
                    {blocked ? <Ban size={16} /> : <I size={16} />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px]">
                      <Link to={`/app/cases/${m.case_id}`} className="font-mono font-medium text-brand hover:underline">{m.account_no}</Link>
                      <span className="text-muted">{m.borrower} · {m.recipient}</span>
                      <span className="chip bg-sunken text-muted uppercase">{m.channel}{m.language ? ` · ${m.language}` : ""}</span>
                      {m.status === "sent" && <span className="chip bg-ok/10 text-ok">real send ✓</span>}
                      {m.status === "failed" && <span className="chip bg-bad/10 text-bad">real send failed</span>}
                      <span className="ml-auto text-faint num">{m.ts_local}</span>
                    </div>
                    {blocked ? (
                      <div className="mt-1.5 text-[13px] text-warn">{m.block_reason}</div>
                    ) : (
                      <div className={clsx("mt-2 inline-block max-w-[560px] rounded-2xl rounded-tl-sm px-3.5 py-2 text-[13.5px] leading-6",
                        m.channel === "whatsapp" ? "bg-[#dcf8c6] text-[#111b21] dark:bg-[#005c4b] dark:text-[#e9edef]" : "bg-sunken")}>{m.body}</div>
                    )}
                    {m.status === "failed" && m.block_reason && <div className="mt-1 text-[12px] text-bad">{m.block_reason}</div>}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </>
  );
}
