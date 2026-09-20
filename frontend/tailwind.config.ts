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
        "kept-tint": "var(--kept-tint)",
        caution: "var(--caution)",
        "caution-tint": "var(--caution-tint)",
        surface: "var(--surface)",
        "cat-food": "var(--cat-food)",
        "cat-packaging": "var(--cat-packaging)",
        "cat-equipment": "var(--cat-equipment)",
        "cat-ewaste": "var(--cat-ewaste)",
        "cat-other": "var(--cat-other)",
      },
      fontFamily: {
        sans: "var(--font-plex-sans), system-ui, sans-serif",
        condensed: "var(--font-plex-condensed), var(--font-plex-sans), system-ui, sans-serif",
      },
      // Sizes are variables so one media query in tokens.css moves the whole
      // scale up a step on the laptop layout without touching a single class.
      fontSize: {
        figure: ["var(--size-figure)", { lineHeight: "var(--line-figure)", fontWeight: "600" }],
        total: ["var(--size-total)", { lineHeight: "var(--line-total)", fontWeight: "600" }],
        title: ["var(--size-title)", { lineHeight: "var(--line-title)", fontWeight: "600" }],
        section: ["var(--size-section)", { lineHeight: "var(--line-section)", fontWeight: "600" }],
        body: ["var(--size-body)", { lineHeight: "var(--line-body)", fontWeight: "400" }],
        caption: ["var(--size-caption)", { lineHeight: "var(--line-caption)", fontWeight: "400" }],
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
        ticket: "var(--ticket-w)",
        drawer: "420px",
        row: "var(--row-h)",
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
