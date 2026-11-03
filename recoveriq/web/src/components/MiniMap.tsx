import L from "leaflet";
import { useEffect } from "react";
import { Circle, CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { useColors } from "../lib/colors";
import { useIsDark } from "../lib/theme";

export function Tiles() {
  const dark = useIsDark();
  // Standard OpenStreetMap tiles (no key). Dark mode re-tints the same tiles with a CSS filter.
  return (
    <TileLayer key={dark ? "d" : "l"} className={dark ? "tiles-dark" : "tiles-light"}
      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      subdomains="abc" maxZoom={19} />
  );
}

function Fit({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1) map.fitBounds(L.latLngBounds(points).pad(0.35), { maxZoom: 16 });
    else if (points.length === 1) map.setView(points[0], 15);
  }, [JSON.stringify(points)]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export function CaseMap({ home, visits }: { home: [number, number]; visits: { lat: number; lng: number; verification: string; device_ts: string }[] }) {
  const c = useColors();
  const col = (v: string) => (v === "verified" ? c.ok : v === "low_conf" ? c.warn : c.bad);
  return (
    <MapContainer center={home} zoom={15} scrollWheelZoom={false} className="h-[220px] rounded-lg z-0">
      <Tiles />
      <Fit points={[home, ...visits.map((v) => [v.lat, v.lng] as [number, number])]} />
      <Circle center={home} radius={300} pathOptions={{ color: c.brand, weight: 1, fillOpacity: 0.06, dashArray: "4 4" }} />
      <CircleMarker center={home} radius={7} pathOptions={{ color: "#fff", weight: 2, fillColor: c.ink, fillOpacity: 1 }}>
        <Tooltip>Borrower address · 300 m verification radius</Tooltip>
      </CircleMarker>
      {visits.map((v, i) => (
        <CircleMarker key={i} center={[v.lat, v.lng]} radius={6} pathOptions={{ color: "#fff", weight: 2, fillColor: col(v.verification), fillOpacity: 1 }}>
          <Tooltip>{v.verification.replace("_", " ")} · {new Date(v.device_ts).toLocaleString("en-IN")}</Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
