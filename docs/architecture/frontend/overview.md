# Frontend Overview

**Last Updated**: 2026-05-10 (revision: chart visual polish — donut + bar gradients, sweep-in, majority marker)

The frontend is a static Svelte 5 + Vite + Tailwind + d3 bundle that renders election artifacts from [`datasets/`](../../../datasets/). It has no production backend (CLAUDE.md Holy Law #1) and never commits data files (§4). Built with `bun`. Routed with a tiny custom hash router.

How the bundle finds its data is covered in [data loading](data-loading.md). The two heavy interactive surfaces are documented separately:

- [Psephlab](psephlab.md) — what-if simulator (vote mutations + pluggable counting rules).
- [Map](map.md) — MapLibre GL cartography (state / district / AC choropleths, future socio-economic overlays).

The dev/ops surface is its own application, not part of the public bundle: see [admin overview](../admin/overview.md).

This page covers personas, information architecture, the visualization catalog, the stack, and routing.

## Personas

The product serves four distinct personas. Heavy code lives behind the first two; the latter two are mostly the same screens with simpler entry paths.

| Persona | Goal | Primary surface |
| --- | --- | --- |
| **Citizen** *(default landing)* | "Who won where? Show me my state on a map." | Explore — India map → state → AC drilldown |
| **Strategist / Psephologist** | "If 3% had swung, who governs? What if we'd used STV instead of FPTP?" | Psephlab |
| **Journalist / Analyst** | "Actuals, margins, swings vs prior election, screenshot-friendly" | Explore (read-only views) |
| **Data Admin** *(internal)* | "What data do we have? Is it valid? Re-run the pipeline. Patch a typo." | Admin app (separate, never deployed publicly) |

Default landing is the **Citizen** path: India choropleth at `#/`, with a tooltip on each state showing the leading party and a link into the state Explore view. The Strategist enters the same way and clicks **Psephlab** in the left rail once they've chosen a scope.

## Information architecture

Layout is **tools-in-rail + scope picker on top** (Azure DevOps style). The left rail holds tools; the scope picker pinned at the top of the rail holds the current `Country → State → Election` selection and persists when the user switches tools.

```
┌─────────────────┬───────────────────────────────────────────┐
│ ◯ India ▾       │                                           │
│   ◯ TN  ▾       │                                           │
│   ◯ AcGen 2026 ▾│                                           │
├─────────────────┤             <active tool canvas>          │
│ ▣ Explore       │                                           │
│ ▣ Psephlab      │                                           │
│ ▣ Compare       │                                           │
│ ▣ Settings      │                                           │
└─────────────────┴───────────────────────────────────────────┘
```

Tools available depend on the scope:

| Scope | Explore | Psephlab | Compare |
| --- | :---: | :---: | :---: |
| Country (no state chosen) | ✓ (India choropleth) | – | ✓ (state-vs-state seat tallies) |
| State + Election | ✓ (state map + party totals) | ✓ | ✓ (this election vs previous) |
| State + Election + AC | ✓ (per-AC top-N + NOTA) | ✓ (single-AC mode) | ✓ |

The mobile breakpoint collapses the rail to a hamburger; the scope picker becomes a sticky header.

### IA rationale

- **Why tools-in-rail, not geography-in-rail.** A strategist switching from "explore actuals" to "run a swing" should not lose their scope. Putting tools in the rail and scope at the top makes scope a property of the session, not a property of the navigation.
- **Why a scope picker, not URL-only navigation.** The hash router (below) already encodes scope, but a visible picker is needed because Psephlab and Compare both *operate on a chosen scope* — the user needs to see and change it without typing in the address bar.
- **Why no separate Citizen / Strategist / Admin "modes".** Modes hide features and force a choice the user shouldn't have to make. Admin is split out because it ships in a separate bundle (different deployment story); Citizen vs Strategist is just "which tool did you click first".

### IA — alternatives considered

- **Geography-first rail with contextual tools.** Cleaner mental model for the Citizen, but penalises the Strategist who switches scopes constantly. Rejected.
- **Two-rail layout (geography left, tools top).** Used by some BI tools. Rejected: too much chrome for what is fundamentally a focused analysis app.
- **Single-mode landing with hidden Psephlab.** Rejected — Psephlab is a flagship feature, not a hidden one.

## Visualization catalog

All views reuse a small set of components from `src/lib/`. The catalog is fixed; new views compose existing pieces rather than introducing new chart libraries.

| Component | Used by | Notes |
| --- | --- | --- |
| `maplibre/IndiaMap.svelte` | Home (country choropleth) | MapLibre GL country-level state polygons; party hue per leading-party tally. See [map](map.md). |
| `maplibre/StateAcMap.svelte` | StateOverview, Constituency | MapLibre GL state-level AC polygons with district overlay; selection state binds to the `?ac=...` URL param. |
| `PartyBar.svelte` | StateOverview, Party, Psephlab | Animated horizontal bar of seat tally. |
| `SeatDonut.svelte` | StateOverview, Party | Donut of vote share, total in centre. |
| `ParliamentArc.svelte` | Psephlab, Compare | Auto-rowed seat-dot semicircle, majority midline + legend. |
| `SwingSankey.svelte` | Psephlab | Approximate party-to-party vote flow between actuals and scenario. Loser-drop ÷ gainer-share apportionment, labelled as approximate in the chart caption. |
| `MarginHistogram.svelte` | StateOverview | Margin-of-victory distribution per election. |
| `AcStackedBar.svelte` | Constituency | Top-5 + NOTA + collapsed Others, per AC. |

Animations use **`svelte/motion`** spring physics (rich animation budget per design): bars settle, map fills tween between scenarios, parliament dots stagger in. d3 stays as a math library for scales and arc generators; chart DOM is authored in Svelte.

### Color scheme

Default party colors are canonical (DMK red, AIADMK twin-leaves green, BJP saffron, INC blue, etc.) and ship as `frontend/src/lib/colors/parties.default.ts` keyed by ECI party code. Users override per party from Settings; overrides persist in `localStorage` under `yen-gov:party-colors`. The override map is also embedded in shared scenario URLs so a strategist's screenshot matches what their colleague sees.

This is intentionally NOT a `datasets/reference/` artifact: party color is presentation, not provenance. Pulling it into a contract surface would force every dataset reader to depend on a presentation choice.

### Implementation notes (Phase 1e)

The rail and scope picker landed as three modules under `frontend/src/lib/`:

- `scope.svelte.ts` — module-scoped rune store for the `(country, state, election)` tuple. `country` is hard-coded (`IN`); `election` lives in `localStorage` (`yen-gov:scope:election`); `state` is **derived from the URL path** (regex match on `/s/:state` or `/lab/:state/...`) rather than stored, so deep links and back/forward keep the picker in sync without any subscription plumbing.
- `ScopePicker.svelte` — three native `<select>`s, each labelled. Country and Election render disabled today (one option each); the selects are still present so the picker UI stays uniform when more options arrive. Changing State navigates the router (`location.hash = "#/s/<code>"` or `"#/"` for All India). Selecting "With data" / "Other states" optgroups makes the difference visible to the user without dropping the long tail.
- `LeftRail.svelte` — desktop layout is a 240 px sticky sidebar with brand → ScopePicker → tools → footer; below the **`lg` breakpoint (1024 px)** the rail collapses to a top header + slide-in drawer. The breakpoint was raised from `md` (768 px) to `lg` after a regression where mid-width laptops and tablets had the static rail steal 240 px from the page content, overlapping the Psephlab grid (which only switches to its two-column layout at `lg`). Picking the same threshold for both means the rail and the canvas appear together. Tools that require a state (`Analyze Trends`, `Compare`, `Psephlab`) render as disabled non-links with a `title=` tooltip explaining why, instead of disappearing — the user learns the rule.

  **Brand wordmark.** The mark is `Yen ☸ Gov` set in **Outfit 300** (Google Fonts), with the Ashoka Chakra (24 navy-blue spokes, per the [Indian flag specification](https://en.wikipedia.org/wiki/Ashoka_Chakra)) replacing the previous `-` hyphen. The chakra is built inline as SVG so it scales with the cap-height and inherits its color via `currentColor`. Word colors are darkened-saffron (`#c2410c`) and darkened-flag-green (`#166534`) — chosen for AA contrast on white while still reading as a quiet tricolor nod. Rationale: the previous plain-bold `yen-gov` mark was indistinguishable from generic dev-tool branding; the Indian-flag motif anchors the product's domain on first glance without being literal. The hyphen was dropped at the user's request — typographically the chakra acts as the separator.

  **Tab labels.** "Analyze Trends" replaces the earlier "SQL" label so the rail reads as **what the tool lets you do**, not the technology behind it. Citizens shouldn't need to know SQLite + sql.js is the substrate.

  **Footer.** "Yen Gov · For an informed India" replaces "yen-gov · Indian election data" — the project's intended scope (electoral data plus social/economic/welfare layers over time) is broader than just elections, and the tagline now reflects that.

`main.ts` mounts the rail once into `#rail` and lets the router replace `#route` on every navigation, identical to the previous TopNav setup. The interim TopNav.svelte from Phase 1a was removed in the same commit.

## Phasing

Build order, smallest shippable slice first:

| Phase | Status | Scope | Ships |
| --- | --- | --- | --- |
| 1 | ✅ shipped | **Explore** for TN + AS + KL + WB (May 2026) — India choropleth landing, state map (district + AC), per-AC top-N, party color overrides | `IndiaMap`, `StateAcMap`, `MarginHistogram`, `AcStackedBar`, `LeftRail`, `ScopePicker` |
| 2 | ✅ shipped | **Psephlab** v1 — per-AC manual swing, statewide swing, threshold drop, ad-hoc party-bag, FPTP counting, scenario-as-URL | [psephlab.md](psephlab.md); `ParliamentArc`, `SwingSankey`; `lib/psephlab/` engine |
| 3 | ✅ shipped | **Compare** — split-screen scenario-vs-scenario (paste two Psephlab share URLs into A and B; middle column shows per-party seat Δ); election-vs-election empty-states until prior-event datasets land | [compare.md](compare.md); `Compare.svelte` route only — no extra `lib/diff.ts`, the per-party union is computed inline |
| 4 | ⏳ in progress | **Admin app** — separate `admin/` Svelte app + FastAPI; v0 ships Inventory panel; Schemas / Pipeline / Patches follow | See [admin overview](../admin/overview.md) |
| 5 | deferred | Additional **counting-rule plugins** (IRV, STV, D'Hondt, Sainte-Laguë), socio-economic map overlays | Documented in [psephlab](psephlab.md) and [map](map.md) but not implemented in v1 |

Each phase is independently shippable and reviewable.

## Stack

| Concern         | Choice                                |
| --------------- | ------------------------------------- |
| Framework       | Svelte 5 (runes)                      |
| Bundler         | Vite 6 + `@sveltejs/vite-plugin-svelte` |
| Styling         | Tailwind 3 + PostCSS                  |
| Charts          | d3 v7 (used as SVG-math library)      |
| Package manager | bun                                   |
| Routing         | custom ~50-line hash router           |
| Dev data access | Vite middleware → `../datasets` at `/data` (see [data loading](data-loading.md)) |

## Layout

```
frontend/
├── package.json          bun project; deps pinned
├── vite.config.ts        registers serveDatasets() middleware; sets browser export conditions
├── svelte.config.js
├── tailwind.config.js / postcss.config.js
├── tsconfig.json         strict TS
├── index.html            single mount point: <div id="app">
└── src/
    ├── main.ts                 Svelte 5 mount() entry; mounts LeftRail + startRouter
    ├── app.css                 Tailwind directives only
    ├── lib/
    │   ├── router.svelte.ts    hash router (~80 lines, rune-backed `route` store)
    │   ├── scope.svelte.ts     scope rune store (country/state/election)
    │   ├── ScopePicker.svelte  three native <select>s for the rail
    │   ├── LeftRail.svelte     persistent rail (desktop) / drawer (mobile)
    │   ├── data.ts             typed views over datasets/ schemas + fetchers
    │   ├── sql.ts              cached sql.js Database per (event, state)
    │   ├── colors/             party color store (defaults + localStorage overrides)
    │   ├── maplibre/           IndiaMap, StateAcMap, sources helpers
    │   ├── psephlab/           types, engine, rules/, mutations/, scenario codec
    │   ├── PartyBar.svelte     horizontal bar of seats by party
    │   ├── SeatDonut.svelte    d3 pie/arc donut, total in centre
    │   ├── ParliamentArc.svelte
    │   ├── SwingSankey.svelte
    │   ├── MarginHistogram.svelte
    │   └── AcStackedBar.svelte
    └── routes/
        ├── Home.svelte         /        — country choropleth landing
        ├── StateOverview.svelte /s/:state-slug
        ├── Constituency.svelte  /s/:state-slug/ac/:ac-slug   (e.g. 167-mylapore)
        ├── Party.svelte         /s/:state-slug/party/:party-slug   (e.g. dmk-d34)
        ├── Explore.svelte       /s/:state-slug/explore  (sql.js)
        ├── Psephlab.svelte      /lab/:state-slug/:event
        ├── Settings.svelte      /settings
        └── NotFound.svelte
```

The split between page-level components (`routes/`) and reusable presentational components (`lib/*.svelte`) is the only structural rule.

## Reactivity rules (Svelte 5 specifics)

- Type annotations go on the `let` binding, never on the `$state(...)` call: `let x: T | null = $state(null)`. The form `let x = $state<T | null>(null)` parses but does not register the rune (caught during scaffolding).
- Avoid bare local identifiers named `state` — they trigger Svelte's store-prefix detection (`$state` rune ambiguity). Use `state_code` etc.
- Use `$derived` for any value computed from state; never recompute in the template.
- `$props()` is the only sanctioned way to receive component inputs.

## Build and run

```bash
cd frontend
bun install
bun run dev      # http://localhost:5173, /data/* served from ../datasets
bun run build    # emits dist/
```

The deploy step ships `dist/` together with `datasets/` such that `/data/...` URLs resolve at the deployed origin — see [data loading > production placement](data-loading.md#production-placement).

## Stack rationale

Constraints driving the choices:

- **Static-only output.** Rules out anything requiring a server runtime (Next.js SSR, SvelteKit adapter-node).
- **Schema-shaped data.** The bundle pulls `result.summary.json` etc. and presents them; no GraphQL, no client-side ORM.
- **Small surface area.** First slice is one page (state overview); future slices add more pages, not more frameworks.
- **Operator is a Python-first developer.** JS toolchain should be predictable with one obvious package manager.

Picked: Svelte 5 (small compiled output, explicit reactivity), Vite 6 (fast dev, plugin ecosystem), Tailwind 3 (utility-only, no custom CSS framework), d3 v7 (used as a *library* for arc/pie/scale math — SVG is authored directly in Svelte), bun (single binary, fast install, one lockfile).

Specifics worth knowing:

- d3 ships ~30 kB gzipped. Acceptable for the first slice; if the bundle grows past ~200 kB gzipped overall we revisit per-module imports.
- bun is the only supported package manager. `npm install` / `pnpm install` are not run in CI; contributors install bun.

### Stack — alternatives considered

- **SvelteKit.** Rejected. Adds router, SSR scaffolding, adapter complexity that buys nothing for a static one-route bundle today. Can adopt later if routing demands it.
- **React + Vite.** Viable, but Svelte's reactivity model maps more directly to "render this JSON" without state-management ceremony, and the compiled output is smaller for chart-heavy pages.
- **Echarts / Chart.js.** Rejected for the first slice. They bundle their own SVG/canvas renderer and theme system; d3 lets us compose minimal SVG that matches Tailwind classes directly.
- **npm or pnpm.** Viable. bun chosen for install speed and a single-binary toolchain; switching is a lockfile regen if it ever becomes a constraint.

## History routing with slug URLs (custom, no router lib)

URLs use the standard History API (clean paths, no `#`). They look like:

- `/`                                                — country index (India choropleth landing)
- `/s/:state-slug`                                   — state Explore view (map + party totals)
- `/s/:state-slug/ac/:ac-slug`                       — per-constituency result (e.g. `/s/tamil-nadu/ac/167-mylapore`)
- `/s/:state-slug/party/:party-slug`                 — per-party detail (e.g. `/s/tamil-nadu/party/dmk-d34`)
- `/s/:state-slug/explore`                           — ad-hoc SQL surface (sql.js, see [data loading](data-loading.md))
- `/lab/:state-slug/:event`                          — Psephlab for a chosen scope
- `/lab/:state-slug/:event?s=<scenario>`             — Psephlab with a scenario loaded from the query string
- `/settings`                                        — color overrides, layout preferences (localStorage-backed)
- `/about?section=<id>`                              — About page, optionally scrolled to a section
- `/compare/:state-slug/:event?mode=scn|elec&a=<scenario>&b=<scenario>&eventb=<event>` — [Compare.svelte](../../../frontend/src/routes/Compare.svelte). `mode=scn` (default): two Psephlab scenarios on the same actuals; `mode=elec`: same state across two events.

On project Pages the deploy base is `/yen-gov/`, so all paths above are prefixed accordingly at runtime via `import.meta.env.BASE_URL` — see [`frontend/src/lib/url.ts`](../../../frontend/src/lib/url.ts).

### Slugs

Path identifiers are human-readable slugs, not raw codes. Helpers in [`frontend/src/lib/slug.ts`](../../../frontend/src/lib/slug.ts) build:

- **State slug** — lowercased state name (e.g. `tamil-nadu`). Resolved back to the ECI code via [`states.codeFromSlug()`](../../../frontend/src/lib/states.svelte.ts), which accepts both the slug AND the raw ECI code (`S22`) for backwards compatibility with old bookmarks.
- **AC slug** — `<eci_no>-<name-slug>` (e.g. `167-mylapore`). Parsed via `parseAcSlug()`; only the leading number is authoritative — the name is cosmetic and a wrong/stale name still resolves the right AC.
- **Party slug** — `<short-name-slug>-<eci_code>` (e.g. `dmk-d34`). Parsed by splitting on the LAST `-`; the trailing token is the ECI code. Falls back to short-name match if the suffix is missing or unknown.

All URL construction goes through [`frontend/src/lib/url.ts`](../../../frontend/src/lib/url.ts) (`url.home()`, `url.state(code)`, `url.ac(code, eci_no, name)`, `url.party(code, party_eci, short)`, etc.). Programmatic navigation uses the same module's `navigate(path)` which calls `history.pushState` and dispatches `popstate` for the router to pick up.

[`frontend/src/lib/router.svelte.ts`](../../../frontend/src/lib/router.svelte.ts) exposes a `route` rune (`$state`-based store) parsed from `window.location.pathname` (after stripping the deploy base) and updated on `popstate`. A document-level `click` handler intercepts plain in-app `<a>` clicks and routes them through `navigate()`; external/blank-target/modifier-key clicks pass through.

`currentPath()` ignores `location.search` for pattern matching, so Psephlab and Compare can attach `?s=...` / `?a=&b=` query state without affecting routing.

### GitHub Pages 404.html SPA shim

GitHub Pages is a static host with no SPA awareness, so a fresh request to `/yen-gov/s/tamil-nadu/ac/167-mylapore` would 404. Pages does serve [`frontend/public/404.html`](../../../frontend/public/404.html) for any unknown path under the base — our shim captures the requested path into `sessionStorage["yg:redirect"]`, then bounces to the deploy base. The boot script at the top of [`frontend/index.html`](../../../frontend/index.html) reads it back and calls `history.replaceState` BEFORE the SPA initialises, so the router sees the real path on first render. The base path is templated into 404.html at build time by `template404Plugin` in [`frontend/vite.config.ts`](../../../frontend/vite.config.ts).

No router library is added. The current need (~9 routes, no nesting, no guards, no transitions) does not justify a dependency.

### Routing rationale

- **Clean, shareable URLs.** Slug paths read like a URL; ECI codes (`S22`, `D34`) live only as URL-resolution detail.
- **Backwards-compatible.** `states.codeFromSlug()` accepts old code-only URLs (`/s/S22`); the AC parser is tolerant of name drift.
- **Single source of truth.** `lib/url.ts` builds every in-app URL. There is no string concatenation of route paths anywhere else.
- ~80 lines of routing code, fully readable. No hidden behaviour, no version churn from an external lib.

Acknowledged costs:

- The 404.html shim is a one-frame redirect on first deep-link load. Network panels show the 404 momentarily; link previews on platforms that don't run JS will see the redirect HTML rather than the destination's metadata.
- Custom code = our problem to maintain. Mitigated by the trivial scope (parse → match → render, plus a 30-line shim).

### Routing — alternatives considered

- **`svelte-routing` / `svelte-spa-router`.** Viable, but adds a dependency and an opinion (slot-based routing, named params, etc.) for a small route table. Rejected on YAGNI.
- **SvelteKit with adapter-static.** Gives us file-system routing and SSG. Rejected because (a) Holy Law #1 forbids assuming any backend, and adapter-static is a heavy migration path; (b) we already have a working Vite + plain-Svelte setup; (c) routing is the only thing SvelteKit would buy us right now.
- **Hash routing (previous design).** What we shipped first. Replaced because users expected shareable clean URLs, the `#/` was confusing in screenshots, and the 404.html shim is well-understood (used by Create-React-App, rafgraph/spa-github-pages, etc.).

## Discoverability & deselect (UX audit, May 2026)

These rules apply to every chart that lists parties (`PartyBar`, `SeatDonut`, `ParliamentArc`).

### Always show every party — no client-side threshold

Earlier the State Overview's "Seats by party" bar dropped parties with `seats_won == 0 && vote_share_pct < 1.0`. That silently erased fringe-but-noisy parties (e.g. TVK in TN, ~30 % vote share but 0 seats), which is exactly the kind of "interesting null" a results product must surface, not hide.

The rule now: the route owns the sort, the chart shows whatever it's given. Filtering is opt-in via search inputs, not implicit.

### Click-to-mute parties

Clicking a party row (`PartyBar`), donut slice (`SeatDonut`), or legend chip (`ParliamentArc`) toggles that party in a `hidden_parties: Set<string>`. Hidden parties render at low opacity — they are NOT removed, and the underlying seats / vote share / paint scaling do NOT recompute. This is by design: we are visualising one ground-truth allocation; muting is a viewing aid, not a re-tally. The donut centre swaps to "X of Y seats" so the user always sees how much of the chamber they've muted.

The mute set lives on the parent route, not the child component, so all three charts on State Overview stay in sync. The set resets when:

- the loaded `state_code` changes (TVK in TN ≠ TVK in KL — keys are reused),
- the user clicks "Show all".

In **Psephlab** there's an additional rule: the mute set resets the moment a scenario gains its first mutation (`scenario.mutations.length` 0 → ≥1). Rationale: scenarios are about what-ifs, and "did I hide them or did the mutation erase them?" is a lousy mental model. Once mutations exist the user has opted into the experiment; further mutations don't reset (they're refinements).

The mute key is `party_eci_code ?? party_short` — the ECI code where present, falling back to the display short name for parties whose ECI code is null in our dataset. This matches what the chart components already use as their list keys.

### Search inputs (State Overview)

Two `<input type="search">` fields on State Overview — one above the Parties grid, one above the district list. Both are pure local `$state`, case-insensitive substring match.

- **Party search** filters on `party_short`, `party_full`, and `party_eci_code` so users can find a party by short name, long name, or ECI code.
- **AC search** filters by name substring OR exact `eci_no` string match (so "167" jumps to AC 167). Districts with zero matches collapse out of the listing entirely.

Search and mute are intentionally orthogonal: search hides whole rows from the Parties grid; mute only dims the chart slices. They have separate UIs because they answer different questions ("does this party exist?" vs "I don't care about this party right now").

### MarginHistogram caption

The histogram caption was a single line ("234 constituencies · stacked by winning party"). Two complaints with that: (a) "margin of victory" needs explaining for non-experts; (b) screen readers had no way to associate the SVG with the explanation. The current caption is two sentences with `aria-describedby` pointing the SVG at it.

### Layout & motif

State Overview uses a `lg:grid-cols-[3fr_2fr]` top row (map left, donut + KPI cards stacked right). The "Seats by party" bar moved below that row to its own full-width section so wide bars and 0-seat parties have room. Routes use `max-w-screen-2xl` (was `max-w-5xl`/`6xl`) to use modern viewport widths; Psephlab keeps `max-w-6xl` because its sticky 360 px sidebar is laid out against that ceiling.

A subtle background motif (✓ ✗ ballot-box glyphs at opacity 0.035) lives in `body::before` via an inline-SVG `data:` URL. No party symbols (legal/perception risk on a results product) — just neutral electoral marks. Cards are opaque so the pattern only shows in the gutter regions and never reduces text contrast.

### Chart visual language (2026 polish)

The hero charts on State Overview (`SeatDonut` + `PartyBar`) carry a deliberate visual treatment so the page reads as a contemporary results dashboard, not a flat 2010-era listing:

- **Per-slice / per-bar gradients** (party color → ~55% brighter shade). Direction on the donut is rotated to each slice's mid-angle so the highlight sits on the outward face. The base hue stays dominant, so party identification doesn't suffer.
- **Padding + corner radius** on donut slices (`d3.arc().padAngle(0.012).cornerRadius(4)`) plus rounded-full pill bars for the bar chart. We hand-roll the cumulative-angle math (no `d3.pie`) because the chart sweep-in animates `endAngle` against a `tweened` `progress` 0→1.
- **Sweep-in entrance**: donut arcs grow on mount over ~950ms (cubicOut); the centre tally counts up via a separate ~600ms tween. Bars stagger their width transition by `min(i*35, 350)`ms so the bar list ripples in rather than slamming.
- **Soft drop shadow** (SVG `<filter>`, `feGaussianBlur` stdDev 1.6, alpha slope 0.28) and a 1-px white inter-slice stroke give the donut depth on white.
- **Leader pill** below the donut and a small dot beside the leader's bar row anchor the headline without a separate legend.
- **Majority signalling.** The donut shows a thin gold dashed outer ring (`#fbbf24`) only when the leading party has cleared half the chamber. The bar chart always shows a vertical dashed `Majority · N` line — the bar scale is `max(majority * 1.05, …seats_won)` so the marker is guaranteed inside the chart, and the visible *gap* between the top bar and the marker is the actual story in fragmented results (TN 2026: TVK at 108 vs majority at 117). The label flips from centred to right-anchored past 75% to avoid clipping the card edge.
- **KPI tiles** use a thin colored top accent + tinted background (slate / emerald / sky) and `tabular-nums` so numbers align across rows.

These treatments are presentation-only. Data inputs, accessibility roles, hidden-party semantics, and tooltip text are unchanged from the earlier flat versions.

## See also

- [Psephlab](psephlab.md) — what-if simulator design.
- [Map](map.md) — MapLibre GL cartography pipeline.
- [Admin overview](../admin/overview.md) — separate dev-only app + FastAPI.
- [Data loading](data-loading.md) — dev middleware, prod placement, `/explore` SQL.
- [Deployment](../deployment.md) — operator-level workflows.
- [Data flow](../data-flow.md) — system-level picture.
- CLAUDE.md §1 (static-first), §4 (layer rules).
