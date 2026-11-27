/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Architectural Alabaster & Stone Surfaces
        background: "#f4f6f8",
        "on-background": "#0b1320",
        surface: "#f4f6f8",
        "surface-bright": "#f9fafb",
        "surface-dim": "#dfe5ec",
        "surface-variant": "#d5dde6",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#edf1f5",
        "surface-container": "#e6ecf2",
        "surface-container-high": "#dce4ec",
        "surface-container-highest": "#d1dce7",
        "on-surface": "#0b1320",
        "on-surface-variant": "#475569",
        "inverse-surface": "#0f2342",
        "inverse-on-surface": "#f4f6f8",
        outline: "#64748b",
        "outline-variant": "#d5dde6",
        "surface-tint": "#334e68",

        // Deep Maritime Oxford Navy (Primary Brand Anchor)
        primary: "#0f2342",
        "on-primary": "#ffffff",
        "primary-container": "#162e54",
        "on-primary-container": "#e2eaf6",
        "inverse-primary": "#93b4f0",
        "primary-fixed": "#1e40af",
        "primary-fixed-dim": "#3b5fc0",
        "on-primary-fixed": "#ffffff",
        "on-primary-fixed-variant": "#dbeafe",

        // Steel Slate & Warm Ochre Amber (Drift / Pending Caution)
        secondary: "#334e68",
        "on-secondary": "#ffffff",
        "secondary-container": "#dbeafe",
        "on-secondary-container": "#1e3a8a",
        "secondary-fixed": "#fef3c7",
        "secondary-fixed-dim": "#fde68a",
        "on-secondary-fixed": "#92400e",
        "on-secondary-fixed-variant": "#78350f",

        // Deep Forest Emerald (Compliance, Growth, HITL Approval)
        tertiary: "#065f46",
        "on-tertiary": "#ffffff",
        "tertiary-container": "#065f46",
        "on-tertiary-container": "#047857",
        "tertiary-fixed": "#d1fae5",
        "tertiary-fixed-dim": "#a7f3d0",
        "on-tertiary-fixed": "#064e3b",
        "on-tertiary-fixed-variant": "#047857",

        // Oxblood Crimson (Violations, Rejections, Sell / Danger)
        error: "#b91c1c",
        "on-error": "#ffffff",
        "error-container": "#fee2e2",
        "on-error-container": "#991b1b"
      },
      borderRadius: {
        sm: "0.25rem",
        DEFAULT: "0.5rem",
        md: "0.5rem",
        lg: "0.625rem",
        xl: "0.75rem",
        full: "9999px"
      },
      spacing: {
        "margin-mobile": "16px",
        "margin-desktop": "32px",
        unit: "4px",
        xs: "4px",
        sm: "8px",
        md: "16px",
        lg: "24px",
        xl: "32px",
        gutter: "24px"
      },
      fontFamily: {
        // Strict 2-font pairing: Newsreader (editorial display) + Geist (UI & tabular numbers)
        display: ["Newsreader", "Georgia", "serif"],
        sans: ["Geist", "system-ui", "-apple-system", "sans-serif"],
        "display-lg": ["Newsreader", "Georgia", "serif"],
        "headline-md": ["Geist", "system-ui", "sans-serif"],
        "headline-lg-mobile": ["Newsreader", "Georgia", "serif"],
        "title-sm": ["Geist", "system-ui", "sans-serif"],
        "body-base": ["Geist", "system-ui", "sans-serif"],
        "body-mono": ["Geist", "system-ui", "sans-serif"],
        "label-caps": ["Geist", "system-ui", "sans-serif"]
      },
      fontSize: {
        // 3 strict body sizes (+ exempt display sizes for brand, h1, hero net worth)
        meta: ["0.8125rem", { lineHeight: "1.45" }],
        body: ["0.9375rem", { lineHeight: "1.55" }],
        heading: ["1.125rem", { lineHeight: "1.35", letterSpacing: "-0.015em" }],
        brand: ["1.25rem", { lineHeight: "1.2", letterSpacing: "-0.02em" }],
        "page-title": ["clamp(1.75rem, 2.5vw, 2.25rem)", { lineHeight: "1.15", letterSpacing: "-0.025em" }],
        "display-figure": ["clamp(2.125rem, 3.4vw, 3rem)", { lineHeight: "1.06", letterSpacing: "-0.03em" }],

        // Backwards-compatible aliases mapped strictly onto the 3-size + display scale
        "label-caps": ["0.8125rem", { lineHeight: "1.45" }],
        "body-mono": ["0.9375rem", { lineHeight: "1.5" }],
        "body-base": ["0.9375rem", { lineHeight: "1.55" }],
        "title-sm": ["1.125rem", { lineHeight: "1.35", letterSpacing: "-0.015em" }],
        "headline-sm": ["1.125rem", { lineHeight: "1.35", letterSpacing: "-0.015em" }],
        "headline-md": ["1.125rem", { lineHeight: "1.35", letterSpacing: "-0.015em" }],
        "headline-lg-mobile": ["clamp(1.75rem, 2.5vw, 2.25rem)", { lineHeight: "1.15", letterSpacing: "-0.025em" }],
        "display-lg": ["clamp(2.125rem, 3.4vw, 3rem)", { lineHeight: "1.06", letterSpacing: "-0.03em" }]
      },
      boxShadow: {
        sheet: "0 1px 2px rgba(11, 19, 32, 0.04)",
        "nav-scrolled": "0 4px 16px rgba(11, 19, 32, 0.06)"
      },
      transitionTimingFunction: {
        desk: "cubic-bezier(0.22, 1, 0.36, 1)"
      }
    }
  },
  plugins: [],
};
