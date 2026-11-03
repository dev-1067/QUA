import { useEffect, useState } from "react";

export type ThemePref = "light" | "system" | "dark";

function apply(pref: ThemePref) {
  const dark = pref === "dark" || (pref === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  window.dispatchEvent(new Event("riq-theme"));
}

export function useTheme() {
  const [pref, setPref] = useState<ThemePref>(() => {
    try { return (localStorage.getItem("riq-theme") as ThemePref) || "system"; } catch { return "system"; }
  });
  useEffect(() => {
    apply(pref);
    try { localStorage.setItem("riq-theme", pref); } catch { /* ignore */ }
    if (pref !== "system") return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const fn = () => apply("system");
    mq.addEventListener("change", fn);
    return () => mq.removeEventListener("change", fn);
  }, [pref]);
  return [pref, setPref] as const;
}

export function useIsDark() {
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme === "dark");
  useEffect(() => {
    const fn = () => setDark(document.documentElement.dataset.theme === "dark");
    window.addEventListener("riq-theme", fn);
    return () => window.removeEventListener("riq-theme", fn);
  }, []);
  return dark;
}
