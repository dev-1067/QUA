import { useMemo } from "react";
import { useIsDark } from "./theme";

const TOKENS = ["brand", "field", "tele", "digital", "ok", "warn", "bad", "info", "ink", "muted", "faint", "line", "surface", "sunken"] as const;
type Tok = (typeof TOKENS)[number];

/** Resolved theme colours for charts/maps (SVG attributes can't read CSS variables reliably). */
export function useColors(): Record<Tok, string> & { alpha: (t: Tok, a: number) => string } {
  const dark = useIsDark();
  return useMemo(() => {
    const cs = getComputedStyle(document.documentElement);
    const raw: Record<string, string> = {};
    TOKENS.forEach((t) => (raw[t] = cs.getPropertyValue(`--${t}`).trim().replace(/\s+/g, ",")));
    const out: any = {};
    TOKENS.forEach((t) => (out[t] = `rgb(${raw[t]})`));
    out.alpha = (t: Tok, a: number) => `rgba(${raw[t]},${a})`;
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dark]);
}
