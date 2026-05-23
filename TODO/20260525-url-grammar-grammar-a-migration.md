# URL Grammar — Grammar A migration plan

**Date opened**: 2026-05-25
**Status**: Phase 1 in PR
**Authority**: Jony + Hans + Max (sequential debate 2026-05-25); user direction supersedes
**Supersedes**: implicit Grammar C in [ADR-0028](../docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md) (never built) and shipped Grammar B (locked by PR #172)
**See also**: [ADR-0037](../docs/architecture/decisions/0037-url-grammar-drop-india-prefix.md) (the binding decision doc), [docs/architecture/frontend/routing.md](../docs/architecture/frontend/routing.md)

## Why this plan exists

PR #172 (chore/frontend-url-grammar — merged as `aa78203b`) audited the codebase for legacy URLs against the rip-and-replace prompt and found ZERO real legacy URLs against the audited patterns A1–A6. It then LOCKED IN the shipped grammar (`/s/<state>` + `/t/<topic>`) via a 42-test contract. That polish PR was correct given the audit's scope, but it surfaced a deeper drift the audit didn't have authority to resolve:

| Doc / code surface | Says canonical grammar is |
|---|---|
| [docs/architecture/frontend/routing.md](../docs/architecture/frontend/routing.md) (Last Updated 2026-05-17) | `/india/<state-slug>/...` (per ADR-0028) |
| [docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md](../docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md) | `/india/<state-slug>/...` |
| [frontend/src/lib/url.ts](../frontend/src/lib/url.ts) (live, Grammar B) | `/s/<state-slug>/...` |
| [frontend/src/lib/paths.ts](../frontend/src/lib/paths.ts) (existing) | unrelated — holds `DATA_BASE` for runtime fetch prefixes |
| [frontend/src/lib/url.test.ts](../frontend/src/lib/url.test.ts) (PR #172, contract-locked) | `/s/<state-slug>/...` |
| Original rip-and-replace prompt §2 | `/s/in_s<NN>/...` (Hive partition form) |
| User direction 2026-05-25 | `/<state-slug>/...` (no `/india/`, no `/s/`) |

Six positions, four genuinely distinct grammars (Hive form / `/india/...` / `/s/...` / `/<state>/...`). User said: "Having nicer URLs is important. ... So we put this to rest one way or the other."

## The debate (2026-05-25)

Sequential Jony → Hans → Max with each voice seeing the previous one's binding output. Synthesis below is binding for this plan.

### Jony (UI/UX, §0a authority on URL grammar)

**Chose Grammar A** = `/tamil-nadu/mylapore/installed-capacity`. Country home `/` (India implicit on a `.in` domain). Topics keep `/t/<topic>` to isolate the topic namespace from the state namespace (collision safety + single-registry resolver economy). AC slug is pure name (`mylapore`), no `167-` numeric prefix. Reserved-chrome stays at root (`/compare`, `/about`, `/settings`, `/disclaimer`, `/data-completeness`, `/lab/<state>/<event>`).

Rejected: C (`/india/...`) reads as scaffolding for never-built country-multi-tenancy on a `.in` domain; B (`/s/<state>/ac/<ac>`) is markers that don't disambiguate; D (Hive form) is filesystem-dialect not citizen sentence.

Self-objection: link-rot blast radius. Mitigated because yen-gov has ≈zero external citations today; cost of change grows monotonically with every shared link.

### Hans (Governance — Rosling + Rathin Roy + Pramit Bhattacharya)

**Ratified Grammar A.** Added two binding constraints:

1. **Full-name English slugs, no abbreviations** — `/uttar-pradesh` not `/up`, `/madhya-pradesh` not `/mp`. Precedent count: Wikipedia (`Uttar_Pradesh`) + data.gov.in (`uttar-pradesh`) both use full-name; ECI's `S24` and MoSPI's `UP` are negative precedents that trained citizens to ignore URLs. Lock full-name.
2. **State-hub page MUST render `entity_type` (state | UT) badge under H1** — the URL alone can't carry constitutional honesty (Delhi-NCT, J&K-UT-since-2019, etc.); the page chrome closes it. Page chrome contract, not URL contract.

WhatsApp-forward citizen test: place-fact, dominantly. The Karnataka district health officer reads `yen-gov.in/tamil-nadu/mylapore/installed-capacity` the same way she reads `wikipedia.org/wiki/Mylapore` — the URL names what the page IS, not how the site is organised. Citizen-grounded.

Methodology-break survival (Telangana from AP, 2014): Grammar A handles entity splits/renames mildly better than B because the URL itself carries the semantic mismatch a citizen needs to understand the redirect.

### Max (Indicator Scout — OWID precedent)

**Ratified Grammar A with one amendment.** Strengthen the namespace-collision invariant to include AC slugs:

> `urlIndicatorSlugs ⊥ stateSlugs ⊥ topicSlugs ⊥ acSlugsAcrossAllStates ⊥ RESERVED`

The Jony spec's RESERVED list dropped `acSlugs`. AC names are the largest namespace (4,123 across all states); AC names like `central`, `north`, `south`, `kalyan`, `madhepura` are common nouns that will collide with future indicator slugs. Missing AC slugs in the disjointness check is the one bug that lets `mylapore`/`gondal`/`aliganj`-shaped collisions sneak through silently.

OWID slug-across-scopes precedent: OWID uses one flat slug per indicator at `/grapher/<slug>` and pushes geography into `?country=` filter. yen-gov diverges (geography moves into path per [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md#L70) divergence #1). Two canonical rows MAY share one citizen URL slug only when they measure the same noun at different scopes — requires explicit `url_slug` field on `taxonomy/indicators.parquet` and a registry-build cross-scope-consistency test (Phase 1.5).

Missing-scope behaviour (`/tamil-nadu/installed-capacity` when indicator is national-only): **render a stub with one-click deep link to nearest scope**, never silent-redirect, never 404. OWID precedent: `/grapher/<slug>?country=ATA` renders chart frame with "No data" + country-picker. Wikipedia precedent: redlinks render stub.

Cross-state surface (compare across all states): collapse INTO the indicator page itself with a compare-mode tab — not `/compare/<indicator>`. OWID precedent: `/grapher/co2-emissions-per-capita` IS the compare surface, country-picker is a control. Existing election-compare (`/compare/<state>/<event>`) is a different surface and stays.

10k-indicator scaling: collision-safe today (~60 indicators × 4,123 ACs × 36 states = 0 hits) but fragile at OWID-scale. Threshold N where `/i/<slug>` reserved-marker retrofit becomes due is empirical — estimate `N = 800 to 2000` url-slugs based on AC-name distribution. Do NOT pre-ship the marker; ship the Tier-A test that signals when retrofit is due.

## Binding decision (synthesis)

**Grammar A wins.** Final shape:

| Surface | URL |
|---|---|
| Country home | `/` |
| State hub | `/tamil-nadu` |
| AC | `/tamil-nadu/mylapore` (pure name, no `167-` prefix) |
| District | `/tamil-nadu/chennai` (when renderer ships) |
| Indicator @ national | `/installed-capacity` |
| Indicator @ state | `/tamil-nadu/installed-capacity` |
| Indicator @ AC | `/tamil-nadu/mylapore/installed-capacity` |
| Topic index | `/t` |
| Topic landing | `/t/energy` |
| Per-state topic | `/tamil-nadu/t/energy` (sub-namespace under state) |
| Party-in-state | `/tamil-nadu/party/dmk-aiadmk` |
| State explore | `/tamil-nadu/explore` |
| Cross-state indicator compare | `/installed-capacity` with compare-mode tab (Phase 3+) |
| Election compare | `/compare/<state>/<event>` (legacy surface, retained) |
| Election lab | `/lab/<state>/<event>` |
| Chrome | `/about`, `/settings`, `/disclaimer`, `/data-completeness`, `/compare` |

Reserved-chrome tokens (top-level positional reservations, MUST NOT be a state slug, topic slug, indicator slug, or AC slug):

```
RESERVED = ["t", "compare", "about", "settings", "disclaimer", "data-completeness",
            "lab", "dev", "s", "ac", "party", "i", "explore"]
```

The last 6 (`s`, `ac`, `party`, `i`, `explore`, `dev`) are retained reservations: `s/ac/party/explore` are legacy-redirect anchors; `i` is the pre-reserved fallback for the future indicator-marker retrofit Max named; `dev` is the existing dev-only Vite alias.

## Four-phase migration

| Phase | Day-1? | Scope | Reversibility |
|---|---|---|---|
| **1** (this PR) | yes | Create [frontend/src/lib/links.ts](../frontend/src/lib/links.ts) with Grammar A builders. Create [ADR-0037](../docs/architecture/decisions/0037-url-grammar-drop-india-prefix.md) amending ADR-0028. Update [routing.md](../docs/architecture/frontend/routing.md) to reflect Grammar A end-state. Add three Tier-A tests (link shape, namespace disjointness, full-name state-slug invariant). Zero call-site migration. Zero route table change. PR #172's 42 tests stay green. | `git revert` |
| **2** | no | Add Grammar A routes to [frontend/src/main.ts](../frontend/src/main.ts) ALONGSIDE existing `/s/*` routes. Root resolver decides state/topic/indicator/chrome by registry. Both grammars resolve concurrently. Internal `<a href>` callers migrate from `url.ts` to `links.ts` one component at a time. AC slug shape change (`167-mylapore` → `mylapore`) ships here. Wire AC slug registry (4,112 names from `dim_acs.parquet`) into `url-namespace-disjointness.test.ts` so the 4-way disjointness Max specified becomes asserted. §13 browser smoke MUST confirm both shapes render. | per-component revert |
| **3** | no | Add `RedirectLegacyUrl.svelte` per [routing.md §strangler-fig](../docs/architecture/frontend/routing.md). On match of `/s/<state>*` rewrite to Grammar A via `history.replaceState`. Cross-state compare surface collapses into indicator page (Max §4). New `url_slug` field on `taxonomy/indicators.parquet` (Max §3i) + Phase 1.5 cross-scope-consistency test extension. Extend `url-namespace-disjointness.test.ts` to the 5-way disjointness Max ratified (indicator slugs joined in). | component delete + ADR amend |
| **4** | no | Delete `/s/*` route entries + legacy `url.ts` builders + PR #172's 42-test contract; replace with the equivalent Grammar A 42-test contract. `RedirectLegacyUrl.svelte` retained one release cycle, then deleted in 4b. Drift closed: docs, code, tests all say A. | one full release of forward-only |

Phase 1 is fully autonomous-doable. Phases 2/3/4 are also autonomous-doable but each one ships as its own PR with §13 browser smoke as the gate.

## Open user-gate questions (none block Phase 1)

1. **Per-state topic URL — `/<state>/t/<topic>` vs `/<state>?topic=<topic>` vs flatten to `/<state>/<topic>`?** Phase 1 paths.ts ships `/<state>/t/<topic>` (Jony's collision-isolation extends to per-state). User may want flatter. **Decision needed before Phase 2 route table change.**
2. **Redirect window length for `/s/<state>*` → `/<state>*`?** Jony spec: "one release cycle then deleted." If yen-gov starts attracting external citations during Phase 2/3 window, may need to extend or make permanent. **Decision needed before Phase 4 redirect deletion.**
3. **Should `url_slug` be a new field on `taxonomy/indicators.parquet` (deterministic, hand-editable) OR derived at registry-build from `indicator_id` (one less drift point)?** Max + Hans share §0a authority on indicator-naming; defaulting to derived in Phase 3 unless user prefers field-on-row. **Decision needed before Phase 3.**

## Phase 1 ship contents (this PR)

1. [frontend/src/lib/links.ts](../frontend/src/lib/links.ts) — typed Grammar A builders (~220 LOC, pure functions, zero call-sites)
2. [frontend/src/lib/links.test.ts](../frontend/src/lib/links.test.ts) — positive Grammar A shape assertions
3. [frontend/src/contracts/url-namespace-disjointness.test.ts](../frontend/src/contracts/url-namespace-disjointness.test.ts) — Phase 1 asserts the 3-way disjointness verifiable from JSON today (state slugs ⊥ topic slugs ⊥ RESERVED). AC slugs (4,112 names in `dim_acs.parquet`, needs DuckDB-WASM in the test harness) wired in Phase 2; indicator url_slug (Max §3i, needs new field on `taxonomy/indicators.parquet`) wired in Phase 3.
4. [frontend/src/contracts/state-slugs-full-name.test.ts](../frontend/src/contracts/state-slugs-full-name.test.ts) — Hans's full-name invariant against real corpus
5. [docs/architecture/decisions/0037-url-grammar-drop-india-prefix.md](../docs/architecture/decisions/0037-url-grammar-drop-india-prefix.md) — new ADR; amends ADR-0028
6. [docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md](../docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md) — Status flipped to "amended-by-ADR-0037"; route grammar table rewritten
7. [docs/architecture/frontend/routing.md](../docs/architecture/frontend/routing.md) — Grammar A end-state documented; strangler-fig framing preserved
8. This plan-doc

## Done criteria for Phase 1

- [ ] `bun run check` clean (svelte-check 0 errors)
- [ ] `bun test --run` green (no regression in PR #172's 42-test contract)
- [ ] New 3 Tier-A tests green
- [ ] No `[DEBUG]` markers
- [ ] No `frontend/src/lib/url.ts` modifications (Phase 2 territory)
- [ ] No `frontend/src/main.ts` modifications (Phase 2 territory)
- [ ] `python -m yen_gov validate --root .` runs clean (no datasets touched)
- [ ] §13 browser smoke NOT applicable — paths.ts has zero call-sites, no UI surface changes
- [ ] Single squash commit per Phase 1 boundary
- [ ] PR uses `--auto` merge gate
