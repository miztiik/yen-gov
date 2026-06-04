# U1 sub-plan - tokens + fonts + retone (the 21.7 modern design system)

**Last Updated**: 2026-06-04
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk U1
**Status**: IN-FLIGHT (2026-06-04, U1.1 first PR open)
**Authority**: Jony (visual + craft) / Gregor (additive contract) / Andre (Devanagari shaping check) per CLAUDE.md section 0a

---

## Why this exists

Parent chunk U1 reads as one row in the parent Execution Ledger but expands into four distinct deliverables: (a) the token layer (`app-tokens.css` + Tailwind `theme.extend` ADDITIVE mirror + drift contract test), (b) self-hosted subset variable fonts (Inter Latin + Noto Sans Devanagari with GSUB/GPOS shaping retention + Outfit wordmark) with `font-display: swap` and `LICENCES.md` provenance, (c) the cutover (REMOVE the Google-CDN `<link>` + the two `preconnect`s in `frontend/index.html`, ADD the preload for Inter Latin, flip body font-family to the new var, retone the hardcoded `slate-400` ballot motif in `frontend/src/app.css` onto a `var(--surface-sunken)` reference, apply tabular numerals in data contexts, and run the Devanagari conjunct render smoke), (d) closure (distil into `docs/architecture/frontend/design-system.md`; flip the parent U1 ledger row -> MERGED; archive this sub-plan under `docs/archive/plans/`).

