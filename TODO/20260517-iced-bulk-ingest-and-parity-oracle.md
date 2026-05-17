# ICED bulk ingest + value-parity oracle + composites + country-entity — design

**Status:** user-approved 2026-05-17. All 5 open questions in §9 resolved (locked into §2 and §4). Implementation may begin.

> **User direction verbatim:** "For the country entity URL yeah mirror what state is doing... if existing entity URL is wrong, fix it there as well. We don't hide behind seniority and then continue the stupidity. And what do you mean by adding alias? Does it generalize across all indicators? ... let us do all 14 of Max's parsers. ... consistency check ... a hybrid. ... discom health ... If they are agreeing on unit then let us do that. And try to see if we can generalize that, because we don't want to create unicorns in our code that is hard to maintain."

**Date:** 2026-05-17.
**Inputs:** Hans (governance), Max (indicator scout), Gregor (architect), Fowler (engineering) — four parallel agent consultations summarised below.
**Empirical ground truth:** `.runtime/iced_recon/triage_20260517075101.csv` (46-of-55 endpoints fetched OK, 9 path-rotation failures listed in §7).

---

## 1. What the user asked for

> "Download all ICED data, store in our format, then we can probably reshape. **Absolutely data consistency checks** — not whether download succeeded or JSON is compliant. Check the website and look at what data we have; numbers must match."

Three jobs:

A. **Bulk-ingest** every ICED endpoint we can, raw + parsed.
B. **Value-parity oracle**: prove our cell-for-cell numbers match upstream.
C. **Consolidate** adapters into composites where the per-metric file pattern fights the citizen question.

And the meta-rule: this is a multi-month subsystem, not a sprint. Phases are explicitly sequenced; nothing ships without parity passing for its slice.

---

## 2. The eight resolutions (settled before any code)

| # | Decision | Why |
|---|---|---|
| 1 | Citizen-facing field name = **`upstream_parity`** (object), populated INTO the existing required-null `divergence` slot (v2.0). Never `validate`, never `verified`. | Hans's term-smear hazard; the `divergence` slot is already reserved for exactly this. No schema bump. |
| 2 | Per-artifact append-only ledger at **`datasets/parity/in/<id>.ledger.jsonl`** (new path, new schema v1.0). Fowler over Gregor on this — git-diff per indicator stays readable, aggregate JSON would smear every run. | Fowler: "`git log <ledger>` answers Hans's 'when did this cell last match' natively without custom tooling." |
| 3 | Aggregate index **`datasets/reference/in/indicators-parity.json`** as the admin-panel grep point — generated, never hand-edited, sibling of `indicators-completeness.json`. | Gregor's pattern argument is correct for the *index* even if not for the *history*. |
| 4 | Oracle lives at **`tools/iced_parity/`** — operator-driven CLI + nightly task. NOT in `pytest`, NOT in `backend/`, NOT in `admin/`. | Hits a live external service; `pytest` tests code (lessons.md 2026-05-16 validator-descope); `backend/` is runtime-imported; admin is a UI shell. |
| 5 | Composites: **3 of them** (`discom_health`, `re_potential`, `coal_consumption`). Pattern = `rows[].facet` (already in schema since v1.3) plus a new optional **`indicator.sub_metrics[]` registry**. Schema bump = v4.2 → v4.3 additive. NO v5.0 contraction phase unless a future composite forces it. | Gregor's `metrics[]` array idea is overkill; the `facet` field already does the work. |
| 6 | Composite migration sequencing = **3 commits per composite** (emit-alongside / switch readers / delete legacy), staged not fused. Different bite size from ADR-0026 because the 5 legacy artifacts stay schema-valid throughout. | Fowler's expand→migrate→contract with a Branch by Abstraction at the catalogue layer. |
| 7 | Country-entity = **loader change + ALL entity routes rewritten to place-first cascade with flat indicator slug** per [ADR-0028](../docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md) (2026-05-17). Schema already has `entity_kind: "country"` (line 145). No schema bump. Country renders to line/scalar primitives ONLY, never to a choropleth. Boundary registry gets `boundaries/in/country/IN.json` with `{name, iso3166, no_geometry: true}`. URL scheme: `/india` / `/india/<state>` / `/india/<state>/<ac-slug>` / `/india/<indicator-slug>` / `/india/<state>/<indicator-slug>` / `/india/<state>/<ac-slug>/<indicator-slug>` — **place cascades left, indicator is the last segment, no `/c/`, `/s/`, `/i/` markers, no AC number prefix, no topic prefix in indicator slug**. Path-routed (supersedes hash-routing ADR-0016). Existing `/s/<state>/...` and `#/...` URLs are wrong and get migrated via strangler-fig redirect, not preserved. | User: "we don't hide behind seniority... country can directly be India... I would prefer not to have the number prefix... I like Max's opinion because the scale at OWID works." |
| 8 | Parser-kit = **4 helpers** in `backend/yen_gov/sources/iced_common/parser_kit.py` (`fy_to_period`, `row`, `dedup_sort`, `map_state_rows`). Extracted from observed duplication across 18 existing parsers; refactor commit lands BEFORE the 15 new parsers. | Fowler's grounded count (3+ concrete callers per `/memories/lessons.md`); rejects declarative endpoint-spec DSL as "framework that becomes the new code". |

