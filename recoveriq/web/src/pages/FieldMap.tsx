import clsx from "clsx";
import L from "leaflet";
import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, useMap } from "react-leaflet";
import { Link } from "react-router-dom";
import { VerificationPill } from "../components/badges";
import { Tiles } from "../components/MiniMap";
import { Card, PageHeader, Segmented } from "../components/ui";
import { useColors } from "../lib/colors";
import { ago, titleCase } from "../lib/format";
import { useApi, useLive, useNow } from "../lib/hooks";

function FitAll({ pts, focus }: { pts: [number, number][]; focus: [number, number] | null }) {
  const map = useMap();
  useEffect(() => { if (pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.15), { maxZoom: 13 }); }, [pts.length]); // eslint-disable-line
  useEffect(() => { if (focus) map.flyTo(focus, 15, { duration: 0.8 }); }, [focus, map]);
  return null;
}

export default function FieldMap() {
  const [hours, setHours] = useState<"24" | "168" | "720">("168");
  const { data, reload } = useApi<any>(`/dashboards/field?hours=${hours}`);
  const c = useColors();
  const now = useNow(15000);
  const [fresh, setFresh] = useState<any[]>([]);
  const [focus, setFocus] = useState<[number, number] | null>(null);
  const [filter, setFilter] = useState<string>("all");
  useLive((e) => {
    if (e.type !== "field.checkin") return;
    setFresh((f) => [{ ...e, id: e.case_id + e.ts, account_no: e.account_no, agent: e.agent_name, ts: e.ts, live: true }, ...f].slice(0, 30));
    setFocus([e.lat, e.lng]);
  });
  const visits = useMemo(() => [...fresh, ...(data?.visits ?? [])].filter((v) => filter === "all" || v.verification === filter), [fresh, data, filter]);
  const pts = useMemo(() => (data?.visits ?? []).map((v: any) => [v.lat, v.lng] as [number, number]), [data]);
  const col = (v: string) => (v === "verified" ? c.ok : v === "low_conf" ? c.warn : c.bad);
  const counts = (data?.visits ?? []).reduce((m: any, v: any) => ({ ...m, [v.verification]: (m[v.verification] || 0) + 1 }), {});

  return (
    <>
      <PageHeader title="Live field map" sub="Every check-in carries device GPS, accuracy and a server timestamp. Visits more than 300 m from the address, with poor accuracy, or with impossible travel speed are flagged."
        actions={<Segmented value={hours} onChange={(v) => { setHours(v); setFresh([]); }} items={[{ id: "24", label: "24 h" }, { id: "168", label: "7 days" }, { id: "720", label: "30 days" }]} />} />
      <div className="grid xl:grid-cols-[1fr_340px] gap-4">
        <div className="card overflow-hidden h-[620px] relative">
          <MapContainer center={[20.5, 78.9]} zoom={5} className="h-full w-full z-0">
            <Tiles />
            <FitAll pts={pts} focus={focus} />
            {visits.map((v: any) => (
              <CircleMarker key={v.id} center={[v.lat, v.lng]} radius={v.live ? 9 : 5}
                pathOptions={{ color: v.live ? "#fff" : col(v.verification), weight: v.live ? 3 : 1, fillColor: col(v.verification), fillOpacity: v.live ? 1 : 0.7 }}>
                <Popup>
                  <div className="font-medium">{v.account_no}</div>
                  <div>{v.agent} · {titleCase(v.outcome)}</div>
                  <div style={{ color: col(v.verification) }}>{String(v.verification).replace("_", " ")}{v.distance_m != null && ` · ${Math.round(v.distance_m)} m from address`}</div>
                  <Link to={`/app/cases/${v.case_id}`}>Open case →</Link>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
          <div className="absolute left-3 bottom-3 z-[500] card px-3 py-2 text-[12px] flex gap-3 shadow-pop">
            {[["verified", "Verified"], ["flagged", "Flagged"], ["low_conf", "Low accuracy"]].map(([k, l]) => (
              <span key={k} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: col(k) }} />{l} <span className="text-muted num">{counts[k] ?? 0}</span></span>
            ))}
          </div>
        </div>
        <Card title="Check-ins" sub={fresh.length ? `${fresh.length} live this session` : "Newest first"} pad={false}
          actions={<select className="select w-auto h-8 text-[12px]" value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All</option><option value="verified">Verified</option><option value="flagged">Flagged</option><option value="low_conf">Low accuracy</option>
          </select>}>
          <ul className="max-h-[560px] overflow-y-auto divide-y divide-line">
            {visits.slice(0, 120).map((v: any) => (
              <li key={v.id} onClick={() => setFocus([v.lat, v.lng])} className={clsx("px-4 py-2.5 cursor-pointer hover:bg-sunken", v.live && "bg-brand-soft/40 animate-slideIn")}>
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[12.5px] font-medium">{v.account_no}</span>
                  <span className="text-[11.5px] text-faint">{ago(v.ts, now)}</span>
                </div>
                <div className="text-[12.5px] text-muted flex items-center justify-between gap-2 mt-0.5">
                  <span className="truncate">{v.agent} · {titleCase(v.outcome)}</span>
                  <VerificationPill v={v.verification} />
                </div>
              </li>
            ))}
            {data && !visits.length && <li className="p-6 text-center text-[13px] text-muted">No check-ins in this window.</li>}
          </ul>
          <div className="px-4 py-2.5 border-t border-line text-[12px] text-muted"><button className="hover:text-ink" onClick={() => reload()}>Refresh</button></div>
        </Card>
      </div>
    </>
  );
}
