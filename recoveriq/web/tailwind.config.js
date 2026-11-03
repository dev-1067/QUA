/** @type {import('tailwindcss').Config} */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        canvas: v("canvas"), surface: v("surface"), sunken: v("sunken"), line: v("line"), "line-strong": v("line-strong"),
        ink: v("ink"), muted: v("muted"), faint: v("faint"),
        brand: { DEFAULT: v("brand"), strong: v("brand-strong"), soft: v("brand-soft"), ink: v("brand-ink") },
        side: { DEFAULT: v("side"), 2: v("side-2"), text: v("side-text"), muted: v("side-muted"), hover: v("side-hover") },
        field: v("field"), tele: v("tele"), digital: v("digital"),
        ok: v("ok"), warn: v("warn"), bad: v("bad"), info: v("info"),
      },
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 0 rgb(var(--line) / 0.6), 0 1px 2px rgb(16 24 20 / 0.04)",
        pop: "0 12px 32px -8px rgb(16 24 20 / 0.22), 0 2px 6px rgb(16 24 20 / 0.08)",
      },
      keyframes: {
        rise: { "0%": { opacity: 0, transform: "translateY(6px)" }, "100%": { opacity: 1, transform: "none" } },
        fade: { "0%": { opacity: 0 }, "100%": { opacity: 1 } },
        pulseRing: { "0%": { transform: "scale(.6)", opacity: .7 }, "100%": { transform: "scale(2.4)", opacity: 0 } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
        slideIn: { "0%": { transform: "translateX(24px)", opacity: 0 }, "100%": { transform: "none", opacity: 1 } },
        sheet: { "0%": { transform: "translateY(100%)" }, "100%": { transform: "none" } },
      },
      animation: {
        rise: "rise .35s cubic-bezier(.2,.7,.2,1) both", fade: "fade .25s ease both",
        ring: "pulseRing 1.6s ease-out infinite", slideIn: "slideIn .3s cubic-bezier(.2,.7,.2,1) both",
        sheet: "sheet .32s cubic-bezier(.2,.8,.2,1) both",
      },
    },
  },
  plugins: [],
};