---

## 3. The one decision that needs you

**API-parity vs rendered-page parity.**

User said *"check the website... numbers matching"*. Strict reading = scrape `iced.niti.gov.in` rendered charts via Playwright and compare to our artifact rows. Pragmatic reading = compare our artifact to ICED's own JSON API (the decrypted envelope), on the assumption that the charts bind from the same source.

| Approach | Pros | Cons |
|---|---|---|
| **API-parity only** (Phase 1 default) | Cheap, deterministic, fast, no Playwright in oracle | Doesn't catch cases where ICED's chart rendering rounds/formats differently than its API exposes. Misses cases where chart is stale vs API. |
| **Rendered-page parity** (Phase 2 add-on) | Catches what the citizen actually sees | Playwright per chart is slow + brittle; ICED chart canvases may not expose values to DOM inspection; requires reverse-engineering each chart type |
| **Hybrid** (recommend) | Phase 1 = API-parity for all sampled cells; Phase 2 = Playwright spot-check on 5 flagship charts per quarter to prove API ≈ rendered. Document API-parity as the operational bar; rendered-page as the calibration. | Two-tier oracle adds complexity but stays honest about its limits. |

**Question for you:** approve the hybrid (Phase 1 ships API-parity; Phase 2 adds rendered-page spot-check), or insist on rendered-page from day one (longer Phase 1, slower to first useful signal)?

---

## 4. Phase sequencing (post-approval)

Numbers are commit-bite estimates, not time estimates.

### Phase 1 — substrate (no new indicators, no behaviour change for citizens)
1. **Tidy**: extract `parser_kit.py` (4 helpers), re-point 3 existing parsers, prove byte-equal output. (1 commit)
2. **Catalogue hygiene**: handle the 9 path-rotation failures from `triage_20260517075101.csv` — re-recon, update or delete each. (1 commit per cluster)
3. **Boundary registry**: add `boundaries/in/country/IN.json` flag-only entry. (1 commit)
4. **Schema bump v4.2 → v4.3** additive: `indicator.sub_metrics[]` optional. Migrate 0 artifacts. (1 commit)

