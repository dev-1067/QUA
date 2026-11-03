import { Check, Copy, ExternalLink, Wifi } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { useApi } from "../lib/hooks";
import { inr } from "../lib/format";

/** URL a phone on the same Wi-Fi can open. Prefers the https listener (needed for GPS and the
 * microphone on phones); null when the app is already opened on a non-local address. */
export function phoneUrl(meta: any, path: string): string | null {
  const local = ["localhost", "127.0.0.1"].includes(location.hostname);
  const ip = meta?.lan_ips?.[0];
  if (!local || !ip) return null;
  return meta.https_port ? `https://${ip}:${meta.https_port}${path}` : `${location.protocol}//${ip}:${location.port || 80}${path}`;
}

export function QrImage({ url, size = 220 }: { url: string; size?: number }) {
  const [img, setImg] = useState("");
  useEffect(() => { QRCode.toDataURL(url, { margin: 1, width: size * 2, color: { dark: "#10201b", light: "#ffffff" } }).then(setImg).catch(() => setImg("")); }, [url, size]);
  return img ? <img src={img} alt="QR code" style={{ width: size, height: size }} className="rounded-lg bg-white p-1.5 ring-1 ring-line" /> : <div className="skeleton" style={{ width: size, height: size }} />;
}

/** QR + link for a borrower payment link. When the app is opened on localhost the QR points at the
 * laptop's LAN address instead, so a phone on the same Wi-Fi can scan and pay. */
export function PayLinkCard({ link }: { link: { path: string; amount: number; gateway: string; gateway_link_id: string } }) {
  const { data: meta } = useApi<any>("/meta");
  const lan = phoneUrl(meta, link.path);
  const url = lan ?? `${location.origin}${link.path}`;
  const [img, setImg] = useState<string>("");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    QRCode.toDataURL(url, { margin: 1, width: 360, color: { dark: "#10201b", light: "#ffffff" } }).then(setImg).catch(() => setImg(""));
  }, [url]);
  const copy = async () => {
    try { await navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 1600); } catch { /* ignore */ }
  };
  return (
    <div className="rounded-xl border border-line bg-sunken/40 p-4 animate-rise">
      <div className="flex gap-4 items-center">
        {img ? <img src={img} alt="Payment QR code" className="h-[132px] w-[132px] rounded-lg bg-white p-1.5 ring-1 ring-line shrink-0" />
          : <div className="h-[132px] w-[132px] skeleton shrink-0" />}
        <div className="min-w-0 text-[12.5px]">
          <div className="label">Scan to pay</div>
          <div className="text-[20px] font-semibold num mt-0.5">{inr(link.amount)}</div>
          <div className="text-muted mt-1 leading-5">Gateway: <span className="font-medium text-ink capitalize">{link.gateway}</span> (test mode)</div>
          <div className="font-mono text-[11px] text-faint truncate">{link.gateway_link_id}</div>
          {lan && <div className="mt-1.5 flex items-center gap-1 text-[11.5px] text-muted"><Wifi size={12} /> QR opens on a phone on the same Wi-Fi{meta?.https_port ? " (https)" : ""}</div>}
        </div>
      </div>
      <div className="flex gap-2 mt-3">
        <input readOnly value={url} className="input h-8 text-[12px] font-mono" onFocus={(e) => e.target.select()} />
        <button className="btn-secondary btn-sm" onClick={copy}>{copied ? <Check size={14} /> : <Copy size={14} />}</button>
        <a className="btn-secondary btn-sm" href={link.path} target="_blank" rel="noreferrer" title="Open borrower page"><ExternalLink size={14} /></a>
      </div>
    </div>
  );
}
