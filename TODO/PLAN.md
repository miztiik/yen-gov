# yen-gov — Phased Build Plan

**Last Updated**: 2026-05-11
**Status**: Phases 0–4 complete + Phase 5 (socio-economic indicator pilot) complete. Single TN slice extended to KL/AS/WB results; energy/installed_mw_by_state indicator rendered nationally on TN overview via generic IndicatorChoropleth.
**Authority**: Non-authoritative scratchpad (per CLAUDE.md §3). Promote decisions into `docs/architecture/` as they solidify.

> **Historical-ADR notice (2026-05-09)**: References below to ADR-0001, -0004, -0007, -0008, -0009, -0010, -0013, -0014, -0015, -0016 record what was done at the time those ADRs existed. Those decisions have since been absorbed into subsystem docs under `docs/architecture/backend/` and `docs/architecture/frontend/`; see `docs/architecture/decisions/README.md` for the mapping table. Only ADR-0002 (provenance) and ADR-0003 (no fetch cache) survive as standalone ADRs.

## Locked decisions (2026-05-08)

- **Scope**: Indian election data. First slice: Tamil Nadu Legislative Assembly election, May 2026 (ECI event `AcGenMay2026`, state code `S22`).
- **Frontend stack**: Svelte + Vite + Tailwind + d3. UI code only — no committed data files.
- **Backend stack**: Python (httpx + tenacity + selectolax/lxml + pydantic v2 + typer + jsonschema).
- **Data tier**: top-level `datasets/` directory, owned by neither runtime. Backend writes; frontend's Vite build copies into `frontend/dist/data/` via `vite-plugin-static-copy`. (CLAUDE.md §3 + §4 amended 2026-05-08.)
- **Identifiers**: ISO 3166 + ECI codes. No invented IDs. (CLAUDE.md §3.)
- **Data emission**: JSON primary (per-AC files + index). SQLite is a derived secondary artifact built from the same validated records — frontend can lazy-load `sqlite-wasm` for cross-cutting queries on a dedicated `/explore` page; no other page may require it.
- **Schema authoring**: hand-authored JSON Schemas are source of truth. Pydantic v2 mirrors live in `backend/yen_gov/contracts/`; CI test asserts compatibility (no drift).
- **Schema versioning**: `x-version` (major.minor only) + `x-changelog` array inside each schema. Two-tier validator (CLAUDE.md §11).
- **Local UX**: CLI is the source of truth. FastAPI server is a thin wrapper that invokes the same commands and streams progress to a small browser page (dev-only, never deployed).
- **Production**: Static bundle on GitHub Pages. No runtime backend. (CLAUDE.md Holy Law #1.)
- **Phase order**: Schemas + reference data → Wikipedia taxonomy scrape → one AC end-to-end → full state → visualizations → CI/Pages.

## Open items still TBD

- District identifier source: LGD codes preferred (gov.in Local Government Directory); Wikipedia slug as fallback when LGD unavailable.
- "Top-N + others" cutoff: provisional default = top 5 candidates + NOTA + collapsed "others" bucket. Confirm with real data in Phase 2.
- GitHub Actions cadence: manual dispatch only for now.

---

## Phase 0 — Schemas, validator, reference seed

**Goal**: Lock the contracts. Stand up the validator. Seed only what can be hand-authored without scraping (national reference, processing knobs).

**Step A — contracts (DONE, 2026-05-08)**
- [x] Amend `CLAUDE.md` §3 to add `datasets/` tier, narrow `config/`, document identifier convention.
- [x] Amend `CLAUDE.md` §4 to forbid frontend data commits and codify `datasets/` as the contract surface.
- [x] Add `CLAUDE.md` §11 (Schema Versioning) and §12 (Open Questions, replacing the old TBD section).
- [x] Update this `TODO/PLAN.md` to reflect the new layout.

**Step B — schemas (DONE, 2026-05-08)**
- [x] Created `datasets/schemas/` with 8 JSON Schemas (draft 2020-12), each at `x-version: "1.0"` with single-entry `x-changelog`. All pass meta-schema validation.

**Step C — validator (DONE, 2026-05-08)**
- [x] `backend/yen_gov/validate.py` implements both tiers per CLAUDE.md §11.
- [x] `backend/pyproject.toml` (jsonschema, typer; pytest as dev extra).
- [x] CLI: `python -m yen_gov validate` → exits 0 on success, lists `[tier A|B] file: message` and exits 1 on failure.
- [x] `config/processing.json` validates against `processing.schema.json`.
- [x] 6 tests under `backend/tests/test_validate.py` (good repo, bad version format, changelog mismatch, wrong $schema_version, missing required field, unknown schema).
- [x] Pydantic mirrors deferred to Phase 1, where the parser actually needs them. Drift guard test added then.

**Step D — seed (DONE, 2026-05-08)**
- [x] `datasets/reference/in/states.json` — Tamil Nadu (S22) only. Other 35 states/UTs deferred to Phase 0.5 to avoid inventing unverified ECI codes.
- [x] `datasets/events/in/eci/AcGenMay2026/election.json` — event metadata for the TN AC May 2026 election.

**Step E — docs (DONE, 2026-05-08)**
- [x] `docs/architecture/data-flow.md` — `datasets/` as contract surface, build-time copy, no runtime backend.
- [x] `docs/architecture/data-model.md` — entities and relationships.
- [x] `docs/reference/schemas.md` — table of schemas with current versions and how to declare `$schema` in data files.
- [x] `docs/reference/identifiers.md` — ECI/ISO/LGD code conventions with verification sources.

**Definition of done**: `python -m yen_gov validate` exits 0; pytest 6/6 green; docs cross-link.

---

## Phase 0.5 — Tamil Nadu reference data + pipeline (DONE, 2026-05-08/09)

**Goal**: Stand up the full backend pipeline (core models/events/IO, ECI + Wikipedia source adapters, composition layer, CLI) and use it to populate the TN reference triple.

- [x] **0.5A — core**: `core/models.py` (Pydantic v2 mirrors of all 8 schemas), `core/events.py` (frozen dataclass events), `core/io.py` (`write_artifact` chokepoint), `core/http.py` (`Fetcher` with tenacity), `core/logging.py` (StructuredLogger). ADR-0004 marked implemented; ADR-0007 added.
- [x] **0.5B — ECI source adapter** (`sources/eci/`): `urls.py`, `partywise.py`, `constituencywise.py` (two-step parser per ADR-0008). Live tests against AcGenMay2026.
- [x] **0.5D — Wikipedia source adapter** (`sources/wikipedia/`): `urls.py` with explicit ECI→Wiki state-name dict, `districts.py` (two-pass with predecessor resolution), `constituencies.py` (minimal per-row, district resolution deferred). ADR-0009.
- [x] **0.5E — pipeline**: `pipeline/compose.py` (`party_lookup_from_partywise`, `compose_result_summary`), `pipeline/run.py` (`run_state_slice` orchestrator), `pipeline/reference.py` (Wikipedia one-shot scrape). CLI commands: `yen-gov run <event> <state>`, `yen-gov reference <state>`. Live e2e smoke (test_pipeline_run_live.py). ADR-0010.
- [x] **0.5F — TN reference data emitted**: `datasets/reference/in/states/S22/districts.json` (38 districts) and `constituencies.json` (234 ACs) generated via `yen-gov reference S22`. Both validate clean.

**Definition of done**: `python -m yen_gov validate` exits 0; pytest 66/66 green; TN reference triple committed.

---

## Phase 1 — One AC end-to-end (DONE as a by-product of 0.5E, 2026-05-08)

The orchestrator + CLI shipped in Phase 0.5E is per-AC capable; the live test in `backend/tests/test_pipeline_run_live.py` exercises Gummidipoondi (S22 AC #1) through the full chain (fetch → parse → compose → validate → write). What 0.5E did NOT ship and Phase 1 originally called for:

- [ ] Frontend Svelte route to render one AC. **Punted** until Phase 3.
- [ ] FastAPI dev server + SSE progress stream. **Punted** — CLI is sufficient for development.
- [ ] Vite static-copy of `datasets/`. **Punted** to Phase 3 frontend work.
- [ ] `docs/how-to/run-the-pipeline.md` — **DONE** (2026-05-09).

---

## Phase 2 — Full state (IN PROGRESS, 2026-05-09)

- [x] State summary parser → `compose_result_summary` (Phase 0.5E).
- [x] Per-AC results loop with bounded sequential fetching → `run_state_slice` (Phase 0.5E).
- [x] Cross-validation: per-AC winners reconcile against partywise → `reconcile_winners_against_partywise` (Phase 2, 2026-05-09). Mismatch raises before any artifact is written.
- [x] "Top-N + others" rule formalized in `config/processing.json` (top 5 + collapsed others). Schema-validated.
- [x] SQLite emitter — DONE Phase 5 (2026-05-09); see ADR-0014 and `docs/reference/sqlite-schema.md`.
- [ ] Multi-AC fixtures (skipped per ADR-0008: live tests preferred over offline fixtures).
- [ ] `docs/concepts/result-aggregation.md` — **DONE** (2026-05-09).

**Definition of done**: full state regenerates deterministically; reconciler agrees with partywise; both JSON outputs validate. SQLite + concepts doc tracked separately.

---

## Phase 3 — Visualization layer

- [ ] State overview: party totals bar, seat-share donut, district-level turnout map (if district GeoJSON feasible).
- [ ] District drill-down: AC list with winner + margin sparkline.
- [ ] Constituency page: top-N candidates bar, vote share, NOTA share, others summary.
- [ ] Party page: seats, margin distribution, narrow-loss list.
- [ ] Optional `/explore` page: lazy-load `sqlite-wasm` for ad-hoc queries.
- [ ] Vitest + Playwright on golden path.
- [ ] Docs: `docs/architecture/frontend.md`, `docs/how-to/add-a-visualization.md`.

**Definition of done**: golden-path tested in a real browser.

---

## Phase 4 — Deployment & CI (DONE, 2026-05-09)

- [x] `ci-checks.yml` — pytest + schema/data validation + frontend build on every PR.
- [x] `deploy-site.yml` — build + stage data per ADR-0013 + publish to Pages + smoke.
- [x] Scraping (`pipeline.yml`) and boundary rebuilds (`boundaries.yml`) removed 2026-05-10 — both are local-only operations (CLAUDE.md §1, §13).
- [x] ADR-0013 (production data placement: CI-side staging).
- [x] `docs/architecture/deployment.md` + `docs/how-to/release.md`.
- [ ] Verify Pages bundle has zero cross-origin fetches — covered by smoke job; live verification pending first actual deploy.

**Definition of done**: workflows committed; smoke job enforces the dev/prod URL contract. Custom-domain / `base` decision deferred to ADR-0014 if a project-Pages URL forces the issue.

---

## Notes

- Each phase starts with re-reading `CLAUDE.md` §1 and §6.
- Anything spanning >3 files in one PR → propose a breakdown first (Level 4+).
- After every phase: grep for `[DEBUG]` (§7), update `docs/`, update this file.

---

## Phase 5 — Socio-economic indicators + national context (DONE, 2026-05-10/11)

Purpose: extend the project from "election-results viewer" toward "compare states across categories" by introducing a generic indicator format and a generic visualization. The election slice and the indicator slice share boundaries, identifiers, and provenance discipline but have independent schemas and pipelines.

- [x] **5A — schemas** (commit c5703e6, 2026-05-10): `indicator.schema.json` (long-form fact table with `value_kind`/`direction`/`scale_hint` metadata), `boundary.sources.schema.json`, governance schema. Three new schemas at v1.0.
- [x] **5B — first ingest** (bd0c208, 2026-05-10): power-plants from `india-geodata` rolled up to ECI states currently in `states.json`. Emitted `datasets/indicators/in/energy/installed_mw_by_state.json`. v1 limitation: only the 4 states with reference data; ~57 upstream state labels unmapped — see `docs/research/energy-power-plants.md` for v2 plan.
- [x] **5C — states.json expansion** (88b8ae4, 2026-05-10): grew from 4 to 35 entries (28 states + 7 UTs). Added `verification_status` enum (`live_url_probe_ok` / `published_authority_only` / `unverified`) per Gregor Hohpe architecture review — Akamai 403'd direct portal probes for 16 codes, so honest typed labels beat fabricated certainty. Schema bumped 3.0 → 3.1. U06 Puducherry intentionally omitted (live portal serves under U07; mystery documented in U07's notes).
- [x] **5D — provenance attribution fields** (3429797, 2026-05-11): additive minor bump on 8 schemas (`election`, `state`, `district`, `constituency`, `party`, `processing`, `result.constituency`, `result.summary`) for optional `sources[].name` + `sources[].authority`. 812 data files migrated.
- [x] **5E — CM term timelines** (440e809 + 6e597cd, 2026-05-11): hand-authored `governments/in/states/{S22,S11,S03,S25}/cm_terms.json`. 16/11/11/10 terms covering 1985–2026, with regime enum (elected/presidents_rule/governors_rule/interim), party_code, alliance, references[].
- [x] **5F — party-colour rework** (10771a8 + 356af4d, 2026-05-11): three-layer model — user override → curated anchor (~13 iconic) → algorithmic OkLCh palette with band-major hue-minor ordering and reserved-hue exclusion. New `colors.forSet(codes)` for one-pass cross-chart de-duplication. Legacy `parties.default.ts` retired. 15 vitest cases.
- [x] **5G — IndicatorChoropleth** (58c5f53, 2026-05-11): generic component driven entirely by indicator metadata. `value_kind` → number formatter; `direction` → ramp hue (teal/red/blue); `scale_hint` → linear/log/symlog; `unit` → legend & tooltip. License badge, time slider, faceted tooltips, 5-stop legend, full SourceList. Wired onto TN state-overview as "National context". 22 vitest cases.

**Definition of done**: 37/37 vitest pass; svelte-check 0 errors; production build succeeds; pushed to origin/main.

---

## Phase 6 — Cross-state comparison + national elections (PLANNED, 2026-05-11)

Purpose: turn yen-gov from "view one state at a time" into "compare states by category". The user mandate (2026-05-11) is explicit: this is the actual product hypothesis. Election data so far is one state's assembly; we also need to ingest national elections (LS-2024) and at least the prior assembly cycle for each of the four covered states, so cross-time and cross-event comparisons are possible.

### 6A — Reviews & propagation (this turn)
- [ ] UI/UX agent review of IndicatorChoropleth (legend semantics, time-slider affordance, mobile breakpoint, colour-direction reading).
- [ ] Citizen agent walkthrough on a mid-tier Android phone (does the National-context section answer a question they'd actually ask?).
- [ ] Governance Strategist review (does aggregating MW by state misrepresent fiscal/energy reality? what indicator categories should we plan for?).
- [ ] Apply priority feedback before propagating.
- [ ] Extend IndicatorChoropleth onto KL/AS/WB state-overview pages.
- [ ] Migrate hot-path multi-party charts (`PartyBar`, `RacesBoard`, `IndiaMap`, `StateAcMap`) from `colors.for(code)` to `colors.forSet(codes)` for cross-chart de-duplication.
- [ ] Indicator icon system: lucide-svelte (already a viable peer dep) or hand-authored SVGs in `frontend/src/lib/icons/indicators/`. Each indicator declares an icon hint (`indicator.icon`); generic fallback when absent. Schema 1.1 minor bump.

### 6B — Documentation sweep (mandatory per user)
- [ ] `docs/architecture/frontend/indicators.md` — new doc covering the indicator data contract, IndicatorChoropleth's metadata-driven rendering, ramp-hue rationale, faceted tooltip behaviour, license-badge surface.
- [ ] `docs/concepts/cross-state-comparison.md` — what it means to compare two states fairly (per-capita normalisation, base-year alignment, unit consistency, fiscal devolution caveats).
- [ ] `docs/architecture/frontend/colours.md` — three-layer party-colour model, ANCHORS rationale, algorithmic palette knobs, when to use `for` vs `forSet`.
- [ ] `docs/architecture/data-sources/elections-india.md` — catalogue of ECI portals (state assembly per cycle, LS general, by-elections), URL templates, what's available pre-2014 vs post-2014, our coverage targets.
- [ ] `docs/architecture/decisions/0005-indicator-as-generic-data-contract.md` — promote the indicator-schema decision out of TODO/SOCIO-ECONOMIC-EXPANSION.md (it meets ADR test (a)+(b): credible alternative was per-indicator schemas; cross-cutting because backend, frontend, and validator all consume it).
- [ ] `docs/architecture/decisions/0006-party-colours-three-layer.md` — anchors + algorithmic + override; cross-cutting (every chart, the settings page, the colour resolver).
- [ ] Update `docs/architecture/data-flow.md` to include the indicators tributary.
- [ ] Update `docs/reference/schemas.md` with the new schemas at their current versions.
- [ ] Memory: persist key design decisions (party-colour, indicator metadata-driven rendering, verification_status enum) into `/memories/repo/`.

### 6C — National elections + prior cycles (data)
- [ ] **Recon**: enumerate ECI portal coverage. State assembly: TN/KL/AS/WB prior cycles (2021/2016/2021/2021). LS general: 2024, 2019, 2014. Note URL patterns (`Pc*` vs `Ac*`), constituency layer (PC vs AC), what fields ECI publishes per cycle (older cycles often have fewer fields). Document in `notes/eci-portal-coverage.md`.
- [ ] Backend: extend `body` enum to admit `lok_sabha`. Add LS constituency reference (PC, 543 seats, ECI codes). Verify per-state PC counts.
- [ ] Pipeline: parameterise `run_state_slice` over body. Emit `datasets/elections/PcGen2024/<state>/...` mirroring the AC layout.
- [ ] Frontend: event-aware StateOverview (selector for AcGenMay2026 vs PcGen2024 vs prior assembly). Default to most recent.
- [ ] Cross-event comparison: swing analysis between consecutive elections (same state, same body, two cycles).

### 6D — Cross-state comparison views
- [ ] **State cards**: a grid of 28 state cards each summarising one indicator (or one election outcome). Sortable + filterable. The "compare two states" view picks two cards.
- [ ] **Ranked tables**: every indicator gets a "states ranked by X" view with per-capita normalisation when a denominator is declared.
- [ ] **Small multiples**: the same indicator over time, one tiny chart per state, on a single page. Lets the citizen spot trajectory differences (is Kerala growing solar faster than TN?).
- [ ] **Category index**: state-level rollup across multiple indicators in a category (energy: installed MW + per-capita kWh + renewable share). Diverging from a national average is the headline.

### 6E — More indicators (data depth)
- [ ] Demographics: total population, density, age pyramid (Census 2011 baseline, NFHS-5 update).
- [ ] Economy: GSDP constant prices (RBI), per-capita NSDP, gross fixed capital formation.
- [ ] Energy: per-capita consumption (CEA), renewable installed MW (MNRE), grid losses (CEA).
- [ ] Health: IMR (NFHS), under-5 mortality, hospital beds per 100k.
- [ ] Education: literacy, GER higher-education (AISHE), pupil-teacher ratio.
- [ ] Infrastructure: road density (MoRTH), rail length (Indian Railways).
- [ ] Each indicator: ingest → indicator.json under `datasets/indicators/in/<category>/...` → render via existing IndicatorChoropleth without new code.

**Definition of done for Phase 6**: a citizen can land on any state's overview, see four assembly elections + the state's standing on six categories of indicators, and click any indicator to compare with another state. All decisions are documented; all reviews (UI/UX, Citizen, Governance) have signed off.