### Phase 2 — parity oracle
5. **Schema v1.0** for `parity-observation.schema.json` + `indicators-parity.schema.json`. (1 commit)
6. **`tools/iced_parity/` module** — `sample.py`, `probe.py`, `classify.py`, `ledger.py`, `banner.py`. Unit tests cover the 8 named test cases from Fowler's §4. (1 commit, behaviour-only follows in §7)
7. **Wire `upstream_parity` into the `divergence` slot** of `write_artifact` — splice-from-ledger pattern (ADR-0026 caller-wins-then-prior). (1 commit)
8. **First end-to-end parity run** against ONE indicator (`energy/state_atc_losses_pct` — the existing one we're about to retire into the composite, useful to baseline before migration). (1 commit, ledger lands)

### Phase 3 — URL migration to place-first cascade + path routing (touches every existing citizen page)

This Phase exists because of user direction. It is the largest single piece of frontend work in the plan; it MUST land before Phase 3b (country-entity routes) because country-entity is what exposed the inconsistency. The scheme is locked by [ADR-0028](../docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md) (place-first cascade, marker-less, flat indicator slug, path-routed, supersedes ADR-0016 hash routing). The five-voice debate (Gregor + Fowler + Jony + Hans + Max) and the OWID-alignment fallback doctrine ([docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md)) are recorded; do not re-debate the scheme here.

Commit sequence (Fowler's Tidy First, amended for path-routing migration):

9. **Path-router substrate** (structural-only):
   - Add `_site/404.html` SPA fallback (copy of `index.html`); wire via Vite `postbuild` step.
   - Extract `frontend/src/lib/paths.ts` helpers (`stateHref`, `acHref`, `indicatorHref`, `indicatorAtStateHref`, `RESERVED_SEGMENTS`). Every internal `<a href>` and `goto(...)` migrates to these helpers in this commit — behaviour identical, no route changes yet.
   - Add `frontend/src/lib/indicator-slug-registry.ts` loader against the new `url_slug` field on `indicators-completeness.json`.
   - Tier-A contract test `frontend/src/lib/paths.test.ts` enforcing the disjoint-set contract (state slugs ⊥ indicator slugs ⊥ AC slugs ⊥ RESERVED).
   - Backend emit-time test: `indicators-completeness.json` `url_slug` field is globally unique and disjoint from RESERVED.

10. **Indicator-slug registry land** (behavioural):
    - Bump `indicators-completeness.schema.json` additively: add optional `url_slug` per indicator (`x-version` minor bump, `x-changelog` entry).
    - `tools/emit_indicators_completeness_index.py` populates `url_slug` from the indicator id leaf (or a hand-overridden catalogue entry for collisions).
    - Drop AC number prefix in the existing AC slug emitter; AC slugs become name-only with `<name>-2` collision fallback.

11. **Route table flip** (behavioural):
    - Replace `Router` mode from hash to path; flip route patterns from `/s/:state/*` to `/india/:state/*` and the indicator-at-geo resolvers.
    - Add `RedirectLegacyUrl.svelte` strangler-fig component matching `#/...` and `/s/<state>/*` patterns, calling `history.replaceState` to the new path on mount.
    - Update e2e specs (`frontend/e2e/*.spec.ts`) to the new paths plus one redirect-assertion per legacy shape.
    - Manual integrated-browser smoke per CLAUDE.md §13: home, one state, one indicator-at-state, one indicator-at-AC, one redirected legacy URL.

12. **Legacy redirect sunset** (separate PR, one release cycle later): delete `RedirectLegacyUrl.svelte`. Tracked in code via `// TODO(2026-11):`.

A Jony consultation already happened in the five-voice debate; ADR-0028 incorporates Jony's read-aloud test (`india/tamil-nadu/installed-capacity` reads as three nouns, no scaffolding) and rejects hash routing on the same grounds. No second Jony consultation needed unless the implementation surfaces a new IA question.

### Phase 3b — country-entity (3 blocked national series unblocked)
13. **Loader change** — `if entity_kind === "country" return <Trend/>`. Existing state-indicator loader handles `entityId === "IN"`. (1 commit, structural)
14. **Promote `parse_per_capita_consumption`** — stop dropping `indiaWorld` rows; emit `datasets/indicators/in/economy/india_per_capita_consumption_inr.json`. (1 commit, behavioural)
15. **Country routes live** — `/india/<indicator-slug>` renders + 1 Playwright spec. (1 commit)
16. **Two more country series** — `india_primary_energy_supply.json` (energy_source_wise_supply), `india_temperature_annual.json` (climate_temperature_annual). Delete `TODO/20260517-iced-country-entity-series-blocked.md`. (1 commit each)

_Note: commit numbering shifted by +2 from the original plan because Phase 3 now has 4 commits (9–12) instead of 2 (9–10). Subsequent Phase 4/5/6/7/8 numbering also shifts; not re-numbered inline here to keep this amendment minimal — re-number on the next plan touch._

### Phase 4 — composites (replace 5 → 1, 5 → 1, 4 → 1)

**Generalisation note (user-mandated):** the row-level `unit` override is NOT a discom_health unicorn. It is a general schema feature for ANY composite-with-mixed-units, ANY current/future source. Schema description must say so explicitly; tests cover at least 2 distinct composites (discom_health + re_potential's `installed_mw` vs `potential_mw` if applicable) before the schema bump ships.

15. **`discom_health` composite** — 3 commits (emit alongside, switch readers, delete legacy 5). Uses the generalised row-level `unit` override added to v4.3 in Phase 1 step 4.
16. **`re_potential` composite** — same 3-commit pattern. (3 commits)
17. **`coal_consumption` cube** — same 3-commit pattern. (3 commits)

### Phase 5 — Max's parsing wave (all 14 endpoints — user-confirmed full commitment)
18. Parsers land one-at-a-time per CLAUDE.md per-indicator commit doctrine. Each commit: parser + artifact + ledger baseline + chart_title quote in `notes`. Sequencing per Max:
    1. `operationalPerformanceStates` (the source under `discom_health`)
    2. `co-emission-metatable-data`
    3. `captive-power-industry`
    4. `oil/consumptionStateProductTrend`
    5. `coal/consumption-domestic-state` (folds into `coal_consumption` composite from Phase 4)
    6. `aqi_map_markers` station-grain
    7. `gen-metatable-data` + `plf-metatable-data` (paired)
    8. `statelevel-power-purchase-quantum-and-cost` + `discom-level-power-purchase-quantum`
    9. `forest-cover-by-state`
    10. `climate/rainfall` (district)
    11. `analytics/energy-sales-category-wise`
    12. `consumerProfileStateWholeData`
    13. `accumulated-losses-consumer-saless`
    14. `environment/land`

### Phase 6 — wave-3 catalogue (planning)
19. Scan triage tail for next 20 candidates → append to `endpoints.py`. (1 commit)

### Phase 7 — admin-panel parity surface
20. `admin/` Parity panel: list indicators sorted by `divergent_cell_count desc`. Match-tiles render nothing (Hans's anti-rot lever).

### Phase 8 — Playwright rendered-page parity calibration (the hybrid Phase 2)
21. `tools/iced_parity/render_probe.py` — Playwright fetches 5 flagship ICED chart pages per quarter, extracts rendered values (via chart-canvas data-attribute inspection or DOM-text scrape), classifies API-vs-rendered delta. Result goes into a separate `datasets/parity/in/<id>.render_ledger.jsonl`. Used to calibrate the API-parity assumption; if it diverges materially, escalate to a per-indicator design call. (1 setup commit + 1 commit per probed chart)

---

## 5. The four hard questions Hans asked Gregor + Fowler — resolved

| Q | Answer |
|---|---|
| (a) How does an operator distinguish silent ICED revision from adapter regression? | `classify.py`: status `revised_upstream` if `upstream != prior_upstream AND our == prior_upstream`. `diverge` if `our != upstream AND our != prior_upstream`. Two distinct enum values, never collapsed to a boolean (Fowler's "ungameable by shape"). |
| (b) Where does parity history live such that `git log` answers "when did this cell last match"? | `git log datasets/parity/in/<id>.ledger.jsonl` — each line is one observation; `git blame` per cell is native. |
| (c) Failure budget — name a number. | **Phase 1 = 0 cells diverge** for the indicator to publish without a banner. 1+ diverge → banner with the cell list. 5%+ diverge → indicator marked `under_review` and held from the topic page roll. Numbers reviewed quarterly after first 10 audits. |
| (d) What stops "parity passed" from becoming the new "validation passed"? | Two structural choices: (i) classifier has no `is_ok()` method — only enum statuses; (ii) admin Parity panel sorts by divergent count desc, match-indicators don't render. Operator literally cannot skim past green checks because there ARE no green checks visible. |

---

## 6. The four risks Fowler flagged — handled

1. **`discom_health` mixed-units** → `rows[].unit` becomes optional override of indicator-level `unit`. Added to v4.3 in Phase 1 step 4.
2. **External-link breakage from id rename** → catalogue gets `aliases: {old_id: composite_id#facet=<facet>}` field. Schema for catalogue gets one additive field. Phase 4 step 13a.
3. **API-parity ≠ citizen-parity** → §3 above, decision deferred to user.
4. **Quarterly ledger growth** → JSONL for v1; revisit at 10k rows; SQLite is the deferred structural fix. NOT pre-built.

---

## 7. Empirical state — bulk-fetch is done

Already completed (commit-able as Phase 0 separately):

- 46-of-55 catalogued endpoints fetched OK into `.runtime/raw/iced/` (gitignored debug cache per ADR-0003).
- 9 failures (4 × 404, 1 × 400): `distinct_values`, `home_map`, `power_generation`, `retired_capacity_plants`, `plant_pipeline_info`, `power_plants_listing`, `plant_list_by_source`, `capacity_metatable`, `discoms_list`. Catalogue paths likely rotated since 2026-05-14 recon. Phase 1 step 2 reconciles these.
- Triage CSV: `.runtime/iced_recon/triage_20260517075101.csv`.
- Notable payload sizes confirming Max's "gold series" picks: `captive_power_industry` 2.0 MB / 15,048 rows; `ice_ev_vahan` 6.3 MB / dict cube; `economy_gva_trend` 3.1 MB / 14,350 rows; `aq_aqi_map_markers` 2.2 MB / 8,453 stations.

---

## 8. Rejected designs (archive — do NOT re-propose)

From Hans/Gregor/Fowler debate:

1. **`upstream_parity` folded as full `divergent_cells[]` array on the citizen artifact** — fetched_at-shape smear (Gregor §1). Only the *summary verdict* belongs inline.
2. **Aggregate `indicators-parity.json` as the only store of history** — git-log of a 100-indicator JSON gives diff noise per run (Fowler vs Gregor §1 conflict resolution).
3. **Parity oracle as a pytest tier** — repeats the 2026-05-16 validator-descope mistake.
4. **Separate `composite-indicator.schema.json`** — doubles renderer set, doubles loader, doubles contract test (Gregor §3 rejection).
5. **Synthesized India polygon as union of states** — invites meaningless single-colour choropleth (Gregor §2 rejection).
6. **Declarative `endpoint_spec.json` + generic ICED parser engine** — framework that becomes the new code; ICED envelopes are too variable (both Gregor §5 and Fowler §2).
7. **Continuous parity polling** — political liability with NITI Aayog; invites captcha-gate spread (Hans §3).
8. **Calling the oracle `validate`** — smear with schema-validation, same shape as `fetched_at` (Hans §6).
9. **`is_ok()` method on `ParityResult`** — collapses revised_upstream + diverge + absent into a boolean operators will stop reading (Fowler §4 via Hans §6.d).
10. **Hiding divergent rows from the citizen page** — theatre; the diff is the most valuable signal (Hans §4).
11. **Fused-commit for the discom_health composite** (5 files at once) — wrong bite size; legacy artifacts stay schema-valid, staged is correct (Fowler §1 vs ADR-0026 precedent).
12. **`backend/yen_gov/parity/`** as oracle home — pulls live external into runtime module (Fowler §3 over Gregor §4).

---

## 9. Open questions — RESOLVED 2026-05-17

| # | Question | Resolution |
|---|---|---|
| 1 | API-parity vs rendered-page parity | **Hybrid.** Phase 1–7 = API-parity. Phase 8 adds Playwright rendered-page spot-check on 5 flagship charts/quarter. |
| 2 | `discom_health` mixed units | **Row-level `unit` override, generalised.** Schema field is for any composite-with-mixed-units. Tests cover ≥2 distinct composites before the schema bump merges. No discom_health unicorn. |
| 3 | Country-entity URL shape | **Place-first cascade, marker-less, flat indicator slug, path-routed** per [ADR-0028](../docs/architecture/decisions/0028-url-scheme-place-first-flat-indicator-slug.md) (2026-05-17). `/india`, `/india/<state>`, `/india/<state>/<ac-slug>`, `/india/<indicator-slug>`, `/india/<state>/<indicator-slug>`, `/india/<state>/<ac-slug>/<indicator-slug>`. No `/c/`, `/s/`, `/i/` markers. No `167-` number prefix on AC slugs. No topic prefix in indicator slug (OWID-aligned). Supersedes ADR-0016 (hash routing). Five-voice debate (Gregor + Fowler + Jony + Hans + Max) digest in the ADR. Existing `/s/<state>/...` and `#/...` URLs migrated via strangler-fig redirect for one release cycle. User: "we don't hide behind seniority... I like Max's opinion because the scale at OWID works." |
| 4 | Catalogue aliases | **Generic at catalogue layer, not iced-specific.** `topic-catalogue.json` schema gets an additive `aliases: {old_id → new_ref}` field that applies to any indicator rename in any source, current or future. |
| 5 | Phase 5 budget | **All 14 of Max's parsers, full commitment.** No stop-after-N gate. |

---

## 10. What lands in the next commit (if approved as-is)

Phase 0: `.runtime/iced_mirror_wave2.log` + the refreshed `.b64` snapshots are gitignored — nothing to commit. The triage CSV is also gitignored (`.runtime/`). So technically nothing from today's mirror needs a commit; the substrate proof is the file existing locally.

Phase 1 step 1 (parser_kit extraction) is the first real commit, gated on your approval of this doc.

---

## 11. Handoff state

- Hans output: archived in chat-session-resources (toolu_vrtx_01WEi5Xi4mSh4ScNxLi5uf5i).
- Max output: archived in chat-session-resources (toolu_vrtx_01Y1onWnwwYWGhb1x2gFZhwy).
- Gregor output: archived in chat-session-resources (toolu_vrtx_017uixcPEiQiZMg6DcP7kQy9).
- Fowler output: same.
- Bulk fetch: `.runtime/iced_recon/triage_20260517075101.csv` + 46 refreshed `.b64`s in `.runtime/raw/iced/`.

**Stop. Awaiting user decisions on §9.**
