# Design system - tokens, fonts, Devanagari shaping, ADDITIVE rule

**Last Updated**: 2026-06-05

The yen-gov design system distilled out of U1 (PRs #714, #716, #718, plan section 21.7 + 23.5) and extended by U2 (PRs #739, #742, #745, plan section 21.8). It is one CSS-token layer + a Tailwind mirror + three self-hosted variable-font subsets + a body cutover + a Devanagari shaping gate + a place-first breadcrumb spine, governed by ONE rule (additive-not-override) so component migration can happen progressively without ever leaving the app half-broken.

The colour system documented in [colours.md](colours.md) is layered ON TOP of these tokens (party-colour anchors + indicator ramps come from OkLCh and resolve via the `--accent` / `--pos` / `--caution` / `--neg` semantic colour tokens here). Read this file first for the chrome surface; read colours.md next for the data surface.

## Where it lives

| Surface | File | What it does |
| --- | --- | --- |
| CSS-side truth | [frontend/src/app-tokens.css](../../../frontend/src/app-tokens.css) | `:root` custom properties for colour / type / radius / elevation / motion |
| Tailwind mirror | [frontend/tailwind.config.js](../../../frontend/tailwind.config.js) | `theme.extend` resolves utility classes to `var(--token)` |
| Body cutover | [frontend/src/app.css](../../../frontend/src/app.css) | `@font-face` + `body { font-family + font-feature-settings }` + ballot-motif retone |
| Token import order | [frontend/src/main.ts](../../../frontend/src/main.ts) | imports `./app-tokens.css` BEFORE `./app.css` so every later rule may reference a token |
| Preload + CDN removal | [frontend/index.html](../../../frontend/index.html) | single Inter-Latin preload; Google-CDN `<link>` + two `preconnect`s removed |
| Self-hosted fonts | [frontend/public/fonts/](../../../frontend/public/fonts/) | `inter-latin.woff2` + `noto-sans-devanagari.woff2` + `outfit-latin.woff2` + `LICENCES.md` |
| Subset build script | [tools/build_fonts.py](../../../tools/build_fonts.py) | operator-only `fonttools subset` recipe |
| Drift contract | [frontend/src/contracts/app-tokens.test.ts](../../../frontend/src/contracts/app-tokens.test.ts) | vitest: tokens declared, every Tailwind `var()` resolves, every non-exempt `--var` mirrored |
| Devanagari gate | [frontend/e2e/devanagari-conjunct.spec.ts](../../../frontend/e2e/devanagari-conjunct.spec.ts) | Playwright: kSha conjunct width < KA + SSA pair width |

## Token map

The five token families, each declared once in `app-tokens.css` on `:root` and mirrored by name into `tailwind.config.js theme.extend`. Type-scale tokens, `--font-feature-tabular`, and `--dur` are intentionally exempt from a Tailwind mirror (see "Drift contract" below); every other token has at least one Tailwind utility that resolves through it.

| Family | CSS var | Tailwind mirror | Notes |
| --- | --- | --- | --- |
| Colour - chrome | `--ink` | `text-ink` / `bg-ink` | body text + dark chrome |
| | `--ink-muted` | `text-ink-muted` | secondary copy |
| | `--line` | `border-line` | 1px hairline |
| | `--surface` | `bg-surface` | card surface |
| | `--surface-sunken` | `bg-surface-sunken` | gutter / page background |
| | `--app-bar-bg` | `bg-app-bar-bg` | mobile glass app bar surface (white at 80% alpha; alpha BAKED IN, never compounded with Tailwind's `/<opacity>`) |
| | `--accent` | `text-accent` / `bg-accent` | chakra indigo brand accent (NOT saffron / green) |
| Colour - data direction | `--pos` | `text-pos` / `bg-pos` | "good" status |
| | `--caution` | `text-caution` / `bg-caution` | "caution" status |
| | `--neg` | `text-neg` / `bg-neg` | "bad" status |
| Colour - brand | `--brand-saffron` | `text-brand-saffron` / `bg-brand-saffron` | LeftRail wordmark (flag-derived saffron, WCAG-AA cousin of #FF9933) |
| | `--brand-green` | `text-brand-green` / `bg-brand-green` | LeftRail wordmark (flag-derived green, WCAG-AA cousin of #138808) |
| | `--brand-chakra` | `text-brand-chakra` / `bg-brand-chakra` | LeftRail wordmark (chakra navy) |
| Type - family | `--font-sans` | `font-yen-sans` | Inter then Noto Sans Devanagari then system fallbacks |
| | `--font-display` | `font-yen-display` | Outfit -> `--font-sans` |
| | `--font-deva` | `font-yen-deva` | "Noto Sans Devanagari" -> `--font-sans` |
| | `--font-feature-tabular` | (none; applied directly on `body`) | `"tnum" 1, "lnum" 1` |
| Type - scale | `--text-xs` .. `--text-4xl` | (none; matches Tailwind stock `text-*` ladder 1:1) | minor-third 1.2 at base 16px |
| Radius | `--r-sm` / `--r-md` / `--r-lg` / `--r-pill` | `rounded-yen-sm` / `-yen-md` / `-yen-lg` / `-yen-pill` | 6 / 10 / 14 / 9999 px |
| Elevation | `--e1` / `--e2` / `--e3` | `shadow-e1` / `-e2` / `-e3` | low-spread tinted shadows |
| Motion - duration | `--dur-fast` / `--dur` / `--dur-slow` | `duration-fast` / (none for `--dur`) / `duration-slow` | 120 / 200 / 320 ms |
| Motion - easing | `--ease-out` / `--ease-spring` | `ease-yen-out` / `ease-yen-spring` | cubic-bezier curves |

`@media (prefers-reduced-motion: reduce)` collapses every `--dur*` to 1ms inside `app-tokens.css` so per-component code does not re-test the media query.

## The ADDITIVE rule

The system ships under one constitutional constraint inherited from plan section 23.5:

> **No Tailwind default is REDEFINED.** Tailwind's stock `slate-*` ramp, `sm`/`md`/`lg` radius scale, `sans` font family, and `transitionDuration` keys are untouched. Components migrate to the new tokens progressively across U2..U5; until then, un-migrated code keeps its old-but-consistent look. The app is never half-broken.

Concretely:

- Colour mirrors use NEW semantic keys (`ink`, `accent`, `pos`, ...) instead of redefining `slate-*`.
- Radius mirrors use `yen-sm` / `yen-md` / `yen-lg` / `yen-pill` so `rounded-sm` keeps its stock 2px meaning until a component opts in.
- Font-family mirrors use `yen-sans` / `yen-display` / `yen-deva` so `font-sans` keeps its stock ui-sans-serif meaning until a component opts in.
- `transitionDuration` mirrors only `fast` and `slow`; the stock `DEFAULT` (150ms) is untouched so existing `transition` utilities do not globally shift.

This is what made U1.1 ship as ZERO visible change (the tokens are dormant until later chunks migrate components) and what lets U2..U5 land one component at a time.

## Self-hosted fonts

Three variable-axis woff2 subsets ship inside the static bundle per Holy Law #1, produced by [tools/build_fonts.py](../../../tools/build_fonts.py) and attributed in [frontend/public/fonts/LICENCES.md](../../../frontend/public/fonts/LICENCES.md):

- `inter-latin.woff2` (176 KB) - Inter v4.1, SIL OFL 1.1 - body + UI + data, Latin only.
- `noto-sans-devanagari.woff2` (178 KB) - Noto Sans Devanagari v2.006, SIL OFL 1.1 - Hindi / Marathi rendering.
- `outfit-latin.woff2` (25 KB) - Outfit, SIL OFL 1.1 - LeftRail wordmark only.

The single load-bearing recipe is:

```
fonttools subset INPUT.ttf \
    --output-file=OUTPUT.woff2 \
    --flavor=woff2 \
    --layout-features='*' \
    --name-IDs='*' \
    --glyph-names \
    --symbol-cmap --legacy-cmap \
    --notdef-glyph --notdef-outline --recommended-glyphs \
    --unicodes='<script range>'
```

`--layout-features='*'` is non-negotiable: it keeps the GSUB / GPOS shaping tables intact. A codepoint-only prune (a common copy-paste mistake when starting from an Inter recipe) silently strips Devanagari conjunct shaping and produces a font that "looks Hindi" to a Latin reviewer but lays out three atomic glyphs instead of one ligature to a Devanagari reader. The Devanagari gate below catches this.

Per `@font-face` block in [frontend/src/app.css](../../../frontend/src/app.css) the browser fetches each subset on demand by `unicode-range`: Devanagari is only downloaded when a U+0900-097F codepoint enters the layout tree (a state name in Hindi, a dataset label in Devanagari). Inter is preloaded (the one `<link rel="preload">` in `index.html`) because every route renders it on first paint.

The body cutover (U1.3) flips the `body` rule to read the design-token font stack and the tabular-numerals feature setting directly:

```css
body {
  font-family: var(--font-sans);
  font-feature-settings: var(--font-feature-tabular);
}
```

CSS inheritance does the rest: every chart axis, every table cell, every numeric column inherits tabular numerals automatically. Per-component `tabular-nums` Tailwind utility classes are defensive fallback, not the primary delivery mechanism. `--font-sans` lists "Noto Sans Devanagari" right after "Inter" so the browser's unicode-range matching routes Latin to Inter and Devanagari to Noto automatically; no per-component `font-family: var(--font-deva)` override is needed for mixed text.

## Devanagari shaping gate

[frontend/e2e/devanagari-conjunct.spec.ts](../../../frontend/e2e/devanagari-conjunct.spec.ts) is the runtime gate that proves the woff2 still ships GSUB. It loads `/` against the Vite dev server, injects two hidden spans at the same font-size against the same `font-family: "Noto Sans Devanagari", serif` stack, and measures their widths:

| Span | Codepoints | Rendered as | Width |
| --- | --- | --- | --- |
| A (conjunct) | KA (U+0915) + VIRAMA (U+094D) + SSA (U+0937) | one shaped ligature glyph (kSha) | narrow |
| B (pair) | KA (U+0915) + SSA (U+0937) | two atomic glyphs (no virama, never a ligature) | wider |

The invariant is `width(A) < width(B)`. It can only hold if the woff2's GSUB lookups are present and the browser is using them. A codepoint-only subset would render three atomic glyphs in span A and make A wider than B; the spec would fail at the `expect(widthConjunct).toBeLessThan(widthPair)` assertion. The spec also asserts the resolved font-family includes "Noto Sans Devanagari" so a 404 on the woff2 (silent fallback to serif) cannot accidentally satisfy the width ratio.

The same recipe applies to any future Indic-script subset (Tamil, Telugu, Bengali, Kannada, Malayalam): pick one shaping-load-bearing conjunct + measure it against its un-ligaturable component pair.

## Drift contract

[frontend/src/contracts/app-tokens.test.ts](../../../frontend/src/contracts/app-tokens.test.ts) runs in vitest and asserts three invariants:

1. The core token set is declared in `app-tokens.css` (colour 13 [9 chrome + glass + 3 brand] + type-family 4 + type-scale 8 + tabular-feature 1 + radius 4 + elevation 3 + motion 5 = 38 names).
2. Every `var(--...)` reference in `tailwind.config.js theme.extend` resolves to a `--var` that exists in `app-tokens.css` (no dangling references).
3. Every non-exempt `--var` declared in `app-tokens.css` has at least one Tailwind mirror referencing it.

The exempt set is documented inline in the test:

- `--text-xs` .. `--text-4xl`: Tailwind's stock `text-*` ladder already matches one-for-one.
- `--font-feature-tabular`: applied directly on `body`, not via a utility class.
- `--dur` (the default 200ms): redefining Tailwind's `duration-DEFAULT` would shift every transition globally; the ADDITIVE rule forbids that.

Per `/memories/lessons.md` the test uses RELATIVE imports (`node:fs` / `node:path` / `node:url`) because vitest does not resolve the `$lib` SvelteKit alias.

## Per-component migration

| Chunk | What migrates | Status |
| --- | --- | --- |
| U2 | LeftRail brand hex, breadcrumb chrome, drawer surfaces, glass app bar, district URL node | MERGED #739 + #742 + #745 |
| U3 | icon set under `frontend/public/icons/` + LICENCES.md | MERGED #736 |
| U4 | chart switcher chrome, axis colours | TODO |
| U5 | skeleton / loading states | TODO |

Each chunk replaces per-component literal hex / px / ms values with the matching `var(--token)` (or the matching Tailwind utility that resolves through one). The drift contract test does NOT block migrations - it blocks SILENT drift at the token layer.

### U2 - GeoBreadcrumb + glass app bar + district URL node (PRs #739 / #742 / #745)

U2 lifted the place-first primary-nav surface onto the token layer in three chunks. **U2a (#739)** added the `url.district(stateCode, districtSlug)` builder in [frontend/src/lib/url.ts](../../../frontend/src/lib/url.ts), registered `/s/:state/d/:district` (and reserved `/sd/:subdistrict` -> `NotFound`) in [frontend/src/main.ts](../../../frontend/src/main.ts), and shipped a minimal [frontend/src/routes/District.svelte](../../../frontend/src/routes/District.svelte) landing so the breadcrumb has somewhere to ascend TO; the slug is opaque to the builder (caller supplies the already-slugified district name) and the URL grammar contract from ADR-0048 / ADR-0050 holds (kebab-case slug, never uppercase ECI, never Hive partition form). **U2b (#742)** shipped [frontend/src/lib/GeoBreadcrumb.svelte](../../../frontend/src/lib/GeoBreadcrumb.svelte): a sticky glass primary-nav spine (`bg-white/80 backdrop-blur border-b border-line`, `sticky top-12 lg:top-0 z-20`) that derives `India > <state> > <district-or-ac>` from the route's `path` + `params` via the pure `computeCrumbs()` helper (no DOM, no fetch, trivially testable). Each ascend crumb is an `<a href={url.X()}>`; the leaf is a `<span aria-current="page">`. Mounted at the top of all 5 place-first routes (Home / StateOverview / StateTopic / Constituency / District). The trailing `v` sibling-jump popover (mentioned in the sub-plan scope) was deferred per the stop-and-surface trigger - the popover needs a data fetch the route does not already do, and shipping a half-coverage menu hurts citizen trust more than waiting (Citizen verdict). **U2c (#745)** re-clustered the LeftRail per parent section 21.8's same-side fix (mobile: brand + `[=]` LEFT, search top-right; drawer slides from the LEFT with `var(--ease-spring)` + `var(--dur)`), gave the mobile app bar a glass surface (`bg-app-bar-bg backdrop-blur border-b border-line` - the `--app-bar-bg` token bakes in 80% alpha so the ballot motif reads faintly through), lifted the three flag-derived hex literals (`#d97706` / `#15803d` / `#000080`) out of LeftRail inline styles onto `--brand-saffron` / `--brand-green` / `--brand-chakra` tokens, flipped the wordmark `font-family` onto `var(--font-display)` (Outfit from U1.2), and added a `build <sha>` footer line via `import.meta.env.VITE_BUILD_SHA` (injected at build time by [frontend/vite.config.ts](../../../frontend/vite.config.ts) from `git rev-parse --short HEAD`, falls back to `dev`). The ballot-motif data-URL stroke in [frontend/src/app.css](../../../frontend/src/app.css) stayed a literal hex (CSS variables do not resolve inside `url(data:...)`) but now carries an explicit `--surface-sunken` semantic comment so a future surface-ramp re-tune updates both in lockstep. U2 closure is in PR #NNNN; the sub-plan lives at [docs/archive/plans/20260605-u2-breadcrumb-drawer-district-subplan.md](../../archive/plans/20260605-u2-breadcrumb-drawer-district-subplan.md).

Every U2 sub-row honoured the ADDITIVE rule: no Tailwind default was redefined, no existing component was migrated outside LeftRail, no existing URL changed. The four new tokens (`--brand-saffron` / `--brand-green` / `--brand-chakra` / `--app-bar-bg`) are reachable by name from any later component without having to grep LeftRail. The drift contract caught the token-count bump in CI before merge (9 -> 13 colour, 34 -> 38 total).

## See also

- [colours.md](colours.md) - OkLCh party-colour resolver + indicator sequential ramps; layers on top of the colour tokens here.
- [overview.md](overview.md) - personas, IA, visualization catalog, stack.
- [docs/archive/plans/20260604-u1-tokens-fonts-subplan.md](../../archive/plans/20260604-u1-tokens-fonts-subplan.md) - the U1 sub-plan that shipped the token layer + fonts (PRs #714, #716, #718, #720).
- [docs/archive/plans/20260605-u2-breadcrumb-drawer-district-subplan.md](../../archive/plans/20260605-u2-breadcrumb-drawer-district-subplan.md) - the U2 sub-plan that shipped the per-component migration onto the tokens (PRs #739, #742, #745).
- [TODO/20260603-data-and-charting-platform-reset-plan.md](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) sections 21.7, 21.8, 23.5 - the design-spec source.
- [CLAUDE.md](../../../CLAUDE.md) section 13 (UI verification) + Holy Law #1 (static-first) + Holy Law #9 (provenance, applied to the font licence ledger).
