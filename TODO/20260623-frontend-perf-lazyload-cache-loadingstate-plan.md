# Frontend Perceived-Performance Plan - Lazy-Load, Caching, Loading-State

**Last Updated**: 2026-06-23
**Level**: 3-4 (structural, phased; one row touches a router-contract boundary - see ESCALATE)
**Authoring personas**: Jony (UI/UX) + Fowler (Engineering), in debate, converged. UX authority = Jony + Citizen; engineering-craft authority = Fowler (CLAUDE.md section 0a).

> This is an AUTHORED plan. It has NOT been implemented. Add it to context and say "implement it" to run the EXECUTION BLOCK below.

---

## Section 0 - Operating contract

### Why this plan exists

Three questions were asked about the citizen frontend (and the dev-only admin app):

1. Are we lazy-loading across the entire app?
2. Do we show "loading"/"fetching" - or meaningful contextual placeholders - while data loads?
3. Do we fetch-once + reuse the cache, instead of re-fetching every time?

The audited answers (every claim verified directly in code, not via summary):

| Question | Verdict today | Evidence |
| --- | --- | --- |
| Lazy-loading | **NO.** Zero intentional code-splitting. [frontend/src/main.ts](../frontend/src/main.ts) statically imports all ~28 routes; [frontend/vite.config.ts](../frontend/vite.config.ts) has no `manualChunks`. `prewarmDB()` boots ~5.2 MB DuckDB-WASM unconditionally on every page including `/about`. Only `@huggingface/transformers` is already lazy (yenask). `maplibre-gl` is a dead dependency (no importer). | [main.ts](../frontend/src/main.ts), [duckdb.ts](../frontend/src/lib/duckdb.ts#L290) |
| Loading-state | **INCONSISTENT.** Good on [StateOverview.svelte](../frontend/src/routes/StateOverview.svelte) (skeleton KPI grid), [TopicLanding.svelte](../frontend/src/routes/TopicLanding.svelte), [StateElection.svelte](../frontend/src/routes/StateElection.svelte) (panel-state machine). **Blank white page for 5-10s** (DuckDB cold start) on [Constituency.svelte](../frontend/src/routes/Constituency.svelte) (the reported `.../ac/tezu` URL), [District.svelte](../frontend/src/routes/District.svelte), [StateTopic.svelte](../frontend/src/routes/StateTopic.svelte). Static frozen-looking "Loading..." text on [StateSubRouter.svelte](../frontend/src/routes/StateSubRouter.svelte), [StateElectionsLanding.svelte](../frontend/src/routes/StateElectionsLanding.svelte), [AssemblyElections.svelte](../frontend/src/routes/AssemblyElections.svelte). Every map renders a **blank box** during load. | grep of `"loading"`, `animate-pulse`, `Skeleton` |
| Caching | **PARTIAL.** Cached (module-promise, fetch-once): manifest, [election-events.ts](../frontend/src/lib/election-events.ts), [governments.ts](../frontend/src/lib/governments.ts), [view-models/districts.ts](../frontend/src/lib/view-models/districts.ts), tile-layouts, yenask catalogue + model. **Re-fetched every call/mount**: [boundaries.ts](../frontend/src/lib/boundaries.ts) geometry (0.5-10 MB per state, re-downloaded on every map mount), [catalogue.ts](../frontend/src/lib/catalogue.ts), [grapher/catalogue.ts](../frontend/src/lib/grapher/catalogue.ts), [state-tiers.ts](../frontend/src/lib/state-tiers.ts), [canonical/csv-columns.ts](../frontend/src/lib/canonical/csv-columns.ts). DuckDB `query()` has **no result memo**. The router ([router.svelte.ts](../frontend/src/lib/router.svelte.ts)) does `innerHTML="" ; mount()` on every navigation -> full re-mount, every `onMount()` fetch re-runs (no keep-alive). No service worker; weak GitHub Pages HTTP caching. | [duckdb.ts](../frontend/src/lib/duckdb.ts#L562), [boundaries.ts](../frontend/src/lib/boundaries.ts#L318) |

The spine fact that makes every fix structural (not a band-aid, Holy Law #5): **the data corpus is immutable within a session.** It changes only on deploy, and a deploy changes the bundle hash and forces a full page reload, which resets all module state. So an in-session in-memory cache has a **zero staleness window by construction** - this is correct-by-construction, not a TTL hack.

### Hard-coded scope (in-scope rows)

Rows 1-7 in the Status Reckoner. Nothing else.

### Out of scope (do NOT smuggle in)

- **Service worker / PWA precache.** Real answer for instant repeat-load + offline, but the "stuck-on-stale-version" failure mode on GitHub Pages has no server-side kill-switch and is irreversible; for a civic-truth product, confidently serving stale data is worse than serving slow data honestly. DEFER. If ever revived it is a Level-4/5 design consultation whose FIRST deliverable is a tested versioned-SW kill-switch + `/data/*`-stays-network-first, BEFORE any precache logic.
- **Router keep-alive / component caching across navigation.** The `innerHTML="" ; mount()` full re-mount is the upstream cause of "every `onMount` refetches," but the Row 3-5 data caches capture ~90 percent of the felt cost (the network fetch + the scan) without touching the mount lifecycle. Keep-alive is a router-contract change (Gregor's boundary) with state-leak risk; Level 4. DEFER.
- **Per-chart d3 micro-splitting** (the ~140 KB the audit floated). d3 is used by nearly every citizen chart route; fragmenting it buys request-waterfall overhead for a citizen landing on a chart anyway. Speculative. REJECT.
- **Hand-authored vendor `manualChunks`.** Once the dev routes go lazy, Vite's default chunker pulls heavy deps out of the chrome initial load for free. Revisit ONLY on a measured `vite build` report showing a fat shared chunk. REJECT now.
- **A blanket memo on `query()`** keyed by SQL string. Unbounded key space, whitespace-fragile keys, band-aid over the router-remount structure. Cache at the bounded-id loader boundary instead (Row 5).
- **A generic configurable cache framework** (TTL / eviction). Staleness risk is zero under deploy-equals-reload; a framework is ceremony for a problem we do not have. REJECT.
- **Route-level lazy import for shared-dep routes** (Explore, Psephlab, CompareElections, CompareIndicator). Their heavy deps (d3, DuckDB) are shared with core citizen routes, so route-lazy does NOT remove those bytes from the initial load - it only adds a click-to-blank waterfall. Lazy ONLY the genuinely-isolated dev routes (Yenask, DevChartsSandbox). See Row 2.
- **Admin app** (`admin/`). Dev-only, never deployed (`"private": true`), 4 static routes, no heavy deps. No citizen impact. Leave alone.

### ESCALATE triggers (stop and ask)

- **Row 2 router change balloons.** If adding async-component support to [router.svelte.ts](../frontend/src/lib/router.svelte.ts) for the 2 lazy dev routes turns out to require a routing-contract redesign (more than a thin async-component loader wrapper), STOP: split the lazy-route commit out, ship the `prewarmDB()` gate alone (the high-value, low-risk part), and surface the router-contract question for Gregor + user sign-off.
- **Any schema change.** None is expected. If a row appears to need one, escalate (Level 5, Hans + Max).
- **A loading-copy string would name a machine.** ADR-0021 (no-implementation-disclosure) is binding: no public copy may name storage formats, query engines, internal paths, or boundary-check mechanisms. "Loading database...", "Querying...", "DuckDB", "WASM", "Loading map..." are all banned. If a row seems to need such a string, the answer is a shaped skeleton with no text - do not ship the string.

### Chosen strategy (the converged persona ruling)

| Q | Fowler (engineering) | Jony (UX) | CONVERGED RULING |
| --- | --- | --- | --- |
| Code-split aggressiveness | Delete dead maplibre; gate prewarm; lazy the dev/rare routes; no d3 micro-split | Gate prewarm is the honest win; don't trade an invisible cost for a visible click-to-blank waterfall; keep core routes eager | Delete maplibre (Row 1). Gate `prewarmDB()` on a `needsDB` route predicate (Row 2, dominant win). Lazy-import ONLY the isolated dev routes Yenask + DevChartsSandbox (Row 2). NO route-lazy for shared-dep routes. NO d3 micro-split. NO vendor `manualChunks`. |
| Caching | Module-promise per loader; boundary geometry cache is highest-value; NO `query()` memo; cache at bounded-id loader layer | Re-downloading geometry on back betrays the browser's back=instant contract; cache the immutable, never build a TTL framework | Module-promise cache on the small loaders (Row 4). `Map<url, Promise>` geometry cache in boundaries.ts (Row 3, top value). Query-result cache at the bounded-id view-model loader boundary, NOT a `query()` SQL memo (Row 5). One-line "immutable per deploy" invariant comment at each cache. |
| Service worker | DEFER - irreversible stuck-on-stale on Pages, marginal benefit | DEFER - civic-truth harm if stale data served confidently | DEFER + ESCALATE (Level-4/5). Out of scope. |
| Loading-state pattern | Seam already exists (LoaderResult + ChartShell + Skeleton); defect is inconsistent ADOPTION + a shapeless generic skeleton; build exactly 3 content-shaped primitives, wire through ChartShell, delete bespoke loaders | A blank white page reads as broken; content-shaped skeletons are honest anticipation (zero layout shift); a generic spinner is an anxious confession; kill every static "Loading..." string | Build EXACTLY 3 content-shaped primitives (KpiGridSkeleton, TableSkeleton, MapFrameSkeleton), wired through the existing [ChartShell.svelte](../frontend/src/lib/charts/ChartShell.svelte) loading arm (Row 6). Adopt on every blank-page + "Loading..."-text + blank-map surface and DELETE the bespoke loaders (Row 7). Map cold placeholder = framed neutral box at final dims (TileCartogram pending treatment), NOT the silhouette (the silhouette shares the blocked fetch); the silhouette is an optional progressive first-paint, not the cold stage. NO skeleton-from-spec framework. |

---

## Section 1 - Status Reckoner

Rows are PRs. Status starts `[ ] PENDING`, flips to `[x] DONE` with the merged PR number.

| Row | Title | Status | PR | Parallel-group | Depends-on | Effort | Risk |
| :-: | --- | :-: | :-: | :-: | :-: | :-: | :-: |
| 1 | Delete dead `maplibre-gl` dependency | [x] COLLAPSED no-op | - | A | none | XS | Low |
| 2 | Gate `prewarmDB()` + lazy-import isolated dev routes | [ ] BLOCKED-NEEDS-DECISION | - | B | none | M | Med (router boundary - see ESCALATE) |
| 3 | Boundary-geometry session cache in `boundaries.ts` | [x] DONE | #1208 | A | none | S | Low (highest VALUE) |
| 3b | Map-component geometry cache (5 d3 charts) | [x] DONE | #1210 | A | Row 3 | S | Low (discovered) |
| 4 | Module-promise caches on the uncached reference loaders | [x] DONE | #1211 | A | none | M | Low |
| 5 | Query-result cache at the view-model loader boundary | [x] DONE | #1212 | A | none | M | Low-Med |
| 6 | ChartShell seam + 3 content-shaped skeleton primitives | [x] DONE | #1213 | C | none | M | Low (additive) |
| 7 | Adopt skeletons + delete bespoke loaders (no blank page) | [x] DONE (slice 1) | #1214 | D | Row 6 | L | Low-Med |

### Execution outcome (2026-06-23, autonomous run)

6 PRs merged (#1208, #1210, #1211, #1212, #1213, #1214). Per-row receipts:

- **Row 1 - COLLAPSED no-op.** `maplibre-gl` was already absent from `frontend/package.json` + `frontend/bun.lock`, `frontend/src/lib/maplibre/` already deleted, zero importers (a prior PR shipped it). The ~40 remaining matches are accurate historical comments (kept). Receipt: `git grep -i maplibre frontend/package.json frontend/bun.lock` -> empty.
- **Row 3 - DONE #1208.** Session cache on `loadBoundaryFromPath` (folded into the existing `_resetCachesForTesting` hook). Covers the district-choropleth / silhouette / `boundaries/sources.ts` consumers.
- **Row 3b - DONE #1210 (discovered mid-Row-3).** The 5 d3 map components (`IndiaPartyMap`, `StateAcMapD3`, `IndiaPcMapD3`, `StatePcMapD3`, `GeoChoropleth`) fetch geometry via their OWN `fetch(url)`, bypassing `loadBoundaryFromPath`. New `charts/geometry-cache.ts` (`fetchGeometryJson`, URL-keyed) routes all 5 through one cache. Browser-verified: the AC topojson is fetched ONCE and NOT re-fetched on back-navigation (the headline 0.5-10 MB win).
- **Row 4 - DONE #1211.** Audit correction: 4 of the 6 flagged loaders were ALREADY cached; only `fetchTopicCatalogue` + `fetchStateTiers` were genuinely uncached. Both now session-cached.
- **Row 5 - DONE #1212.** Bounded-id row cache on the 3 `run*Query` functions in `election-results.ts` (keyed by event/state/eci_no), NOT a blanket `query()` SQL memo (the Fowler-converged mechanism).
- **Row 6 - DONE #1213.** 3 content-shaped primitives (`KpiGridSkeleton`, `TableSkeleton`, `MapFrameSkeleton`). NOTE: `ChartShell` already exposes a `loading_slot` snippet seam, so no `ChartShell` change was needed.
- **Row 7 - DONE #1214 (slice 1).** Adopted skeletons on the reported blank Constituency AC page (a loading branch where there was none) + the 3 frozen-`Loading...`-text routes + Home's bespoke pulse. Deferred to a slice 2 (noted in the PR): the 4 map components' blank-box loading, `District.svelte`, `StateTopic.svelte`, `Explore.svelte`.
- **Row 2 - BLOCKED-NEEDS-DECISION.** The `prewarmDB()` gate was built but browser-verified INEFFECTIVE: `ScopePicker.svelte` (always mounted in the `LeftRail` shell) calls `loadStates()` on mount, which boots DuckDB (`registerCsvFile` + `query`) on EVERY page including `/about`, regardless of the route gate. Making `/about` skip the ~5.2 MB wasm boot requires deferring/replacing the scope picker's eager state load - a citizen-facing UX change (Jony + Citizen authority) outside Row 2's declared `main.ts` + `router.svelte.ts` scope. The inert gate was discarded; NOT shipped (zero value alone). DECISION NEEDED:
  - **(A)** Defer `ScopePicker`'s `loadStates()` to dropdown-open (states populate on interaction) + keep the gate.
  - **(B)** Load the 36-row states list without DuckDB (lightweight fetch + parse) so the picker never boots the engine.
  - **(C)** Drop Row 2 (accept DuckDB boots on all pages; the pure-chrome-only session that benefits is rare).

**Scheduling.** Group A = Rows 1, 3, 4, 5 (four agents at once - zero shared files between them). Group B = Row 2 (owns [main.ts](../frontend/src/main.ts) + [router.svelte.ts](../frontend/src/lib/router.svelte.ts) - the risk hotspot; one careful reviewer). Group C = Row 6 (owns [ChartShell.svelte](../frontend/src/lib/charts/ChartShell.svelte) + new primitive files). A, B, C all run in parallel. The ONLY serialization line is **Row 6 -> Row 7** (primitives must exist before adoption). Row 7 itself shards three ways (7a maps / 7b tables / 7c KPI/route bodies) once Row 6 lands.

**Collision-avoidance contract** (each hot shared file owned by exactly ONE row):

| Hot shared file | Owned by |
| --- | --- |
| [frontend/src/main.ts](../frontend/src/main.ts), [frontend/src/lib/router.svelte.ts](../frontend/src/lib/router.svelte.ts) | Row 2 ONLY |
| [frontend/src/lib/boundaries.ts](../frontend/src/lib/boundaries.ts) | Row 3 ONLY |
| [frontend/src/lib/catalogue.ts](../frontend/src/lib/catalogue.ts), [frontend/src/lib/grapher/catalogue.ts](../frontend/src/lib/grapher/catalogue.ts) | Row 4 ONLY |
| [frontend/src/lib/charts/ChartShell.svelte](../frontend/src/lib/charts/ChartShell.svelte) | Row 6 ONLY |
| view-models/*.ts (query callers) | Row 5 ONLY |
| route `.svelte` bodies + chart-component bodies | Row 7 ONLY |

Non-collision proof for the one overlap worth naming: Row 2 lazy-imports a route via the main.ts route-table *entry*; Row 7 adds a skeleton inside that route's *body* (`.svelte`). Different files - no collision. Benign semantic interaction: once Row 3 caches geometry, Row 7's map skeleton shows only on first map mount - that is the desired behaviour, not a conflict.

---

## Section 2 - Per-row specs

### Row 1 - Delete dead `maplibre-gl` dependency

- **Scope.** `maplibre-gl` has no importer anywhere in `frontend/src` (the live maps are d3-geo). Remove it. Durov/Fowler deletion discipline: the best code is deleted code; zero risk after a grep confirms no importer.
- **Files.** [frontend/package.json](../frontend/package.json) (remove the dep), `frontend/bun.lock` (regenerate via `bun install` and stage in the SAME commit per CLAUDE.md Definition-of-Done). Possibly stale comments in [StateAcMapD3.svelte](../frontend/src/lib/charts/StateAcMapD3.svelte) / [IndiaPartyMap.svelte](../frontend/src/lib/charts/IndiaPartyMap.svelte) that reference a future "delete lib/maplibre" - update only if they now read false.
- **Acceptance gates.** `bun run build` green; `bun run test` green; `grep -ri "maplibre" frontend/src` returns zero matches; `maplibre-gl` absent from package.json AND bun.lock.
- **Oracle.** `rg -i maplibre frontend/src/` returns ZERO lines, and `bun run build` succeeds with maplibre-gl removed from the manifest + lockfile. (If any importer is found, STOP - this row's premise is false; surface it.)

### Row 2 - Gate `prewarmDB()` + lazy-import isolated dev routes

- **Scope.** Two changes, two commits (Beck two-hat: structural first, behavioural second).
  - **Commit 1 (structural).** Add a `needsDB?: boolean` capability to the `Route` interface in [router.svelte.ts](../frontend/src/lib/router.svelte.ts), and add a thin async-component loader so a route entry can carry a `() => import("./routes/X.svelte")` lazy component (rendered behind the existing generic `Skeleton` as the load fallback). Keep the change minimal - a loader wrapper, NOT a routing-contract redesign (see ESCALATE).
  - **Commit 2 (behavioural).** In [main.ts](../frontend/src/main.ts): (a) mark each route `needsDB` true/false (query routes Home, `/t/*`, `/:state`, `/:state/t/*`, `/:state/elections/*`, Explore, Psephlab, Compare, NationalElection = true; chrome routes `/about`, `/disclaimer`, `/settings`, `/parties`, `/docs/*` = false); (b) call `prewarmDB()` ONLY when the matched route is `needsDB` (move the call out of the unconditional top-level into the router's render path, gated on the matched route); (c) convert the 2 isolated dev routes `Yenask` and `DevChartsSandbox` to lazy `() => import(...)`.
- **Files.** [frontend/src/lib/router.svelte.ts](../frontend/src/lib/router.svelte.ts), [frontend/src/main.ts](../frontend/src/main.ts), and a new/updated router test.
- **Why only Yenask + DevChartsSandbox lazy.** They are the only routes whose deps are genuinely isolated from the citizen core (DevChartsSandbox mounts every chart fixture; Yenask pulls yenask/* glue, and `@huggingface/transformers` is already lazy). Explore/Psephlab/Compare share d3 + DuckDB with core routes, so lazy-loading them removes nothing from the initial load and only adds a waterfall - excluded by the converged ruling.
- **Acceptance gates.** `bun run build` green; `bun run test` green; a unit test asserts the `needsDB` classification for EVERY route in the table (no route unclassified); Section 13 browser-verify: load `/about` and confirm NO DuckDB-WASM wasm asset is fetched (network panel / `read_page`), then load `/` and confirm it IS fetched.
- **Oracle.** `needsDB` predicate coverage test = a bijection over the route table: every registered route maps to an explicit `true`/`false`, and the set classified `false` is exactly `{/about, /disclaimer, /settings, /parties, /docs/indicator/*, /docs/lab/*}`. Plus the browser check: `/about` issues zero `duckdb-*.wasm` requests.

### Row 3 - Boundary-geometry session cache in `boundaries.ts`

- **Scope.** The single highest-value cache. [boundaries.ts](../frontend/src/lib/boundaries.ts) core loader (`loadBoundaryFromPath`, the `fetch(topoUrl)` / `fetch(geoUrl)` site around [L318](../frontend/src/lib/boundaries.ts#L318)) re-downloads 0.5-10 MB of geometry on every map mount. Add a module-level `Map<resolvedUrl, Promise<result>>` so a given boundary URL is fetched + decoded ONCE per session. Reuse the EXACT proven pattern in [state-silhouette.ts](../frontend/src/lib/state-silhouette.ts) (`Map<key, Feature|null>` + `inFlight` serialization + null-cached-so-missing-doesn't-re-probe). Add a one-line comment pinning the "immutable per deploy = zero staleness window" invariant so no future agent adds speculative invalidation.
- **Files.** [frontend/src/lib/boundaries.ts](../frontend/src/lib/boundaries.ts) ONLY + its test.
- **Acceptance gates.** `bun run test` green; new fetch-once test; existing boundary loader tests still green; Section 13 browser-verify: navigate state -> back -> state and confirm the boundary geojson is NOT re-requested on the second visit.
- **Oracle.** Fetch-once test: stub `fetch`, call the boundary loader twice for the same resolved URL, assert `fetch` was called exactly once and both calls resolve to the same decoded collection (and a `null` result is also cached - a second call for a missing file does not re-probe).

### Row 4 - Module-promise caches on the 5 uncached reference loaders

- **Scope.** Copy the proven [election-events.ts](../frontend/src/lib/election-events.ts) module-promise pattern (`let _cache: Promise<T> | null = null; if (_cache) return _cache; _cache = fetch(...).then(...); _cache.catch(() => { _cache = null; })`) onto each currently-uncached small loader so each is fetched ONCE per session. Internally shardable per file.
  - [catalogue.ts](../frontend/src/lib/catalogue.ts) `fetchTopicCatalogue` (note it cascades into `fetchGrapherTopicCatalogue` - cache both)
  - [grapher/catalogue.ts](../frontend/src/lib/grapher/catalogue.ts) `fetchGrapherTopicCatalogue` + `fetchGrapherIndicatorCatalogue`
  - [state-tiers.ts](../frontend/src/lib/state-tiers.ts) `fetchStateTiers`
  - [canonical/csv-columns.ts](../frontend/src/lib/canonical/csv-columns.ts) `csvColumnsClause` (the column schema)
  - [canonical/canonical-entity-translation.ts](../frontend/src/lib/canonical/canonical-entity-translation.ts) geo-csv fetch + [elections/constituency-lookup.ts](../frontend/src/lib/elections/constituency-lookup.ts) electoral-entities fetch (cache if a single shared promise is clean; otherwise leave constituency-lookup to a follow-up if its key varies)
- **Files.** The loader modules listed above + a fetch-once test per loader. Each loader is its own file - no collision; shardable across sub-agents if desired, but ships as ONE PR.
- **Acceptance gates.** `bun run test` green; one fetch-once test per cached loader; `catch`-resets-the-cache-on-failure test (so a transient failure does not pin a rejected promise forever).
- **Oracle.** Per-loader fetch-once test: stub `fetch`, call the loader twice, assert `fetch` called once; then make the stub reject once and assert the cache resets (next call re-fetches).

### Row 5 - Query-result cache at the view-model loader boundary

- **Scope.** Deliver the back-navigation speedup WITHOUT a blanket `query()` memo (rejected: unbounded SQL-string keys, band-aid over the router remount). Add a bounded-id-keyed result cache at the view-model loader layer - the loaders that call `query()` (e.g. `view-models/election-results.ts` `runNationalPcQuery` / `runStateAcQuery` / `runConstituencyQuery`, and the constituency / state-overview loaders). Key on the bounded semantic id the loader already receives (e.g. `(event, state_code, eci_no)`), NOT on raw SQL. Reuse the [state-silhouette.ts](../frontend/src/lib/state-silhouette.ts) `Map` + `inFlight` pattern. Pin the immutable-per-deploy invariant in a comment.
- **Files.** The view-model loader modules under [frontend/src/lib/view-models/](../frontend/src/lib/view-models/) that call `query()` + their tests. Does NOT touch [duckdb.ts](../frontend/src/lib/duckdb.ts) `query()` itself (leave the primitive un-memoized).
- **Acceptance gates.** `bun run test` green; query-once test per cached loader; existing view-model loader contract tests still green; Section 13 browser-verify: Home -> State -> back to Home does not re-run the home query (observable as no repeated DuckDB scan / faster second paint).
- **Oracle.** Query-once test: stub the loader's `query`/connection seam, invoke the loader twice with the same bounded id, assert the underlying query ran exactly once; invoke with a DIFFERENT id, assert it runs again (the key is the bounded id, not a global singleton).

### Row 6 - ChartShell seam + 3 content-shaped skeleton primitives

- **Scope.** Build EXACTLY three content-shaped skeleton components, each mapping to >=3 real repeated surfaces named in the audit (so each earns its abstraction - not over-engineering): `KpiGridSkeleton` (KPI tile grid), `TableSkeleton` (header + N ghost rows), `MapFrameSkeleton` (framed neutral box at the final map dimensions carrying the [TileCartogram.svelte](../frontend/src/lib/charts/TileCartogram.svelte) calm pending-cell treatment - needs no fetch). Wire them THROUGH the existing [ChartShell.svelte](../frontend/src/lib/charts/ChartShell.svelte) loading arm (a `variant` prop or the existing `loading_slot`) so there is ONE seam, not a parallel one. The generic [Skeleton.svelte](../frontend/src/lib/Skeleton.svelte) stays as the dispatcher-only fallback (unknown shape). NO skeleton-from-spec framework. Design constraints: calm motion (respects reduced-motion - already handled by Skeleton), recognizable shapes, zero layout-shift (skeleton occupies the final content box).
- **Files.** [frontend/src/lib/charts/ChartShell.svelte](../frontend/src/lib/charts/ChartShell.svelte) (add the variant/slot), 3 new files `KpiGridSkeleton.svelte` / `TableSkeleton.svelte` / `MapFrameSkeleton.svelte` under `frontend/src/lib/` (or `lib/charts/`), + structure tests. ADDITIVE - the ChartShell default loading arm is unchanged so no existing consumer regresses.
- **Acceptance gates.** `bun run test` green; existing ChartShell tests still green; each new primitive has a structure test (renders the expected ghost-shape); Section 13 browser-verify via [DevChartsSandbox.svelte](../frontend/src/routes/DevChartsSandbox.svelte) (mount each primitive against a fixture).
- **Oracle.** Each primitive renders its content shape: `KpiGridSkeleton` emits N ghost tiles in the grid; `TableSkeleton` emits a header + N ghost rows; `MapFrameSkeleton` emits a framed box at the passed dimensions with the neutral-cell treatment - asserted by a structure/DOM test, with the ChartShell default arm proven unchanged.

### Row 7 - Adopt skeletons + delete bespoke loaders (no blank page survives)

- **Scope.** Replace every blank-page / static-"Loading..." / blank-map surface with the Row 6 primitives through the LoaderResult/ChartShell seam, and DELETE the bespoke loaders so there is ONE loading vocabulary. Banned copy per ADR-0021: no string may name a machine. Shard 7a (maps) / 7b (tables + landings) / 7c (KPI + route bodies). The worst-first target list (the user's reported `.../ac/tezu` is #1):

| Surface | Today | Becomes |
| --- | --- | --- |
| [Constituency.svelte](../frontend/src/routes/Constituency.svelte) (reported `.../ac/tezu`) | blank white 5-10s | `KpiGridSkeleton` above a `MapFrameSkeleton` at final dims - zero white |
| [District.svelte](../frontend/src/routes/District.svelte) | blank white | `KpiGridSkeleton` + `MapFrameSkeleton` |
| [StateTopic.svelte](../frontend/src/routes/StateTopic.svelte) | blank white | chart-card skeletons via ChartShell `state="loading"` |
| [IndiaPartyMap.svelte](../frontend/src/lib/charts/IndiaPartyMap.svelte), [StateAcMapD3.svelte](../frontend/src/lib/charts/StateAcMapD3.svelte), [IndiaPcMapD3.svelte](../frontend/src/lib/charts/IndiaPcMapD3.svelte), [GeoChoropleth.svelte](../frontend/src/lib/charts/GeoChoropleth.svelte) | blank box | `MapFrameSkeleton` at final dims; optional `loadStateSilhouette` outline as progressive first-paint once geometry resolves |
| [StateElectionsLanding.svelte](../frontend/src/routes/StateElectionsLanding.svelte), [AssemblyElections.svelte](../frontend/src/routes/AssemblyElections.svelte) | static "Loading..." | `TableSkeleton` (known shape); delete the text |
| [StateSubRouter.svelte](../frontend/src/routes/StateSubRouter.svelte) | static "Loading..." | single silent generic `Skeleton` shimmer (unknown shape - dispatcher carve-out); delete the text |
| [Explore.svelte](../frontend/src/routes/Explore.svelte) | dead-disabled run button, no reason | keep control alive; inline shimmer on the result area while building - never a dead control with no explanation |
| [Home.svelte](../frontend/src/routes/Home.svelte) | bespoke `animate-pulse` grey box | swap to `MapFrameSkeleton` (matches eventual choropleth, zero CLS); delete the one-off pulse div |
| [StateOverview.svelte](../frontend/src/routes/StateOverview.svelte) (the `/gujarat` URL) | already good | LEAVE ALONE - this is the template the rest copy |

- **Files.** The route + chart-component `.svelte` bodies listed above (NOT ChartShell - owned by Row 6). Delete the `"Loading..."` strings and Home's `animate-pulse` div.
- **Acceptance gates.** `bun run test` green; `bun run test:e2e` green if runtime changed; `rg "Loading\\.\\.\\." frontend/src/routes` returns zero citizen-facing matches; `rg "animate-pulse" frontend/src/routes/Home.svelte` returns zero; **mandatory Section 13 browser-verify** on the two reported URLs (`/gujarat` and `/arunachal-pradesh/elections/assembly-2024/ac/tezu`) plus one cross-route smoke - confirm a skeleton renders during load (testid present), no blank white page, no new console `[error]`, no new 404.
- **Oracle.** No-blank-page assertion: an e2e/browser check that [Constituency.svelte](../frontend/src/routes/Constituency.svelte) (the reported pain URL) shows a skeleton container (`data-testid` present) during the cold-load window instead of an empty `#route`, AND a grep proving the bespoke loaders (every citizen-facing `"Loading..."` string + Home's `animate-pulse`) are deleted.

---

## Section 3 - Definition of Done (per row, per CLAUDE.md section 9)

- [ ] Tests at the right tier ship WITH the row (no mocks beyond the `fetch`/`query` loader-seam carve-out). Full suite green at merge.
- [ ] `bun run build` + `bun run test` green; `bun run test:e2e` if frontend runtime changed.
- [ ] For any `frontend/` runtime change: Section 13 browser-verify (dev server up, navigate affected routes + one cross-route smoke, no new `[error]`, no new 404).
- [ ] Lockfile in sync (Row 1 must regenerate + stage `bun.lock` in the same commit).
- [ ] Docs updated if a contract/invariant changed (e.g. Row 2's `needsDB` route capability + Row 3-5 cache invariants -> a note in [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md)).
- [ ] No `[DEBUG]` markers; no new hardcoded values; no banned ADR-0021 copy.
- [ ] Post-merge cleanup per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md).

---

## Execution contract (autonomous - follow blindly, do not re-plan)

When this plan is in context and the instruction is "implement it", execute as the ORCHESTRATOR with NO further questions except at an ESCALATE trigger. There is no processing step after this block - the rules below are the whole instruction set.

1. **Orchestrator + subagent-PR topology.** The main agent owns the Status Reckoner and never lets its own context overflow. Each PR-row is dispatched to a stateless `runSubagent` brief that is self-contained: the row scope, the files, the acceptance gates, and the one oracle. The subagent does the row; the orchestrator merges and moves on.
2. **One row = one PR = one branch.** Park master on a `scratch-master-parking` branch so no worktree owns `main` (clean gh-merge). Author per [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md): 2-commit-then-squash, the 5-gate Definition-of-Done, browser-verify for any frontend/admin runtime change.
3. **Ship loop, non-stop.** Keep PRs in flight; never idle. As soon as one row's gates are green, merge (`gh pr merge --squash --delete-branch`), pull main, start the next row. Pre-existing unrelated test failures are not gating - document the baseline, do not block.
4. **Tests ship with the row.** Write/update only the tests the row needs. Full suite green at merge. No new mocks unless asked.
5. **Persona debate converges to ONE ruling.** When a row hits a contested design call, run the authority personas (CLAUDE.md section 0a) in debate, not parallel review; bake the single written verdict into the row and proceed.
6. **Manage context via offload.** Push breadth-y reads, audits, and exploration into subagents so the orchestrator's window stays lean. The orchestrator holds only the Reckoner, the current row, and the merge state.
7. **Post-merge hygiene every time.** Delete the remote branch, prune `: gone` local branches, remove `.tmp_*`, distill durable lessons.
8. **Stop only at a real boundary.** Stop and ask ONLY when: an ESCALATE trigger fires (Level-5), an explicit user-named source/instruction would be scope-narrowed (STOP-AND-SURFACE per CLAUDE.md section 10), or an audit chain exceeds depth 3 (the loop is lossy - escalate with Path A/B/C options, do not ship a 4th audit). Otherwise do not pause; the user is not watching.
9. **Closure.** Done only when every in-scope row is DONE or COLLAPSED-with-cited-rationale. No-op rows carry a receipt (the command + its zero result). Archive the plan-doc with a per-row distillation map per [docs/how-to/distill-a-plan.md](../docs/how-to/distill-a-plan.md).

### Parallelization for the ship loop

- Dispatch Group A (Rows 1, 3, 4, 5), Group B (Row 2), and Group C (Row 6) concurrently - they share no files (see the collision-avoidance contract). Rows 1/3/4/5 are four independent subagent briefs.
- Hold Row 7 until Row 6 has merged (the only dependency line). Then shard Row 7 into 7a (maps) / 7b (tables + landings) / 7c (KPI + route bodies + Home + Explore) as three concurrent briefs.
- Row 2 is the risk hotspot (router boundary). Give it the careful reviewer; if its router-async change exceeds a thin loader wrapper, split out the lazy-route commit and ship the `prewarmDB()` gate alone (ESCALATE).

## See also

- [CLAUDE.md](../CLAUDE.md) - authority table (section 0a), correction levels (section 6), anti-patterns (section 10), Definition of Done (section 9).
- [docs/architecture/frontend/data-loading.md](../docs/architecture/frontend/data-loading.md) - the data-loading contract these rows extend.
- [docs/concepts/citizen-first.md](../docs/concepts/citizen-first.md) - ADR-0021 no-implementation-disclosure (binding for loading copy).
- [docs/how-to/ship-a-pr.md](../docs/how-to/ship-a-pr.md) - the PR lifecycle the EXECUTION BLOCK references.
- [frontend/src/lib/state-silhouette.ts](../frontend/src/lib/state-silhouette.ts) - the `Map` + `inFlight` cache pattern Rows 3 + 5 reuse.
- [frontend/src/lib/loader-result.ts](../frontend/src/lib/loader-result.ts) + [frontend/src/lib/charts/ChartShell.svelte](../frontend/src/lib/charts/ChartShell.svelte) - the loading seam Rows 6 + 7 wire through.
