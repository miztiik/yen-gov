# Design system - tokens, fonts, Devanagari shaping, ADDITIVE rule

**Last Updated**: 2026-06-05

The yen-gov design system distilled out of U1 (PRs #714, #716, #718, plan section 21.7 + 23.5), extended by U2 (PRs #739, #742, #745, plan section 21.8), and extended by U5 (PRs #752, #755, #757, plan sections 20.12 + 21.9 + 23.5). It is one CSS-token layer + a Tailwind mirror + three self-hosted variable-font subsets + a body cutover + a Devanagari shaping gate + a place-first breadcrumb spine + a chart-shell state-slot contract + a sticky theme-chip jump strip + one generic indicator-doc route, governed by ONE rule (additive-not-override) so component migration can happen progressively without ever leaving the app half-broken.

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
| U4 | chart switcher chrome, axis colours | MERGED #748 + #750 |
| U5 | Skeleton primitive, ChartShell loading/error/empty/data state slots, IndicatorDoc route + URL builder, IndicatorJump sticky theme-chip strip | MERGED #752 + #755 + #757 |
| F2a | CategoryBar consolidation - one renderer with `mode={"ranked" \| "stacked" \| "diverging"}` replaces three standalone renderers (`OrderedCategoryBar`, `HorizontalGroupedBar`, `lib/CompositionBar.svelte`). Adapter packages stay put (`bar-view-models/`, `multi-dim-view-models/`, `composition-bar/`). | MERGED #781 + #782 + #784 + #785 + #786 |
| F2b | New renderers + map primitives - `GeoChoropleth.svelte` (d3-geo SVG static welfare map with `mode={"fill" \| "symbol"}` discriminator), `Matrix.svelte` (entity x time heatmap), `Treemap.svelte` (d3-hierarchy tiled part-to-whole), `CirclePack.svelte` (d3-hierarchy clustered-magnitude with `mode={"pack" \| "bubble"}`), plus C2 `ChoroplethLegend.svelte` / C3 `MapTooltip.svelte` / C5 `SourceLine.svelte` primitives. Shared `color-scale.ts` (`binnedSequential` + `sqrtAreaScale`). All renderers consume `(entity, time, value)` rows; HONESTY rule (sqrt-area for symbol / treemap / circle-pack); diagonal-stripe hatch for missing data. | MERGED #789 + #790 + #793 + #794 + #795 + #796 + #797 + this PR |

Each chunk replaces per-component literal hex / px / ms values with the matching `var(--token)` (or the matching Tailwind utility that resolves through one). The drift contract test does NOT block migrations - it blocks SILENT drift at the token layer.

### U2 - GeoBreadcrumb + glass app bar + district URL node (PRs #739 / #742 / #745)

> **Post-shipment URL grammar update (2026-06-10).** The `/s/:state/d/:district` shape U2a shipped has been superseded: PR-P1..PR-P4 (#867/#868/#869/#871) dropped the `/s/` prefix to bare `/<state>/...`, and D1 (#883) dropped the `/d/` literal marker via a runtime depth-2 dispatcher. The live district URL today is positional `/<state>/<district>`; the U2 design rationale (place-first cascade, kebab slugs, breadcrumb ascent target) is unchanged. See [docs/architecture/frontend/url-grammar.md](url-grammar.md) ADR-0037 + [docs/architecture/frontend/routing.md](routing.md) for the live grammar.

U2 lifted the place-first primary-nav surface onto the token layer in three chunks. **U2a (#739)** added the `url.district(stateCode, districtSlug)` builder in [frontend/src/lib/url.ts](../../../frontend/src/lib/url.ts), registered `/s/:state/d/:district` (and reserved `/sd/:subdistrict` -> `NotFound`) in [frontend/src/main.ts](../../../frontend/src/main.ts), and shipped a minimal [frontend/src/routes/District.svelte](../../../frontend/src/routes/District.svelte) landing so the breadcrumb has somewhere to ascend TO; the slug is opaque to the builder (caller supplies the already-slugified district name) and the URL grammar contract from ADR-0048 / ADR-0050 holds (kebab-case slug, never uppercase ECI, never Hive partition form). **U2b (#742)** shipped [frontend/src/lib/GeoBreadcrumb.svelte](../../../frontend/src/lib/GeoBreadcrumb.svelte): a sticky glass primary-nav spine (`bg-white/80 backdrop-blur border-b border-line`, `sticky top-12 lg:top-0 z-20`) that derives `India > <state> > <district-or-ac>` from the route's `path` + `params` via the pure `computeCrumbs()` helper (no DOM, no fetch, trivially testable). Each ascend crumb is an `<a href={url.X()}>`; the leaf is a `<span aria-current="page">`. Mounted at the top of all 5 place-first routes (Home / StateOverview / StateTopic / Constituency / District). The trailing `v` sibling-jump popover (mentioned in the sub-plan scope) was deferred per the stop-and-surface trigger - the popover needs a data fetch the route does not already do, and shipping a half-coverage menu hurts citizen trust more than waiting (Citizen verdict). **U2c (#745)** re-clustered the LeftRail per the same-side fix (mobile: brand + `[=]` LEFT, search top-right; drawer slides from the LEFT with `var(--ease-spring)` + `var(--dur)`), gave the mobile app bar a glass surface (`bg-app-bar-bg backdrop-blur border-b border-line` - the `--app-bar-bg` token bakes in 80% alpha so the ballot motif reads faintly through), lifted the three flag-derived hex literals (`#d97706` / `#15803d` / `#000080`) out of LeftRail inline styles onto `--brand-saffron` / `--brand-green` / `--brand-chakra` tokens, flipped the wordmark `font-family` onto `var(--font-display)` (Outfit from U1.2), and added a `build <sha>` footer line via `import.meta.env.VITE_BUILD_SHA` (injected at build time by [frontend/vite.config.ts](../../../frontend/vite.config.ts) from `git rev-parse --short HEAD`, falls back to `dev`). The ballot-motif data-URL stroke in [frontend/src/app.css](../../../frontend/src/app.css) stayed a literal hex (CSS variables do not resolve inside `url(data:...)`) but now carries an explicit `--surface-sunken` semantic comment so a future surface-ramp re-tune updates both in lockstep. U2 closure is in PR #747.

Every U2 sub-row honoured the ADDITIVE rule: no Tailwind default was redefined, no existing component was migrated outside LeftRail, no existing URL changed. The four new tokens (`--brand-saffron` / `--brand-green` / `--brand-chakra` / `--app-bar-bg`) are reachable by name from any later component without having to grep LeftRail. The drift contract caught the token-count bump in CI before merge (9 -> 13 colour, 34 -> 38 total).

### U5 - Skeleton + ChartShell state slots + IndicatorDoc route + IndicatorJump strip (PRs #752 / #755 / #757)

U5 lifted the loading / error / empty / data states + the indicator-doc IA + the theme-chip jump strip onto the token layer in three sub-rows. **U5a (#752)** shipped [frontend/src/lib/Skeleton.svelte](../../../frontend/src/lib/Skeleton.svelte) (a generic loading primitive with a `prefers-reduced-motion`-aware shimmer, reading from `--surface-sunken` / `--r-md` / `--dur`; module-scope `skeletonStyle({width,height})` helper is the testable surface so vitest covers the size resolution without mounting) and folded the four state slots (`loading` / `error` / `empty` / `data`, default `data`) into the EXISTING [frontend/src/lib/charts/ChartShell.svelte](../../../frontend/src/lib/charts/ChartShell.svelte) instead of minting a new state-aware shell - header + footer (title, subtitle, toolbar, honesty banners, sources, actions) render UNCHANGED across all four states; only the body branches. The resolver [frontend/src/lib/charts/chart-shell/state.ts](../../../frontend/src/lib/charts/chart-shell/state.ts) normalises `null` / `undefined` -> `"data"` so callers never branch on undefined; `DEFAULT_ERROR_MESSAGE = "Data unavailable"` and `DEFAULT_EMPTY_MESSAGE = "No data for this selection."` are the canonical copy. The empty-state diagonal-stripe SVG hatch is inlined into ChartShell (no new shared `HatchPattern.svelte` component for one caller; matches the existing `CategoryBar` `ocb__hatch` / `hgb__cell-hatch` (class names carried over from the retired `OrderedCategoryBar` / `HorizontalGroupedBar` bodies, lifted byte-identical into the consolidated renderer in F2a) / `FacetPanelGrid.fpg__hatch` visual language). The four state branches consume `--surface-sunken` + `--ink-muted` only - no new tokens minted. **U5b (#755)** added the `url.indicatorDoc(indicatorId)` builder in [frontend/src/lib/url.ts](../../../frontend/src/lib/url.ts) (preserves the `<topic>/<id>` slash as a path separator, never URL-encodes it), registered `/docs/indicator/:topic/:id` in [frontend/src/main.ts](../../../frontend/src/main.ts), and shipped ONE generic [frontend/src/routes/IndicatorDoc.svelte](../../../frontend/src/routes/IndicatorDoc.svelte) route that reads the catalogue + render hints + provenance (NEVER hand-authored per indicator). The route uses the same loading + error chrome the chart cards use via `<ChartShell state="loading|error|data">` - one consistency contract between cards and doc pages. Pure helpers `projectToFourFieldSource()` + `cadenceLabel()` are the testable surface (the route component itself is one mount per indicator id; no jsdom tests). The cadence + staleness banner driven by `update_period_days` (plan section 20.10) and the 4-field provenance read from `entities/source.csv` (plan section 7) ship as TODO markers in the doc rendering; they lift when B2a / B2b emit the columns and F1 / X1a re-point the read path. **U5c (#757)** shipped [frontend/src/lib/IndicatorJump.svelte](../../../frontend/src/lib/IndicatorJump.svelte): a sticky theme-chip jump strip (sticky `top-12`, mobile-first ~360px, horizontal-scroll chip row with active highlight, type-to-filter input above) mounted at the top of [frontend/src/routes/StateOverview.svelte](../../../frontend/src/routes/StateOverview.svelte) when >1 topics. Scroll-spy is wired in `$effect` via an `IntersectionObserver` (`rootMargin: "-80px 0px -60% 0px"`); the pure helpers `filterGroups()` + `activeIdForOffsets()` exported from the module-scope `<script module>` are the testable surface (16 vitest cases). The `current` chip is `$bindable` so the parent route can drive initial mount AND the observer mutates it as the user scrolls. Each topic section in `StateOverview` gets a `data-jump-id={topic.id}` attribute so the observer knows what to watch. The strip reads from `--surface` / `--surface-sunken` / `--line` / `--ink` / `--ink-muted` / `--accent` / `--r-pill` only - no new tokens minted.

Every U5 sub-row honoured the ADDITIVE rule: no Tailwind default was redefined, no existing component was MIGRATED (Skeleton is new; IndicatorDoc + IndicatorJump are new routes / components; ChartShell gained state branches but its default `state="data"` is byte-for-byte the pre-U5a behaviour for every existing caller). No new tokens were minted in U5 (token count stays at 38 from U2c); the drift contract did not need to bump. The (i) glyph on each ChartShell title linking to `/docs/indicator/<id>` is the JOB OF every renderer that has an indicator id, and lifts in the renderer-by-renderer migration that follows U5 (NOT scope of U5b). The theme-drawer integration of IndicatorJump (plan section 20.12: "reused by state page + theme drawer") is deferred to the sub-plan that lifts the drawer's theme grid; U5c integrates only into the state route.

### F2a - CategoryBar consolidation (PRs #781 / #782 / #784 / #785 / #786)

F2a collapsed three standalone bar renderers into ONE component with a discriminated-union `mode` prop. The seam shape is:

```ts
type CategoryBarProps<T> =
  | { mode: "ranked"; view_model: OrderedCategoryBarViewModel<T>; ... }
  | { mode: "stacked"; view_model: GroupedBarViewModel<T>; ... }
  | { mode: "diverging"; view_model: CompositionBarModel; ... };
```

The `mode` literal is the discriminator; TypeScript narrows each branch so each body sees only the props it needs. Renderer-internal helpers (axis, scale, sort, tiny-segment lift, hatch placeholder) stay shared. Per the design doctrine: there are now exactly **8 base renderers + 1 optional + 3 primitives + 2 modes** in the chart engine; adding a fourth bar mode is a design-spec change, not an additive PR.

**Five PRs shipped F2a as five strangler-fig slices** per `/memories/patterns.md` PR #78 doctrine:

- **F2a.1+F2a.2 (#781)** added the `CategoryBar.svelte` shell with `mode="ranked"` (byte-identical body lift from the retired `OrderedCategoryBar.svelte` 196 LOC) and flipped DevChartsSandbox's only consumer. The `bar-view-models/` builder package stayed put as the canonical VM toolkit; the renderer just changed name.
- **F2a.3+F2a.4 (#782)** added `mode="stacked"` (body lift from the retired `HorizontalGroupedBar.svelte` 289 LOC) and flipped the same sandbox. `multi-dim-view-models/` stayed put. The `legendColour` helper now exports from CategoryBar's `<script module>` block (Svelte-5 generic-component gotcha: `export type` cannot live in the instance script).
- **F2a.5.1 (#784)** added `mode="diverging"` (body lift from the retired `lib/CompositionBar.svelte` 252 LOC) with a sandbox-only proof; production mount untouched. The diverging body wraps itself in ChartShell internally because the `CompositionBarModel` carries title / subtitle / honesty_banners / caption_fptp that the existing top-level `wrap_in_shell` mechanism doesn't surface.
- **F2a.5.2 (#785)** migrated the single production consumer (the experiment-gated composition-bar A/B mount in [frontend/src/routes/StateOverview.svelte](../../../frontend/src/routes/StateOverview.svelte) line ~775) from `<CompositionBar />` to `<CategoryBar mode="diverging" />`, deleted the standalone `lib/CompositionBar.svelte` (262 LOC), and updated the Playwright spec selectors from `[data-component="composition-bar"]` to `[data-component="category-bar"][data-mode="diverging"]` with a deletion-guard assertion. §13 in-browser smoke against `/s/karnataka?yg_variant=treatment` (Karnataka = S10, in the experiment's targeting list per `experiment-definition.json`) verified all three buckets: treatment renders the diverging bar + donut sibling, control renders donut only, TN out-of-targeting renders donut only even with the override. The experiment id (`chart-composition-bar-election-seats`), cookie mechanism (`?yg_variant=<variation_id>` URL override persisting to `yg_variant_<experiment_id>` cookie via `bucket.ts:readOverride`) and removal contract are unchanged.
- **F2a.5.3 (#786)** rewrote the `composition-bar/` package README to reframe it as the **diverging-bar adapter package consumed by `CategoryBar mode="diverging"`** (option-a from the F2a.5 sub-sub-plan; minimal-churn KEEP-the-folder + clarify-the-contract, no rename or split). The package is now explicitly analogous to `bar-view-models/` (ranked) and `multi-dim-view-models/` (stacked).

A pre-flight audit in F2a.5.2 corrected the F2a sub-plan body's blast-radius assumption: `composition-bar/` had ONE production consumer (StateOverview line ~775, experiment-gated), not five (the originally-claimed `IndicatorChoropleth` 923 LOC / `IndicatorRanked` 474 LOC / `IndicatorSmallMultiples` 227 LOC / `StackedTrendV2` 805 LOC do NOT import from `composition-bar/`; their grep matches were unrelated namespace collisions). The audit also corrected the experiment-cookie smoke recipe (the sub-sub-plan body had originally proposed a `composition_bar=on` cookie and `/s/tamil-nadu` smoke route - both incorrect against the actual `bucket.ts` machinery and the explicit TN-exclusion in `experiment-definition.json`).

Net F2a delta: **3 standalone renderer files deleted** (`OrderedCategoryBar.svelte` 196 + `HorizontalGroupedBar.svelte` 289 + `lib/CompositionBar.svelte` 262 = **747 LOC**), **1 consolidated renderer added** (`CategoryBar.svelte` 606 LOC). Adapter packages unchanged. DevChartsSandbox is the sandbox seam for all three modes; production routes consume CategoryBar directly with `mode={"ranked" | "stacked" | "diverging"}`. The discriminated-union pattern is the design template F2b (new renderers) can build on: a new bar mode is `mode: "new-mode"` plus a new body branch, not a new file.

F2a honoured the ADDITIVE rule: no Tailwind default was redefined, no token was minted, and no existing renderer's DOM contract changed (the body lift preserved `data-component` / `data-mode` / `data-segment-id` / `data-share-pct` / hatch class names; the only attribute change was the wrapper element flipping from `data-component="composition-bar"` to `data-component="category-bar" data-mode="diverging"`, which downstream Playwright + golden-render fixtures pick up directly). All three modes share the same `<ChartShell>` wrap + the same `bar-view-models/` / `multi-dim-view-models/` / `composition-bar/` adapter contracts.

### F2b - new renderers + map primitives (PRs #789 / #790 / #793 / #794 / #795 / #796 / #797 + closure)

F2b shipped the eight remaining renderer surfaces called out in the renderer plan (§14.3 + §15.1): four new renderers (`GeoChoropleth`, `Matrix`, `Treemap`, `CirclePack`), three primitives (C2 `ChoroplethLegend`, C3 `MapTooltip`, C5 `SourceLine`), and one shared color-scale module (`color-scale.ts` with `binnedSequential` + `sqrtAreaScale`). The seam shape is:

- **Sub-plan ledger**: 8 sub-rows F2b.1..F2b.8 (see F2b sub-rows below).
- **Primitives (F2b.2 / #790)**: `ChoroplethLegend` (rectangular binned intensity bar + value-tick caret on hover), `MapTooltip` (region label + parent + formatted value + swatch chip; absolute-positioned by caller), `SourceLine` (`Source: <owner> (as of <vintage>)` chip; optionally linked). All three are pure presentation leaves with no aria/role (CLAUDE.md §0). Color-scale.ts exposes `binnedSequential({domain, bins, direction, format_tick})` returning `{colorForValue, bin_edges, swatches, tick_labels, positionForValue}` + `sqrtAreaScale({max_value, range_min_px, range_max_px})` + `shouldRenderValueTick(domain, value)` + `positionForValue(domain, value)` helpers.
- **GeoChoropleth (F2b.3 / #793 + F2b.7 / #797)**: d3-geo SVG static welfare map per the renderer plan (§14.5: "d3-geo SVG for ALL static welfare choropleths; maplibre-gl fenced to election AC pan/zoom"). Loads topojson via `fetch(DATA_BASE + topojson_path)`, decodes via `topojson-client.feature()`, projects via `geoMercator().fitSize([w, h], collection)` per the F4 island-render-smoke contract. `mode={"fill" | "symbol"}` discriminator on the SAME .svelte file: fill renders one `<path>` per feature filled by `binnedSequential.colorForValue(rows[key])`; symbol derives `geoCentroid(feature)` + projects + renders one `<circle>` per feature area-sized via `sqrtAreaScale(value)` over a faint base outline. No-data fall-through to a diagonal-stripe `<pattern>` hatch (C4 from renderer plan §14.3). Default `mode="fill"` preserves F2b.3 byte-identical behaviour for callers that don't supply the prop.
- **Matrix (F2b.4 / #794)**: entity x time heatmap. Top axis = times, left axis = entities, body = cells coloured via `binnedSequential.colorForValue()` (the SAME scale GeoChoropleth uses; renderer plan doctrine #5). Missing cells fall through to the same `url(#matrix-hatch)` C4 idiom GeoChoropleth uses. Hover-driven C2 legend value-tick + C3 tooltip. Pure helpers `rowsByEntityByTime`, `entityOrder`, `timeOrder`, `deriveDomain` exposed from `matrix-helpers.ts` so vitest covers the pivot/sort/domain math without DOM.
- **Treemap (F2b.5 / #795)**: d3-hierarchy `treemap()` aspect-ratio-balanced rectangles whose AREA is value-proportional (HONESTY per renderer plan §15.1: 4x value reads as 4x area, not 16x). Labels render only on tiles wide AND tall enough (default 40x18 px thresholds); smaller tiles are swatch-only with the label on hover. Two-level grouping via `parent_id`; flat-list shortcut when all `parent_id` omitted. Caller-supplied `color_for_tile` fn accepts both category palettes and shared-scale binned colours (proves the seam).
- **CirclePack (F2b.6 / #796)**: d3-hierarchy `pack()` layout with `mode={"pack" | "bubble"}` discriminator. `pack` = padding=2, hierarchical (respects `parent_id`; precise-compare vibe). `bubble` = padding=8, flat (ignores `parent_id`; clustered-magnitude vibe). Same HONESTY rule as Treemap (sqrt area). Labels render only when `r >= 24px`; smaller circles are swatch-only with hover tooltip.
- **Storage-format-agnostic**: all four renderers consume `(entity, time, value)` rows only (renderer plan invariant #1). The loader seam below owns parquet-vs-csv abstraction; renderers stay byte-identical when X1a/X1b cutover lands.
- **Strangler-fig topology**: F2b ships ALONGSIDE the existing `IndicatorChoropleth.svelte` (maplibre) and `MapChoropleth.svelte`. A separate post-F2b chunk migrates production routes from maplibre to d3-geo; the maplibre path stays live until the d3-geo path is proven across production routes.
- **§13 sandbox seam**: each renderer ships a fixture section in [frontend/src/routes/DevChartsSandbox.svelte](../../../frontend/src/routes/DevChartsSandbox.svelte) (fixtures 7-11). The sandbox is the §13 smoke surface for the seven renderer PRs.
- **U4 ChartType drift**: every renderer's Machine id is already a member of the `ChartType` union (U4 #748 pre-loaded all 12 members + the chart-index.md section-1 table). The drift gate ([frontend/src/lib/grapher/chart-index.drift.test.ts](../../../frontend/src/lib/grapher/chart-index.drift.test.ts)) stayed green through every F2b PR.
- **A11y descope**: all renderers omit aria/role on SVG body elements per CLAUDE.md §0; visible affordances only (hover-driven tooltip, cursor change, stroke-on-hover).
- **D3 deps added**: F2b.5 promoted `d3-hierarchy ^3.1.2` + `@types/d3-hierarchy ^3.1.7` from transitive (via `d3`) to first-class runtime deps for clean tree-shaking. Same pattern F4 used for `d3-geo` + `@types/d3-geo`.

Net F2b delta: **9 NEW files** (GeoChoropleth + Matrix + Treemap + CirclePack `.svelte` + their `-helpers.ts` + helper `.test.ts` + ChoroplethLegend + MapTooltip + SourceLine + color-scale.ts + tests), **~2500 LOC added** (renderers + tests + helpers + sandbox demos + sub-plan ledger), **0 production routes touched** (sandbox-only for v1; production migration is post-F2b strangler-fig).

The F2a discriminated-union pattern repeats here: GeoChoropleth `mode={"fill" | "symbol"}` + CirclePack `mode={"pack" | "bubble"}` both swap visual idioms by flipping ONE prop, no new files. The shared `color-scale.ts` is the contract surface that lets a citizen read across GeoChoropleth, Matrix, and any future renderer in the same palette domain without a perceptual reset.

F2b honoured the ADDITIVE rule: no Tailwind default redefined, no existing renderer touched (IndicatorChoropleth + MapChoropleth still live), no existing route's contract changed. The seven renderer files + three primitive files + one helper module land as new surfaces alongside the existing renderers; the strangler-fig migration is a separate future chunk.

## See also

- [colours.md](colours.md) - OkLCh party-colour resolver + indicator sequential ramps; layers on top of the colour tokens here.
- [overview.md](overview.md) - personas, IA, visualization catalog, stack.
- U1 sub-plan (PRs #714, #716, #718, #720) - shipped the token layer + fonts.
- U2 sub-plan (PRs #739, #742, #745) - shipped the per-component migration onto the tokens.
- U5 sub-plan (PRs #752, #755, #757) - shipped Skeleton + ChartShell state slots + IndicatorDoc route + IndicatorJump strip.
- F2a sub-plan (PRs #781, #782, #784, #785, #786) - shipped CategoryBar consolidation.
- F2a.5 sub-sub-plan (PRs #784, #785, #786) - shipped the diverging-mode body lift + StateOverview production migration + composition-bar/ README rewrite.
- F2b sub-plan (PRs #789, #790, #793, #794, #795, #796, #797 + closure) - shipped GeoChoropleth + Matrix + Treemap + CirclePack + C2/C3/C5 primitives + shared color-scale.
- [frontend/src/lib/charts/composition-bar/README.md](../../../frontend/src/lib/charts/composition-bar/README.md) - the diverging-bar adapter package README (post-F2a.5.3 framing).
- [CLAUDE.md](../../../CLAUDE.md) section 13 (UI verification) + Holy Law #1 (static-first) + Holy Law #9 (provenance, applied to the font licence ledger).
