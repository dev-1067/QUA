import clsx from "clsx";
import L from "leaflet";
import { ChevronRight, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { GeoJSON, MapContainer, useMap } from "react-leaflet";
import { Link } from "react-router-dom";
import { SentimentPill } from "../components/badges";
import { Card, PageHeader, Skeleton } from "../components/ui";
import { useColors } from "../lib/colors";
import { ago, LANG, pct } from "../lib/format";
import { useApi, useLive } from "../lib/hooks";

const NAME_FIX: Record<string, string> = { "NCT of Delhi": "Delhi" };
const norm = (n: string) => NAME_FIX[n] ?? n;

function mix(a: number[], b: number[], t: number) { return a.map((x, i) => Math.round(x + (b[i] - x) * t)); }
function moodColor(avg: number) {
  const red = [200, 54, 54], amber = [226, 160, 52], green = [34, 139, 84];
  const t = (avg + 1) / 2;
  const rgb = t < 0.5 ? mix(red, amber, t * 2) : mix(amber, green, (t - 0.5) * 2);
  return `rgb(${rgb.join(",")})`;
}

function Fit({ geo }: { geo: any }) {
  const map = useMap();
  useEffect(() => { if (geo) map.fitBounds(L.geoJSON(geo).getBounds(), { padding: [10, 10] }); }, [geo, map]);
  return null;
}

export default function Sentiment() {
  const [state, setState] = useState<string | null>(null);
  const states = useApi<any>("/dashboards/sentiment?level=state");
  const cities = useApi<any>(state ? `/dashboards/sentiment?level=city&state=${encodeURIComponent(state)}` : null, [state]);
  const borrowers = useApi<any>(state ? `/dashboards/sentiment?level=borrower&state=${encodeURIComponent(state)}` : null, [state]);
  const [geo, setGeo] = useState<any>(null);
  const [hover, setHover] = useState<string | null>(null);
  const c = useColors();
  useEffect(() => { fetch("/india-states.geojson").then((r) => r.json()).then(setGeo).catch(() => setGeo(null)); }, []);
  useLive((e) => { if (e.type === "sentiment.updated") { states.reload(true); if (state) { cities.reload(true); borrowers.reload(true); } } });

  const byState = useMemo(() => Object.fromEntries((states.data?.items ?? []).map((s: any) => [s.key, s])), [states.data]);
  const style = (f: any) => {
    const s = byState[norm(f.properties.ST_NM)];
    const sel = state === norm(f.properties.ST_NM);
    return {
      fillColor: s ? moodColor(s.avg) : c.sunken, fillOpacity: s ? (sel ? 0.95 : 0.78) : 1,
      color: sel ? c.ink : c.line, weight: sel ? 2 : 0.8,
    };
  };
  const focus = state ? byState[state] : null;
  const hov = hover ? byState[hover] : null;

  return (
    <>
      <PageHeader title="Borrower sentiment" sub="Each agent note, typed or spoken in Hindi, Marathi or English, is classified for mood and reason. Rolled up by state, city and borrower so managers can see where hardship is building."
        actions={state && <button className="btn-secondary" onClick={() => setState(null)}><X size={14} /> All India</button>} />
      <div className="grid xl:grid-cols-[1.15fr_1fr] gap-4">
        <div className="card p-3 relative">
          <div className="h-[560px] rounded-lg overflow-hidden">
            {geo ? (
              <MapContainer center={[22.5, 80]} zoom={4.5} zoomSnap={0.25} scrollWheelZoom={false} attributionControl={false} className="h-full w-full z-0 !bg-transparent">
                <Fit geo={geo} />
                <GeoJSON key={JSON.stringify(Object.keys(byState)) + state + c.ink} data={geo} style={style as any}
                  onEachFeature={(f, layer) => {
                    const n = norm(f.properties.ST_NM);
                    layer.on({ click: () => byState[n] && setState(n), mouseover: () => setHover(n), mouseout: () => setHover(null) });
                  }} />
              </MapContainer>
            ) : <Skeleton className="h-full" />}
          </div>
          <div className="absolute left-6 top-6 card px-3 py-2.5 text-[12px] shadow-pop min-w-[200px] pointer-events-none">
            {hov ? (
              <>
                <div className="font-medium text-[13px]">{hover}</div>
                <div className="text-muted mt-0.5">{pct(hov.positive_pct, 0)} positive repayment mood · n = {hov.notes}</div>
                <div className="text-muted">Top reason: {hov.top_reasons[0]?.label}</div>
              </>
            ) : <div className="text-muted">{hover ? `${hover}: no notes yet` : "Hover a state · click to drill in"}</div>}
          </div>
          <div className="absolute right-6 bottom-6 card px-3 py-2 text-[11.5px] shadow-pop">
            <div className="h-2 w-40 rounded-full" style={{ background: `linear-gradient(90deg, ${moodColor(-1)}, ${moodColor(0)}, ${moodColor(1)})` }} />
            <div className="flex justify-between mt-1 text-muted"><span>Negative</span><span>Positive</span></div>
          </div>
        </div>

        <div className="space-y-4 min-w-0">
          {!state ? (
            <Card title="States" sub={`${states.data?.total_notes ?? "…"} notes analysed`} pad={false}>
              <ul className="divide-y divide-line max-h-[300px] overflow-y-auto">
                {(states.data?.items ?? []).map((s: any) => (
                  <li key={s.key} onClick={() => setState(s.key)} className="px-5 py-2.5 flex items-center gap-3 cursor-pointer hover:bg-sunken">
                    <span className="h-3 w-3 rounded-sm shrink-0" style={{ background: moodColor(s.avg) }} />
                    <span className="flex-1 text-[13.5px]">{s.key}</span>
                    <span className="text-[12px] text-muted num w-28 text-right">{pct(s.positive_pct, 0)} positive</span>
                    <span className="text-[12px] text-faint num w-12 text-right">n={s.notes}</span>
                    <ChevronRight size={14} className="text-faint" />
                  </li>
                ))}
              </ul>
            </Card>
          ) : (
            <Card title={state} sub={focus ? `${pct(focus.positive_pct, 0)} positive · ${pct(focus.negative_pct, 0)} negative · ${focus.notes} notes` : ""}>
              <div className="label mb-2">Cities</div>
              <div className="space-y-2">
                {(cities.data?.items ?? []).map((ci: any) => (
                  <div key={ci.key} className="flex items-center gap-3 text-[13px]">
                    <span className="w-28 truncate">{ci.key}</span>
                    <div className="flex-1 h-2 rounded-full overflow-hidden flex bg-sunken">
                      <div className="bg-ok/80" style={{ width: `${ci.positive_pct * 100}%` }} />
                      <div className="bg-faint/40" style={{ width: `${(1 - ci.positive_pct - ci.negative_pct) * 100}%` }} />
                      <div className="bg-bad/80" style={{ width: `${ci.negative_pct * 100}%` }} />
                    </div>
                    <span className="text-faint num w-12 text-right">n={ci.notes}</span>
                  </div>
                ))}
              </div>
              <div className="label mt-5 mb-2">Borrowers</div>
              <ul className="divide-y divide-line max-h-[200px] overflow-y-auto -mx-5">
                {(borrowers.data?.items ?? []).slice(0, 60).map((b: any) => (
                  <li key={b.key} className="px-5 py-2 flex items-center gap-2 text-[13px]">
                    <Link to={`/app/cases/${b.key}`} className="font-mono text-[12px] text-brand hover:underline">{b.account_no}</Link>
                    <span className="text-muted truncate flex-1">{b.label} · {b.city}</span>
                    <span className="text-[12px] text-muted">{b.top_reasons[0]?.label}</span>
                    <SentimentPill s={b.avg >= 0.2 ? "positive" : b.avg <= -0.2 ? "negative" : "neutral"} />
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card title="Why borrowers are behind" sub={state ? `In ${state}` : "All notes in your scope"}>
            {(() => {
              const src = state ? (focus?.top_reasons ?? []) : (states.data?.reasons ?? []);
              const max = Math.max(1, ...src.map((r: any) => r.n));
              return (
                <div className="space-y-2">
                  {src.map((r: any) => (
                    <div key={r.code} className="grid grid-cols-[150px_1fr_40px] items-center gap-3 text-[13px]">
                      <span className="truncate">{r.label}</span>
                      <div className="h-2 rounded-full bg-sunken overflow-hidden"><div className={clsx("h-full rounded-full", r.code === "will_pay" ? "bg-ok/80" : r.code === "willful_default" ? "bg-bad/80" : "bg-brand/60")} style={{ width: `${(r.n / max) * 100}%` }} /></div>
                      <span className="text-right num text-muted">{r.n}</span>
                    </div>
                  ))}
                </div>
              );
            })()}
          </Card>

          <Card title="Latest notes" pad={false}>
            <ul className="divide-y divide-line max-h-[260px] overflow-y-auto">
              {(states.data?.recent ?? []).map((n: any) => (
                <li key={n.id} className="px-5 py-3">
                  <div className="flex items-center gap-2 text-[12px] text-muted">
                    <SentimentPill s={n.sentiment} /> <span>{n.reason}</span> <span>· {n.city} · {LANG[n.language]}</span>
                    <span className="ml-auto text-faint">{ago(n.ts)}</span>
                  </div>
                  <Link to={`/app/cases/${n.case_id}`} className="block text-[13.5px] mt-1 hover:text-brand">{n.text}</Link>
                  {n.language !== "en" && n.english_text && <div className="text-[12.5px] text-muted">{n.english_text}</div>}
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
