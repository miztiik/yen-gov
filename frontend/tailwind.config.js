/** @type {import("tailwindcss").Config} */
//
// yen-gov Tailwind config (CLAUDE.md doctrine + plan section 21.7 + 23.5).
//
// theme.extend mirrors the CSS custom properties declared in
// frontend/src/app-tokens.css so every utility resolves to a var(--...).
// Mirror is ADDITIVE per section 23.5: no Tailwind default (slate-*
// ramp, sm/md/lg radius, sans font-family, transition-duration keys) is
// REDEFINED here. Components migrate to the new tokens progressively
// across U2..U5; until then, un-migrated code keeps its old-but-
// consistent look. The app is never half-broken.
//
// Drift gate: frontend/src/contracts/app-tokens.test.ts asserts every
// --var in app-tokens.css has at least one mirror here, and every
// mirror value here references an existing --var.
//
export default {
  content: ["./index.html", "./src/**/*.{svelte,ts,js}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--ink)",
        "ink-muted": "var(--ink-muted)",
        line: "var(--line)",
        surface: "var(--surface)",
        "surface-sunken": "var(--surface-sunken)",
        accent: "var(--accent)",
        pos: "var(--pos)",
        caution: "var(--caution)",
        neg: "var(--neg)",
        "brand-saffron": "var(--brand-saffron)",
        "brand-green": "var(--brand-green)",
        "brand-chakra": "var(--brand-chakra)",
        "app-bar-bg": "var(--app-bar-bg)",
      },
      fontFamily: {
        "yen-sans": ["var(--font-sans)"],
        "yen-display": ["var(--font-display)"],
        "yen-deva": ["var(--font-deva)"],
      },
      borderRadius: {
        "yen-sm": "var(--r-sm)",
        "yen-md": "var(--r-md)",
        "yen-lg": "var(--r-lg)",
        "yen-pill": "var(--r-pill)",
      },
      boxShadow: {
        e1: "var(--e1)",
        e2: "var(--e2)",
        e3: "var(--e3)",
      },
      transitionDuration: {
        fast: "var(--dur-fast)",
        slow: "var(--dur-slow)",
      },
      transitionTimingFunction: {
        "yen-out": "var(--ease-out)",
        "yen-spring": "var(--ease-spring)",
      },
    },
  },
  plugins: [],
};