Per CLAUDE.md correction-level discipline (>=4 files structural -> propose breakdown first) and parent plan section 24.5, the right shape is a thin parent row + this sub-plan. B1 and B2a followed the same shape (PRs #629-#670 and #673-#688 respectively).

---

## Scope

### In scope (this sub-plan)

1. `frontend/src/app-tokens.css` (new) - CSS custom properties on `:root` per plan section 21.7 (colour / type / radius / elevation / motion).
2. `frontend/src/main.ts` (one-line import) - load the tokens stylesheet before `./app.css`.
3. `frontend/tailwind.config.js` (theme.extend fill) - ADDITIVE mirror per section 23.5: NEW semantic keys only; Tailwind's `slate-*`, `sm`/`md`/`lg` radius, stock `sans` `fontFamily`, and stock `transitionDuration` keys are untouched. Components migrate per-component in U2..U5.
4. `frontend/src/contracts/app-tokens.test.ts` (new) - drift test locking the CSS-var <-> Tailwind theme.extend round-trip.
5. `frontend/public/fonts/` (new directory) - self-hosted variable woff2 subsets: `inter-latin.woff2`, `noto-sans-devanagari.woff2` (full GSUB/GPOS shaping tables retained, NOT codepoint-only), `outfit-latin.woff2` (wordmark only, weight 300).
6. `frontend/public/fonts/LICENCES.md` (new) - provenance ledger per CLAUDE.md Holy Law #9 (Inter SIL OFL 1.1, Noto SIL OFL 1.1, Outfit SIL OFL 1.1).
7. `frontend/src/app.css` - `@font-face` declarations with `font-display: swap` + `unicode-range` for the Devanagari fall-through; body `font-family: var(--font-sans)` + `font-feature-settings: var(--font-feature-tabular)`; retone the ballot-motif `stroke='%23475569'` data-URL to a calmer value derived from `--surface-sunken` (encoded inline since CSS variables do not resolve inside `url(data:...)`).
8. `frontend/index.html` - REMOVE the Google CDN `<link>` + the two `preconnect`s; ADD a single `<link rel="preload" as="font" type="font/woff2" href="/fonts/inter-latin.woff2" crossorigin>`.
9. `frontend/e2e/devanagari-conjunct.spec.ts` (new) - Playwright in-browser smoke that renders one Devanagari conjunct word (e.g. `kSha = kSa` ligature, `\u0915\u094D\u0937`) inside a hidden span at body font-size; asserts the conjunct lays out as one shaped glyph cluster (not as separate atomic codepoints). A codepoint-only font subset that dropped GSUB/GPOS would fail.
10. `docs/architecture/frontend/design-system.md` (new) - distil: token map, font-subset recipe (`fonttools subset --layout-features='*'`), retone receipt, smoke gate description.

### Out of scope (other parent chunks)

- **U2**: `GeoBreadcrumb.svelte`, LeftRail re-cluster, glass app bar, spring drawer, same-side drawer fix, `url.district()` builder, `/s/:state/d/:district` route. The LeftRail hardcoded brand hex (`#d97706` / `#15803d` / `#000080`) + the Outfit dependency MOVE in U2 per section 23.5; this sub-plan does not touch LeftRail.svelte.
- **U3**: icons -> `frontend/public/icons/` + `LICENCES.md` + repoint `iconRegistryPlugin`.
- **U4** / **U5**: chart switcher + skeletons (independent tracks).
- **F* / X1a / X1b**: data-store cutover (independent).

---

## Sub-row Execution Ledger

| Sub-row | Blocks on | Gate | PR# | Status |
| --- | --- | --- | --- | --- |
| U1.1 tokens (`app-tokens.css` + `main.ts` import + `tailwind.config.js theme.extend` ADDITIVE + drift contract test) | - | build+drift | #714 | IN-FLIGHT |
| U1.2 fonts (self-hosted subset variable woff2 + `LICENCES.md` + `@font-face` declarations + Inter-Latin preload) | U1.1 | build+font-load | - | TODO |
| U1.3 cutover (remove CDN `<link>` + 2 preconnects; flip body font; retone ballot motif; tabular-nums on data; Devanagari conjunct render check) | U1.2 | build+visual+devanagari | - | TODO |
| U1.4 closure (distil to `docs/architecture/frontend/design-system.md`; flip parent U1 row -> MERGED; archive this sub-plan to `docs/archive/plans/`) | U1.1..U1.3 | docs-review | - | TODO |

---

## Per-sub-row notes

### U1.1 tokens

- CSS custom properties on `:root` per section 21.7 verbatim (named tokens for colour / type / radius / elevation / motion).
- Type-scale tokens (`--text-xs` .. `--text-4xl`) values match Tailwind's stock `text-*` utility scale one-for-one (minor-third 1.2 at base 16px) so an existing utility class continues to read identically with or without the new tokens.
- Tailwind mirror uses NEW keys (`ink`, `accent`, `yen-sans`, `yen-sm`, `e1`, `yen-out`, ...) - never `slate`, never the existing default `sm`/`md`/`lg` radius scale, never the default `sans` family. This is the ADDITIVE rule (section 23.5) and is what lets U1.1 ship without re-skinning any component.
- Drift test (`frontend/src/contracts/app-tokens.test.ts`) asserts (a) the core token set is declared, (b) every `var(--...)` in Tailwind's theme.extend resolves to a declared `--var`, (c) every non-exempt `--var` in `app-tokens.css` has at least one Tailwind mirror. Type-scale and `--font-feature-tabular` are exempt by design (covered by Tailwind defaults / applied directly in CSS, not via a utility class).
- In-browser smoke per CLAUDE.md section 13: `bun run dev` -> open `/` -> read page -> confirm no new console errors and the existing slate body / chrome still renders unchanged. Visual gate for U1.1 is "no visible change" (the tokens are dormant until U2..U5 components opt in); the deeper visual + Devanagari smoke fires at U1.3.

### U1.2 fonts (planning, ships next)

- Subset recipe: `fonttools subset INPUT.ttf --layout-features='*' --unicodes='U+0000-024F,U+1E00-1EFF,U+2000-206F,U+20A0-20CF,U+2070-209F'` for Inter Latin (keep ALL OpenType layout features); `--unicodes='U+0900-097F,U+200C-200D,U+25CC'` for Noto Sans Devanagari (keep GSUB/GPOS for conjunct shaping); `--unicodes='U+0020-007E'` for Outfit wordmark only.
- `font-display: swap` everywhere; `unicode-range` on Devanagari `@font-face` so the browser fetches it only when a Devanagari codepoint appears.
- `LICENCES.md` carries each font's SIL OFL 1.1 attribution + upstream URL + the subset recipe used + the date.
- Holy Law #9 reminder: every binary woff2 file ships with a provenance row in `LICENCES.md`.

### U1.3 cutover (planning)

- REMOVE these lines from `frontend/index.html`:
  ```
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500&display=swap" rel="stylesheet" />
  ```
- ADD: `<link rel="preload" as="font" type="font/woff2" href="/fonts/inter-latin.woff2" crossorigin>` (Inter only; Devanagari fetches on demand by `unicode-range`).
- Retone ballot motif in `frontend/src/app.css`: the data-URL `stroke='%23475569'` becomes the same hex referenced under a semantic comment (since CSS vars do not resolve inside `url(data:...)`, the value stays a literal hex but the comment points at `--surface-sunken` semantics).
- Apply `font-family: var(--font-sans)` + `font-feature-settings: var(--font-feature-tabular)` on `body`.
- Devanagari conjunct render smoke: open `/`, inject a hidden span with `style="font-family: var(--font-deva)"` and inner text `\u0915\u094D\u0937` (Devanagari KA + VIRAMA + SSA = the kSha conjunct). Measure the rendered glyph cluster width; assert it is smaller than the codepoint-by-codepoint baseline width (codepoint-only subset emits three separate atomic glyphs; shaped subset emits one ligature glyph that is visibly narrower). The Playwright spec ships under `frontend/e2e/devanagari-conjunct.spec.ts`.

### U1.4 closure

- Distillation home: `docs/architecture/frontend/design-system.md` (new). One H1 + (a) token map (CSS var + Tailwind mirror per row), (b) font subset recipe with the verbatim `fonttools` invocation, (c) the additive-not-override rule + the per-component migration table for U2..U5 consumers, (d) the drift contract pointer.
- Parent ledger row U1 flips from `DEFERRED-TO-SUBPLAN` -> `MERGED`, stamped with the U1.4 PR#.
- This sub-plan moves under `docs/archive/plans/20260604-u1-tokens-fonts-subplan.md` and inbound links across the repo are rewritten.

---

## Parallel-safety

- U1.1 is entirely additive: no Tailwind default is redefined, no component is migrated, no font file is added, no `index.html` line is removed. Other tracks (B2b-blocked, D-DOC2, D-DOC3, U3) may run alongside.
- U1.2 ships only woff2 files + `@font-face` + `LICENCES.md`; the body font-family flip waits for U1.3 so a half-merged state never breaks the page.
- U1.3 is the visible cutover and MUST hold the `devanagari` gate before merge.
- U1.4 is doc-only.

---

## See also

- Parent plan section 21.7 (modern design system token spec, full).
- Parent plan section 23.5 (frontend design + nav corrections, ADDITIVE rule).
- Parent plan section 22.6 (gates catalogue, `build+visual+devanagari`).
- Parent plan section 24.5 (sub-plan spawning shape).
- CLAUDE.md section 13 (UI verification - in-browser smoke).
- `/memories/lessons.md` (vitest `$lib` alias caveat - use relative imports in contract tests).
