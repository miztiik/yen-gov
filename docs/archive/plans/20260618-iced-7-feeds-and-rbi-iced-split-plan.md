# Plan: ICED 7 new feeds + RBI/ICED publisher split + indicator-definition format

> **ARCHIVED 2026-06-25.** This was a parallel *planning* artifact authored in the `yen-gov-tierb` worktree; it was never merged as a plan-doc. The program it locks shipped on `main` independently via the `ingest` Row-N PR series - the Fetch -> Enrich -> Publish engine (#1167 automated fetch + delta-skip + resume, #1170 enrich gates, #1171 reconcile-iced-producers + run_pipeline, #1172 subsystem docs), the RBI/ICED publisher split (#1168 ICED authority tracing + evidence-gated producer correction), and the 7 ICED energy feeds (#1154 / #1157). The SC-1 publisher-split decision is now doctrine in [CLAUDE.md](../../../CLAUDE.md) (the methodology-incompatible publisher-split anti-pattern); the durable design lives in [docs/architecture/ingest/pipeline.md](../../architecture/ingest/pipeline.md) + [docs/how-to/add-a-new-data-source.md](../../how-to/add-a-new-data-source.md). Preserved here for the SC-1 reasoning and the 6-surface indicator-definition format; the source branch `feat/tierb-rbi-iced-split` was retired.

**Last Updated:** 2026-06-18
**Status:** DESIGN LOCKED (Hans + Fowler consulted 2026-06-18); execution phased below.
**Owner:** Tier-B energy program (worktree `yen-gov-tierb`).

This plan covers three user-ratified directives (2026-06-18):
1. **Split RBI / ICED-NITI** dual-source indicators so the two publishers are never blended.
2. **Fetch + ingest 7 new NITI Aayog ICED energy feeds** (browser/staging fetch authorised).
3. **Define a reusable "data-definition format for topic + indicator"** (Fowler + Hans).
Plus option **(a)**: primary-energy + final-energy national series.

Fetch feasibility is CONFIRMED: the env reaches `https://icedapi.niti.gov.in`; all 7 feeds are staged + decrypt cleanly.

---

## Scope-change ledger (CLAUDE.md section 10)

| Row | Date | Intent (what changed, why, what it overrode) | signoff |
|---|---|---|---|
| SC-1 | 2026-06-18 | Split dual-source `installed-capacity-allocated-mw` + `peak-electricity-demand-mw` into per-publisher indicators (RBI history vs ICED recent), never spliced on one trend line. OVERRIDES the prior ratified "Option 1 SPLICE" decision (plan-doc 20260522 section 3 Q-c, OWID-aligned splice + methodology-break marker). Also supersedes the `upsert_source_scoped` coexist helper shipped in PR #1146 (the split makes one-file source-scoping redundant). Reason given by user: the two publishers must not be combined. | USER 2026-06-18 |

---

## 1. The indicator-definition format (reusable checklist - Fowler)

A new indicator is **6 surfaces**, authored together. This is the format to apply to every feed below.

| # | Surface | Register | Binding fields |
|---|---|---|---|
| 1 | `datasets/data/concepts.csv` (or taxonomy concepts) | what is MEASURED (publisher-agnostic identity) | `concept_id` pk, `noun`, `unit_canonical`, `normalisation` (absolute\|per_capita\|per_area\|share\|ratio\|index), `entity_kinds` |
| 2 | `datasets/data/variables.csv` (compiled from `taxonomy/indicators.json`) | the indicator catalogue row | `indicator_id` pk, `concept_id` FK, `unit`, `derivation`, `topic` FK, `source_id` FK, `update_period_days` (non-null int), `time_min/max`, `entity_kinds` |
| 3 | `datasets/data/datapoints/geo/<indicator_id>.csv` (or faceted sibling) | observations | `entity_id` FK, `time` int, `value`, `source_id` FK. Filename == `indicator_id`. |
| 4 | `datasets/data/entities/source.csv` | provenance (citation grain) | `source_id` pk (DERIVED via `canonical.citation.derive_source_id`), `producer`, `title`, `vintage`, `url` |
| 5 | `datasets/data/indicator_topic_tags.csv` | topic membership (M:N) | `topic_id` FK, `artifact_kind="indicator"`, `artifact_id` |
| 6 | `frontend/src/lib/canonical/indicator-allowlist.ts` | render hints + read wiring (ADR-0045) | descriptor `kind`, `canonical_indicator_id`, `csv_path` (or `faceted_csv_path`+`facet_column`), `meta{title, description, entity_kind, value_kind, direction, attribution_geography, comparability, unit}` |

**Non-optional honesty fields** (decide whether the choropleth lies): `attribution_geography`, `comparability`, `direction`.
**Pre-flight gate:** `python -m yen_gov pre-flight-ingest --proposal-file ...` (ADR-0046) before authoring (concept overlap >=0.70 -> UPSERT not mint; concept FK; no grain prefix; update_period_days; justification; source_id derivation). Exit 2 = abort.

---

## 2. Per-feed decisions (Hans governance + Fowler engineering synthesis)

| Feed | Indicators to mint | Grain / storage | Keep / drop | Honesty caveat |
|---|---|---|---|---|
| **solar_potential** | `solar-potential-mw` (1; pick headline scenario @3% wasteland, do NOT facet - scenarios are not additive) | `geo/*.csv`, time=2025 | DROP power-region rows (SR/NER/ER/WR/NR); keep states + IN | potential = geography not performance; `comparability=snapshot_only`; `attribution_geography=where_produced` |
| **wind_potential** | `wind-potential-mw` (1; headline scenario named in vintage) | `geo/*.csv`, time=2025 | same | same |
| **bio_energy_potential** | `bio-energy-potential-mw` (1; SUM the 2 additive streams biomass+bagasse) | `geo/*.csv`, time=2025 | same | same |
| **ice_ev_vahan** | `ev-share-of-registrations-pct` (1 headline) + optional `geo_by_vehicle_fuel/*` 2-D facet | `geo/` headline; `geo_by_vehicle_fuel/*.csv` PK (entity_id,time,vehicle_category,fuel_category) for the cut | DROP `populationData` (reuse existing `state-population-lakhs.csv`); EV-share not absolute | VAHAN coverage weak pre-~2019 -> coverage caveat / break; share only |
| **captive_power_industry** | `captive-power-capacity-mw` + `captive-power-generation-gwh` (2; state totals) | `geo/*.csv` | DROP 22-industry explosion; defer fuel facet (diesel breaks the 5-bucket enum) | self-reported + under-reported; grid-failure proxy framing |
| **transmission_substation_list** | `substation-capacity-commissioned-mva` (1; national series, faceted by voltage class) | `geo_by_voltage/*.csv` entity_id=IN, time=yearOfCompletion | DROP per-asset rows + `createdAt` (no datetime.now); cannot attribute to state (no state field) | lowest-value feed; national-only is the honest grain |
| **aq_coal_plant_impact** | `coal-capacity-fgd-share-pct` (1 primary) + optional point geojson map | `geo/*.csv` (point-in-polygon geocode plant lat/lng -> state, aggregate); `.geojson` point layer for map | keep; geocode each plant to state | `processing_level=major` (geocode derivation); FGD is moving snapshot -> as-of not trend; report unplaced plants |
| **primary-energy** (opt a) | `primary-energy-supply-mtoe` faceted by source | `geo_by_fuel/*.csv` or national; entity_id=IN | national TPES by source | national-only |
| **final-energy** (opt a) | `final-energy-consumption-mtoe` 2-D sector x fuel | NEW `geo_by_sector_fuel/*.csv` PK (entity_id,time,sector,fuel) | national | national-only; needs the new 2-D class |

**New file-classes to add to `columns.json`** (closed enums on each dimension column):
- `geo_by_vehicle_fuel/*.csv` - PK (entity_id, time, vehicle_category, fuel_category).
- `geo_by_sector_fuel/*.csv` - PK (entity_id, time, sector, fuel).
- `geo_by_voltage/*.csv` - PK (entity_id, time, voltage_class).
- (captive uses single-axis `geo_by_industry/*.csv` only if/when the industry split is un-deferred.)

**Speculative-generality guards (Fowler):** do NOT build an N-axis consolidator (only 2 genuine 2-D cases) and do NOT mint a generic `assets/*` class (only 2 asset families). New 2-D producers call `write_csv` directly into the faceted class. Revisit at the 3rd case. Coal points -> `.geojson` geometry tier, NOT a CSV.

---

## 3. The split (Phase 1) - expand / migrate / contract (Fowler)

Targets: `installed-capacity-allocated-mw` (RBI FY04-14 + ICED FY15-25), `peak-electricity-demand-mw` (RBI + ICED).

| Step | Hat | Action |
|---|---|---|
| 1 | structural | EXPAND: mint per-publisher ids sharing one `concept_id`, each with `meta.justification`: `installed-capacity-allocated-iced-mw` (ICED FY15-25) + `installed-capacity-statewise-total-rbi-mw` (RBI FY04-14, "best-available total, pre-ICED basis, no fuel split"). Same pattern for peak. Write new `geo/*.csv` alongside the combined file. No reader change. |
| 2 | structural | EXPAND: add new allowlist descriptors; keep old descriptor live. |
| 3 | behavioural | MIGRATE: switch topic-page wiring to the new series; the two never share one trend line (distinct colour, NO connecting segment, labelled break band - Hans). Fix cross-ref copy. |
| 4 | structural | CONTRACT: delete old combined catalogue row + csv + old descriptor + **delete `upsert_source_scoped`** (zero callers post-split) once nothing references them. |

CLAUDE.md amendment (Fowler wording) lands with Phase 1: narrow the "never mint for a new publisher" anti-pattern to permit a *deliberate, signed-off, methodology-incompatible publisher-split sharing one concept_id with meta.justification* (default still forbids accidental per-fetch minting; within-series breaks still stay one id + a `methodology_breaks` row).

---

## 4. Execution phases (each = 1+ PR, verified + merged before next)

- **Phase 1 - SPLIT** (allocated + peak; delete `upsert_source_scoped`; CLAUDE.md amendment; SC-1 row). Well-defined; do first.
- **Phase 2 - renewable potential** x3 (`geo/`, single year, drop power-regions, headline scenario).
- **Phase 3 - EV share** (drop population; `geo/` headline + optional `geo_by_vehicle_fuel`).
- **Phase 4 - captive power** x2 (state totals).
- **Phase 5 - coal-AQI FGD-share** (point-in-polygon geocode; `processing_level=major`) + optional point geojson.
- **Phase 6 - transmission** national `geo_by_voltage` MVA-per-year.
- **Phase 7 - primary + final energy** (new `geo_by_sector_fuel` 2-D class for final).

Each feed follows the section-1 6-surface format; each re-derives its `source_id` via `derive_source_id` (idempotent); each ships with tests + an `energy-coverage.md` receipt update. Staging is the operator step (`tools/iced_stage.py`); ingest reads the staged `.runtime/raw/iced/<feed>.json` via `load_iced_response(decrypt=True)`.

## 5. Open follow-ups (Hans -> docs/research/)
- Cite the NITI headline scenario adopted for solar (3% wasteland) + wind (120m vs 150m).
- Confirm `iceEvData.value` = annual new registrations vs cumulative stock (changes the share framing).
- Confirm captive `generation` unit (GWh assumed) + whether sourceWise totals reconcile with stateWise.
