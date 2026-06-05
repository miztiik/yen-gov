# U2 sub-plan - GeoBreadcrumb + LeftRail re-cluster + district URL node

**Last Updated**: 2026-06-05
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) chunk U2
**Status**: IN-FLIGHT (spawned #738)
**Authority**: Jony (visual + same-side fix + breadcrumb craft) / Gregor (URL grammar contract + new route node) / Citizen (tap-to-ascend comprehension) per CLAUDE.md section 0a

---

## Why this exists

Parent chunk U2 reads as one row in the parent Execution Ledger but expands into three distinct deliverables plus a closure: (a) the URL grammar gains a district node (`url.district(stateCode, districtSlug)` builder + `/s/:state/d/:district` route + a minimal `District.svelte` landing) so the breadcrumb has somewhere to ascend TO; (b) the new `GeoBreadcrumb.svelte` component (sticky primary-nav spine, glass, tap-to-ascend crumbs + trailing `v` sibling-jump) plus integration into the place-first routes (Home / StateOverview / StateTopic / Constituency / District); (c) the LeftRail re-cluster (same-side fix + glass app bar + spring drawer + token migration of the brand-hex literals + ballot-motif retone + `build <sha>` footer line); (d) closure (distil into `docs/architecture/frontend/design-system.md` per-component-migration U2 row; flip the parent U2 ledger row -> MERGED; archive this sub-plan under `docs/archive/plans/`).

Per CLAUDE.md correction-level discipline (>= 4 files structural -> propose breakdown first) and parent plan section 24.5, the right shape is a thin parent row + this sub-plan. Precedents: U1 (4 sub-rows, PRs #714 / #716 / #718 / #720), B1 (7 sub-rows, PRs #629-#670), B2a (8 emits + closure, PRs #673-#688), D-DOC3 (10 sub-rows in flight). The user's kickoff explicitly named the same 3-way split ("U2a url-builder+route, U2b GeoBreadcrumb component, U2c LeftRail re-cluster").

---

## Scope

### In scope (this sub-plan)

1. `frontend/src/lib/url.ts` - add `url.district(stateCode, districtSlug)` builder; slug derived from the LGD district `display_name` via `slug.ts:slugify()`; accepts ECI state code OR LGD state slug for `stateCode` (same dual-input contract as `url.state` per ADR-0048 / ADR-0050).
2. `frontend/src/main.ts` - register `/s/:state/d/:district` route binding to a new `District.svelte`. Reserve `/sd/:subdistrict` route shape per parent section 23.5 (declared but routes to `NotFound` until a future chunk lifts the data).
3. `frontend/src/routes/District.svelte` (new) - minimal landing route that resolves the LGD district by slug + parent state and renders state + district name + a placeholder body referencing the future chart surface. Reachable via URL; NOT yet linked from any rail item.
4. `frontend/src/lib/url.test.ts` - add canonical-URL grammar assertions: `url.district` shape, never emits uppercase ECI, never emits Hive partition form, never the legacy `/state/<code>` shape; slug-passthrough test (`url.district("tamil-nadu", "coimbatore")` -> `/s/tamil-nadu/d/coimbatore`).
5. `frontend/src/lib/GeoBreadcrumb.svelte` (new) - sticky glass primary-nav spine. Renders the crumb chain `India > <state> > <district-or-ac>` from the current `route.params` (any subset present in the URL is shown; missing levels collapse). Each crumb is an `<a href={url.X()}>` to ascend; the trailing `v` opens a sibling-jump menu of peer entities at the current grain. Styling reads from existing tokens (`--ink`, `--ink-muted`, `--line`, `--accent`, `--surface`, `--e1`) - no new tokens minted in U2b.
6. `frontend/src/lib/GeoBreadcrumb.test.ts` (new) - vitest unit tests: render chain for India / state / state+district / state+AC cases, ascend-link href correctness via `url.X()` builders, sibling-jump menu structure.
7. Route integration (one `<GeoBreadcrumb />` import + mount near the top of each route file): `Home.svelte`, `StateOverview.svelte`, `StateTopic.svelte`, `Constituency.svelte`, `District.svelte` (new in U2a).
8. `frontend/src/lib/LeftRail.svelte` re-cluster: move hardcoded brand hex (`#d97706`, `#15803d`, `#000080`) onto new semantic colour tokens (`--brand-saffron`, `--brand-green`, `--brand-chakra`) added to `app-tokens.css`; move the inline `font-family: "Outfit"` declaration onto `var(--font-yen-display)` (already mapped to Outfit in U1.1); same-side fix per parent section 21.8 (brand + `[=]` LEFT cluster + `[search]` top-right placeholder); glass app bar (`bg-surface/80 backdrop-blur border-line`); spring drawer (`var(--ease-spring)` + `var(--dur)`); `build <sha>` footer line via `import.meta.env.VITE_BUILD_SHA` (or equivalent build-time inject).
9. `frontend/src/app.css` - retone the hardcoded `slate-400`-derived ballot motif onto a `var(--surface-sunken)`-semantic comment (the literal hex stays inline since CSS vars do not resolve inside `url(data:...)`, but the comment + the semantic surface alignment is U1.3's contract that U2c now fulfils for the LeftRail-adjacent motifs).
10. `frontend/src/app-tokens.css` - add `--brand-saffron: #d97706;`, `--brand-green: #15803d;`, `--brand-chakra: #000080;` (the three flag-derived brand-hex literals were already chosen for WCAG AA against the wordmark in U1; U2c just lifts them out of LeftRail into a token home) plus `--app-bar-bg: rgb(255 255 255 / 0.80);` for the glass app bar.
11. `frontend/src/contracts/app-tokens.test.ts` - update token-count assertion to reflect the +4 new tokens (colour 9+3 brand + the +1 glass surface = the colour-family count goes from 9 to 13; total token count from 34 to 38).
12. `frontend/tailwind.config.js` - mirror the 3 brand colour tokens (`brand-saffron`, `brand-green`, `brand-chakra`) so `text-brand-saffron` / `text-brand-green` / `text-brand-chakra` utilities resolve.
13. `docs/architecture/frontend/design-system.md` - flip the per-component-migration U2 row from `TODO` to `MERGED #N`; add the four new colour tokens to the token map; brief distillation paragraph for the GeoBreadcrumb + glass-app-bar surface.
14. `TODO/20260603-data-and-charting-platform-reset-plan.md` - flip U2 row from `DEFERRED-TO-SUBPLAN` to `MERGED` + stamp PR#s for U2a..U2d.
15. `git mv TODO/20260605-u2-breadcrumb-drawer-district-subplan.md docs/archive/plans/20260605-u2-breadcrumb-drawer-district-subplan.md` at U2d closure.

### Out of scope (other parent chunks)

- **U3**: icons -> `frontend/public/icons/` + `LICENCES.md` (already MERGED #736).
- **U4**: chart switcher (`SegmentedControl` + `ChartShell` toolbar + `feasibleAt()` + grapher JSON migration). Blocks on D-DOC2 (MERGED #721).
- **U5**: skeleton + `IndicatorJump` + `routes/IndicatorDoc.svelte` + ChartShell error/empty slots. Blocks on U1.
- **B***, **F***, **X1a/b**, **YA**: backend + data cutover (independent).
- **The data layer for the district route**: U2a ships ONLY the URL grammar + a placeholder landing. The chart surface that consumes it lifts in F2b (new renderers) + U4 (switcher); U2 is the place-first navigation chrome.
- **The `/sd/:subdistrict` route content**: U2a reserves the SHAPE in the router (binding to `NotFound` until a later chunk delivers subdistrict-grain data). The route is mentioned in `url.test.ts` only by its absence (no `url.subdistrict()` builder ships in U2).
- **Component-wide token re-skin**: U2c migrates ONLY the LeftRail brand-hex literals + the ballot-motif retone the U1.3 carry-over named. Every other component still keeps its old-but-consistent look until its own per-component migration row lands in a later sub-plan (the additive rule, parent section 23.5).

---

## Sub-row Execution Ledger

| Sub-row | Blocks on | Parallel-OK with | Gate | PR# | Status |
| --- | --- | --- | --- | --- | --- |
| U2a url.district + `/s/:state/d/:district` route + minimal `District.svelte` + `url.test.ts` assertions | - | U2c, U4, U5 | build+vitest(url) | #739 | MERGED |
| U2b `GeoBreadcrumb.svelte` + integration into Home / StateOverview / StateTopic / Constituency / District | U2a | U2c, U4, U5 | build+vitest(breadcrumb)+in-browser smoke (5 routes) | #742 | MERGED |
| U2c LeftRail re-cluster (same-side fix + glass app bar + spring drawer + token migration + ballot-motif retone + `build <sha>` footer) | U1 (MERGED #720) | U2a, U2b, U4, U5 | build+vitest(tokens)+in-browser smoke | #745 | MERGED |
| U2d closure (distil into `docs/architecture/frontend/design-system.md` U2 row; flip parent U2 ledger; archive this sub-plan) | U2a, U2b, U2c | - | docs-review | _pending_ | TODO |

U2a -> U2b is a hard edge (the breadcrumb's District crumb hrefs through `url.district()`). U2c is parallel-OK with U2a + U2b (LeftRail surface is visually-separable from the breadcrumb spine; the new tokens U2c mints are not referenced by U2b). U2d is closure.

---

## Per-sub-row notes

### U2a url.district + `/s/:state/d/:district` route + minimal `District.svelte`

**Files (~6, ~150 LOC including tests):**

- `frontend/src/lib/url.ts`: new builder
  ```ts
  district(stateCode: string, districtSlug: string): string {
    const slug = states.slug(stateCode) || stateCode.toLowerCase();
    return withBase(`/s/${slug}/d/${districtSlug}`);
  },
  ```
  The `districtSlug` is opaque to the builder (caller supplies the already-slugified district name, derived from `display_name` via `slug.ts:slugify()` at the data-layer boundary, mirroring how `acSlug()` is the boundary for AC slugs). No reverse-resolver in U2a; the page resolves the slug -> LGD district id via `loadAllDistrictEntities()` in U2b's integration row.

- `frontend/src/main.ts`: register the route
  ```ts
  { pattern: "/s/:state/d/:district", component: District,
    parse: ({ state, district }) => ({ state, district_slug: district }) },
  ```
  Plus the `/sd/:subdistrict` shape reserved (binding to `NotFound` until a later chunk):
  ```ts
  { pattern: "/sd/:subdistrict", component: NotFound,
    parse: ({ subdistrict }) => ({ path: `/sd/${subdistrict}` }) },
  ```
  Order is not load-bearing (the new patterns are segment-count-distinct from every existing route).

- `frontend/src/routes/District.svelte` (new, ~60 LOC): resolve the LGD district by slug + parent state code, render `<state> > <district>` heading, a one-paragraph placeholder body, and a `<GeoBreadcrumb />` mount (added in U2b). Calls `loadAllDistrictEntities()` (view-models/districts.ts already national-keyed by LGD code); slug -> district row by `slugify(display_name) === district_slug && parent_entity_id === 'IN-' + state_code`. Renders "District not found" on no-match (one `.catch` arm; no DuckDB retry loop).

- `frontend/src/lib/url.test.ts`: 4 new assertions
  - `url.district("S22", "coimbatore")` matches `/^\/s\/[a-z0-9-]+\/d\/coimbatore$/`
  - `url.district("tamil-nadu", "coimbatore")` slug-passthrough -> `/s/tamil-nadu/d/coimbatore`
  - negative: never emits uppercase ECI in district URL (`url.district("S22", ...)` regex `not /\/S\d{2}\b/`)
  - negative: never emits Hive partition form (`not /in_s/`)
  - negative: never emits legacy `/state/` shape

- `frontend/src/lib/url.ts` JSDoc on `url.district` documents the dual-input rule + the LGD-derived-slug contract.

**Gate**: build + vitest (`url.test.ts` 4 new assertions pass) + svelte-check.

**Risk**: low. URL grammar is purely additive (no existing URL changes), new route component is leaf, no data writes.

### U2b `GeoBreadcrumb.svelte` + integration

**Files (~7, ~250 LOC including tests):**

- `frontend/src/lib/GeoBreadcrumb.svelte` (new, ~140 LOC):
  - Reads `route.params` from `router.svelte.ts` to build the crumb chain from the URL alone (no extra fetch; uses what the page already resolved).
  - `India` crumb -> `url.home()`. `<state-name>` crumb -> `url.state(<eci-code>)`. `<district-name>` crumb -> `url.district(<eci-code>, <district-slug>)`. `<ac-name>` crumb -> `url.ac(<eci-code>, eci_no, name, event?)`.
  - State name resolves via `states.name(<eci-code>)` (already keyed to display, falls back to the code while reference data loads).
  - Sticky positioning: `class="sticky top-12 lg:top-0 z-20"` (under the mobile app bar, beneath the desktop static rail).
  - Glass styling: `class="bg-surface/80 backdrop-blur border-b border-line"`.
  - Trailing `v` sibling-jump button: opens a popover menu of peer entities at the current grain (e.g. on `/s/tamil-nadu/d/<x>`, the menu lists peer districts in Tamil Nadu). Sibling-jump uses the same view-model loader the page itself uses (`loadAllDistrictEntities()` for districts; `fetchConstituencies()` for ACs).
  - Render is reactive on `route.params` so client-side navigation rebuilds the chain without re-mounting.

- `frontend/src/lib/GeoBreadcrumb.test.ts` (new, ~110 LOC): vitest unit tests
  - render India alone (`/` route): one crumb, "India", no link (it's the current page); no trailing `v` jump (root has no siblings).
  - render India > Tamil Nadu (`/s/tamil-nadu`): two crumbs, "India" link to `/`, "Tamil Nadu" current.
  - render India > Tamil Nadu > AC: three crumbs, ascend links correct.
  - render India > Tamil Nadu > District: three crumbs, district crumb href via `url.district()`.
  - sibling-jump menu emits one `<a>` per peer at the current grain.

- Integration: `<GeoBreadcrumb />` mount in 5 route files (`Home.svelte`, `StateOverview.svelte`, `StateTopic.svelte`, `Constituency.svelte`, `District.svelte`). Each is one import + one tag placement near the top of the route's main column. No props (the component reads `route.params` itself).

**Gate**: build + vitest (`GeoBreadcrumb.test.ts` all cases pass) + svelte-check + in-browser smoke per CLAUDE.md section 13: open `/`, `/s/tamil-nadu`, `/s/tamil-nadu/ac/167-mylapore`, `/s/tamil-nadu/t/fiscal`, `/s/tamil-nadu/d/<known-district-slug>`; confirm the breadcrumb renders, ascend links work, no new console errors.

**Risk**: moderate. The component touches 5 route files; the sibling-jump menu has the most surface area. Risk mitigation: if sibling-jump turns out to need a separate data fetch the route doesn't already do, ship the menu collapsed by default + open-on-click triggers the fetch (lazy, no first-paint cost).

**Shipped scope (2026-06-05)**: U2b ships the ascend-only crumb chain + sticky/glass styling + the 5-route integration + the chevron-right glyph (added to the icon registry per parent plan section 21.10's icons-in-public layout). The trailing `v` sibling-jump menu is DEFERRED to a follow-up sub-row (U2b.2 if minted, else folded into U2c) per the user's "don't over-engineer" mandate and the stop-and-surface trigger above: the popover needs a data fetch the route does not already do (peer enumeration at the current grain), the latency profile is unknown without first-fetch instrumentation, and shipping a half-coverage popover hurts citizen trust more than waiting. The breadcrumb's chain + ascend behaviour is the load-bearing primary-nav spine; the popover is an enhancement that lifts cleanly later.

### U2c LeftRail re-cluster (same-side fix + glass app bar + spring drawer + token migration + ballot-motif retone + `build <sha>` footer)

**Files (~5, ~180 LOC delta):**

- `frontend/src/app-tokens.css`: add
  ```css
  --brand-saffron: #d97706;
  --brand-green: #15803d;
  --brand-chakra: #000080;
  --app-bar-bg: rgb(255 255 255 / 0.80);
  ```
  The three brand-hex literals were chosen in U1's wordmark work for WCAG AA against the LeftRail wordmark; U2c just gives them a token home.

- `frontend/tailwind.config.js`: mirror the 3 brand colour tokens under `theme.extend.colors` so `text-brand-saffron`, `text-brand-green`, `text-brand-chakra` resolve. `--app-bar-bg` is consumed directly in CSS (no Tailwind mirror) since it carries an alpha channel and the Tailwind opacity utilities would be lossy.

- `frontend/src/contracts/app-tokens.test.ts`: bump the token-count assertion. Today (post-U1) the test asserts 9 colour + 4 type-family + 8 type-scale + 1 tabular + 4 radius + 3 elevation + 5 motion = 34. U2c adds 3 brand colour tokens + 1 surface token, all in the colour family: 12 + 1 = 13 colour total. New total: 38. The `--app-bar-bg` is documented as a glass-surface token (exempt-set candidate if it ends up applied only in CSS; the drift test verifies whichever decision lands).

- `frontend/src/lib/LeftRail.svelte`:
  - Inline `style="background: #d97706"` etc. -> `class="text-brand-saffron"` (or equivalent Tailwind utility).
  - Wordmark `font-family: "Outfit", ui-sans-serif, system-ui, sans-serif` -> `font-family: var(--font-yen-display)` (already maps to Outfit via U1.1).
  - Mobile cluster: brand + `[=]` LEFT, `[search]` top-right; drawer slides from LEFT with `var(--ease-spring)` + `var(--dur)` (matches the "same-side fix" rule from parent section 21.8).
  - Glass app bar: `class="bg-app-bar-bg backdrop-blur border-b border-line"` (the existing `bg-white border-b border-slate-200` on the mobile header element becomes the glass variant).
  - `build <sha>` footer line: a small `text-[10px] text-ink-muted` line in the footer that renders `import.meta.env.VITE_BUILD_SHA` (set via `vite.config.ts` define block from `git rev-parse --short HEAD` at build time; falls back to `dev` in development).

- `frontend/src/app.css`: retone the ballot-motif `stroke='%23475569'` data-URL background. Since CSS vars do not resolve inside `url(data:...)`, the inline hex stays - the U2c receipt is the explicit comment pointing at `--surface-sunken` semantics so a future agent re-tuning the surface ramp updates both in lockstep.

- `frontend/vite.config.ts`: add `define: { 'import.meta.env.VITE_BUILD_SHA': JSON.stringify(process.env.GIT_SHA || 'dev') }` (or equivalent; the precise mechanism is one of {env var injected by CI, `vite-plugin-version-mark`, inline `child_process.execSync('git rev-parse --short HEAD').toString().trim()`}).

**Gate**: build (no token-count regression) + vitest (`app-tokens.test.ts` reflects +4 tokens) + svelte-check + in-browser smoke per CLAUDE.md section 13: open `/` mobile-viewport (resize to <768px), confirm brand + `[=]` are on the LEFT, `[search]` placeholder on the right, drawer slides from the LEFT with the spring easing; open `/` desktop-viewport, confirm the static rail still renders with the brand wordmark intact; confirm `build <sha>` line in the footer; confirm the LeftRail brand hex literals are gone (`grep -rn "#d97706\|#15803d\|#000080" frontend/src/lib/LeftRail.svelte` returns zero matches).

**Risk**: moderate. LeftRail is touched on every route. The same-side fix is the most visible delta; ensuring the desktop static rail is NOT regressed is the load-bearing in-browser smoke.

### U2d closure

- Distillation home: `docs/architecture/frontend/design-system.md`. Flip the per-component-migration U2 row from `TODO` to `MERGED #N`. Add the four new colour tokens to the token map. Add one paragraph in a new `GeoBreadcrumb + glass app bar` section under the per-component migration table summarising the surface (sticky, glass, tap-to-ascend, sibling-jump menu, mounted on 5 routes).
- Parent ledger row U2 flips from `DEFERRED-TO-SUBPLAN` -> `MERGED`, stamped with U2a..U2d PR#s.
- `git mv TODO/20260605-u2-breadcrumb-drawer-district-subplan.md docs/archive/plans/20260605-u2-breadcrumb-drawer-district-subplan.md` and inbound-link rewrites (parent ledger forwarding pointer is the only inbound).

**Gate**: docs-review (no runtime change); admin-merge at vitest + build green per docs-only stamp-PR doctrine (precedent: U1.4 PR #720 + the D-DOC3.4 stamp PR #735).

---

## Parallel-safety

- **U2a** is purely additive on the URL grammar: a new builder, two new routes, a new leaf component. No existing URL changes, no test of existing URL grammar breaks. Other tracks (B*, D*, U4, U5, F*) may proceed.
- **U2b** is purely additive on the chrome: the `<GeoBreadcrumb />` mount sits ABOVE each route's existing content, no existing component is moved or removed. The breadcrumb component itself reads route params and is render-only. Other tracks may proceed.
- **U2c** touches LeftRail (every-route surface) but is purely token-migration + style-additive: every Tailwind utility class change reads through tokens defined in `app-tokens.css`; no Tailwind default is redefined (additive rule, parent section 23.5). The drift contract (`app-tokens.test.ts`) catches any token-layer regression at unit-test time.
- **U2d** is doc-only.

---

## Stop-and-surface triggers (CLAUDE.md section 10)

- If U2a's slug-derivation rule conflicts with an existing `taxonomy/entities.json` district `display_name` -> `slugify()` collision in any state (two districts with the same slug), STOP and surface a per-state list of collisions. The likely fix is to append the LGD district numeric code as a disambiguator (`coimbatore-567`) in the slug; that is a contract change requiring user sign-off.
- If U2b's sibling-jump menu requires a data fetch the route does not already do AND the fetch latency pushes the breadcrumb's first paint past the rest of the page (visible content-jank), STOP and ship the menu collapsed by default (open-on-click triggers the fetch) so first-paint is unaffected.
- If U2c's `build <sha>` injection requires a build-system change (new Vite plugin, CI env var), STOP and surface the mechanism in the U2c PR body for review before shipping.

---

## Ship loop (per /memories/lessons.md precedents)

Each U2x row follows the standard ship loop:

1. Branch from main, flip own row IN-FLIGHT in commit 1 with `_pending_`, commit + push.
2. `gh pr create --body-file .tmp_pr_body.md` (use `--body-file` for multi-line bodies; `--body` inline trips on `-` tokens).
3. Stamp PR# in row via commit 2 (replace `_pending_` -> `#NNN`), push.
4. Wait for vitest + build green (~12-15 min). Playwright optional for docs-only or runtime-identical PRs.
5. `gh pr merge <N> --squash --admin --delete-branch`.
6. Post-merge cleanup per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md).
7. Open a small stamp PR to flip the now-merged row from IN-FLIGHT to MERGED if needed (catch-up).

Total session time per U2x row: ~50-70 min (matches U1.1 #714 / U1.2 #716 / U1.3 #718 / U1.4 #720 cadence).

---

## See also

- [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) sections 21.8 + 23.5 - the design-spec source.
- [docs/archive/plans/20260604-u1-tokens-fonts-subplan.md](../docs/archive/plans/20260604-u1-tokens-fonts-subplan.md) - the U1 precedent (4 sub-rows, same shape).
- [docs/architecture/frontend/design-system.md](../docs/architecture/frontend/design-system.md) - the distillation home for U2's per-component migration row.
- [docs/architecture/frontend/url-grammar.md](../docs/architecture/frontend/url-grammar.md) - the URL grammar contract (ADR-0028 / ADR-0037 / ADR-0048 / ADR-0050 receipts; U2a extends with the district node).
- [CLAUDE.md](../CLAUDE.md) section 13 (UI verification) + Holy Law #1 (static-first) + section 10 anti-patterns (no hardcoding, no mocks).
