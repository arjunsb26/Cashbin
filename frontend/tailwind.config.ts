import type { Config } from "tailwindcss";

// Every value here points at a CSS variable defined in app/tokens.css.
// That file is the only place a raw colour literal is allowed to live.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "var(--paper)",
        bar: "var(--bar)",
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        rule: "var(--rule)",
        "control-border": "var(--control-border)",
        "red-ink": "var(--red-ink)",
        kept: "var(--kept)",
        caution: "var(--caution)",
        surface: "var(--surface)",
      },
      fontFamily: {
        sans: "var(--font-plex-sans), system-ui, sans-serif",
        condensed: "var(--font-plex-condensed), var(--font-plex-sans), system-ui, sans-serif",
      },
      fontSize: {
        figure: ["56px", { lineHeight: "56px", fontWeight: "600" }],
        total: ["28px", { lineHeight: "32px", fontWeight: "600" }],
        title: ["20px", { lineHeight: "28px", fontWeight: "600" }],
        section: ["15px", { lineHeight: "22px", fontWeight: "600" }],
        body: ["14px", { lineHeight: "20px", fontWeight: "400" }],
        caption: ["12.5px", { lineHeight: "18px", fontWeight: "400" }],
      },
      borderRadius: {
        control: "6px",
        ticket: "2px",
      },
      boxShadow: {
        ticket: "0 1px 0 var(--rule), 0 8px 24px var(--shadow-ticket)",
        overlay: "0 12px 40px var(--shadow-overlay)",
      },
      spacing: {
        rail: "76px",
        ticket: "560px",
        drawer: "420px",
        row: "36px",
      },
      transitionTimingFunction: {
        standard: "var(--ease)",
      },
      transitionDuration: {
        fast: "120ms",
        move: "240ms",
        count: "400ms",
      },
      keyframes: {
        "ticket-in": {
          from: { transform: "translateY(-12px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "drawer-in": {
          from: { transform: "translateX(16px)", opacity: "0" },
          to: { transform: "translateX(0)", opacity: "1" },
        },
        "skeleton-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
      },
      animation: {
        "ticket-in": "ticket-in 240ms var(--ease) both",
        "fade-in": "fade-in 160ms var(--ease) both",
        "drawer-in": "drawer-in 240ms var(--ease) both",
        skeleton: "skeleton-pulse 1800ms var(--ease) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
