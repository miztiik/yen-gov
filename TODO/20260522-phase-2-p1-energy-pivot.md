# Phase 2 P.1 — Energy family pivot

**Last Updated**: 2026-05-22
**Status**: ◻ QUEUED. Hans + Max design pass closed 2026-05-22 (this branch, `refactor/plan-doc-decompose-and-energy-prep`). Three open questions block P.1.A code: (Q-a) entity-scope-as-identity vs. entity-column-only (Hans rule from `indicator-naming.md` §2.4 vs. Max consolidation table); (Q-b) §2b 3-table lock extension to 5 tables (Gregor concurrence); (Q-c) FY04–FY14 RBI long-arc splice vs. drop (Hans methodology-break call). Once resolved, P.1.A opens on a new branch `feat/p1-energy-pivot` from `main` post-merge of the doc-refactor arc.
**Doc class**: plan-doc per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md) — status + active PRs + TBD only; no rationale, no rejected alternatives, no executed-work narrative.
**Cites**: [canonical-store.md §2a–§2b](../docs/architecture/data/canonical-store.md) (disk layout + naming rule) + [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) (D5/D11/D26/D29/D33.8 facet-explode + atomic-fuel + compute-on-read rules) + [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) (sources keyed on `(producer, title, vintage)`) + [topic-taxonomy.md](../docs/concepts/topic-taxonomy.md) + [indicator-naming.md](../docs/concepts/indicator-naming.md) (slug regex + entity-prefix rule).
**Lifted into ledger**: this is the `P.1` row of [`§0e.7` in the slim plan-doc](20260517-canonical-long-format-pivot.md).

---

## §1. Scope summary

41 legacy indicator JSON shards under `datasets/indicators/in/energy/` consolidate to **~22 canonical indicators** across **5 fact-tables** under `datasets/energy/` (extending the §2b 3-table lock by 2 — Q-b open). Net catalogue reduction 46%, mostly from (a) atomic-fuel-only rule retiring TOTAL/THERMAL/composer aggregates per D33.8 compute-on-read, (b) per-distribution-metric fold via `efficiency_dimension` facet, (c) three-way peak-demand near-duplicate collapse to RBI-Handbook long-arc canonical.

## §2. Family decomposition (Q-b — Gregor concurrence open)

The §2b canonical-store.md lock declares 3 energy fact-tables. Max recommends extending to 5 to absorb shards that don't fit the locked 3:

| Fact table | Citizen question | Indicators in P.1 | §2b status |
| --- | --- | --- | :-: |
| `energy/energy_installed_capacity.parquet` | "What kind of plants are in / available to my state?" | `national_installed_capacity_mw` (fuel-faceted), `state_installed_capacity_geographical_mw` (fuel-faceted), `state_installed_capacity_allocated_mw` (fuel-faceted), `national_capacity_pipeline_gw`, `national_thermal_capacity_retired_mw`, `state_renewable_grid_capacity_mw` (source-faceted, P.1.C), `state_rooftop_solar_capacity_mw` (folds into above) | LOCKED |
| `energy/energy_generation.parquet` | "What fuel actually produced our electricity, and how much?" | `state_electricity_generation_gwh` (fuel-faceted), `state_electricity_sales_mu`, `state_plant_load_factor_pct` (fuel-faceted, P.1.C) | LOCKED |
| `energy/energy_distribution_performance.parquet` | "How well does my DISCOM run?" | `state_atc_losses_pct`, `state_distribution_efficiency_pct` (`efficiency_dimension`-faceted), `state_acs_arr_gap_inr_per_kwh`, `state_power_purchase_mix_pct` (`purchase_source`-faceted, P.1.C), `state_rpo_compliance_pct` | LOCKED |
| `energy/energy_demand_supply.parquet` | "Did we get the power we needed?" | `state_peak_electricity_demand_mw`, `state_peak_electricity_supplied_mw`, `state_electricity_requirement_gwh`, `state_electricity_availability_gwh`, `state_per_capita_electricity_availability_kwh`, `state_per_capita_electricity_consumption_kwh` | **EXTENSION** (Q-b) |
| `energy/energy_fuel_consumption.parquet` | "How much coal / oil / primary energy does the country / state consume?" | `state_coal_consumption_mt`, `state_oil_product_consumption_kt` (product-faceted, P.1.C), `national_primary_energy_supply_mtoe` (source-faceted, P.1.C), `national_final_energy_consumption_mtoe` (sector-faceted, P.1.C), `national_renewable_potential_vs_installed_mw` (P.1.C) | **EXTENSION** (Q-b) |

**Dims out of P.1**: `dim_plants.parquet` + `dim_discoms.parquet` are in the §2b lock but neither source is acquired today (NPP for plants; Forum of Regulators for DISCOMs). Defer to Phase 3 per CLAUDE.md §10 "no empty stubs for later."

## §3. Open design questions (resolve before P.1.A code)

**Q-a — Entity scope as indicator identity (Hans + Max + Gregor).** [`indicator-naming.md` §2.4](../docs/concepts/indicator-naming.md) declares "spatial scope is part of identity — two artifacts at different geographies are different indicators." Max's report has `installed_capacity_mw` carry both `entity_id='IN'` and state rows in one indicator. **Recommendation**: honour `indicator-naming.md` — emit `national_installed_capacity_mw` (entity_id='IN' rows only) and `state_installed_capacity_geographical_mw` + `state_installed_capacity_allocated_mw` as separate indicators, all in `energy_installed_capacity.parquet`. Two indicators sharing one fact table is consistent with D5/D11 (row grain identity is what defines the table, not indicator identity). Hans + Gregor co-sign required.

**Q-b — `canonical-store.md §2b` lock extension** to 5 energy fact-tables. Max's rationale: `energy_demand_supply` and `energy_fuel_consumption` cannot fold into the locked 3 without violating §2b rule #2 (identity-vs-occupancy split). Gregor co-sign required; the §2b table is a recorded lock so a §15 paired-test commit must amend it in the same PR as P.1.A.

**Q-c — FY04–FY14 long-arc splice for `state_installed_capacity_allocated_mw`** (Hans). RBI Handbook Table 140 has 20 years of fiscal-year data; CEA per-fuel atomic data starts FY15. Three options: (1) splice — RBI rows for FY04–FY14 with `fuel_type='total_unknown_mix'` sentinel + CEA atomic rows for FY15+, all in one indicator + `methodology_breaks[]` annotation; (2) two id-encoded indicators (`installed_capacity_allocated_base_rbi_pre2015_mw` + `installed_capacity_allocated_base_cea_post2015_mw`); (3) drop FY04–FY14 history (loses long-arc — Roser would refuse). Recommendation: (1) with prominent break-marker. Hans's call before P.1.A.

**Q-d — RBI Handbook `confidence_tier`** under ADR-0032 v2.0 — `gold` (longitudinal compilation) or `silver` (republisher of CEA)? Max recommends `gold` (matches OWID convention where editorial-vetted long-series republisher earns issuing-tier). Hans's call; affects 8 indicators that anchor on RBI.

**Q-e — Splice methodology breaks Hans surfaced**. 8 breaks (B1 Telangana 2014 / B2 Ladakh 2019 / B3 off-grid RE Aug-2021 / B4 UDAY FY15-16 / B5 RBI cosmetic FY19-20 / B6 census-projection post-2012 / B7 coal-total-as-proxy recent FYs / B8 large-hydro definitional carve-out always). B1, B2, B3, B4 promote to `methodology_breaks[]` rows that the renderer surfaces visually (broken line + footnote). Others surface in catalogue `notes` only. Hans + Max sign-off on the 4 promotion-list before P.1.A.

## §4. PR breakdown

Each PR is fused-atomic per CLAUDE.md §15 paired-test discipline (schema bump + Pydantic model + DDL + parquet emit + frontend reader switch + legacy-shard deletion + Tier-B allowlist removal, all in one commit).

| # | PR | Scope | Indicators consumed | Shards retired |
| - | --- | --- | --- | --- |
| **P.1.A** | Foundation — 5-table layout + fuel-mix + reliability + ATC + per-capita-consumption | `national_installed_capacity_mw`, `state_installed_capacity_geographical_mw`, `state_installed_capacity_allocated_mw`, `state_electricity_generation_gwh`, `state_peak_electricity_demand_mw`, `state_peak_electricity_supplied_mw`, `state_atc_losses_pct`, `state_per_capita_electricity_consumption_kwh` | 9 central capacity + 1 state generation + 1 state capacity-by-fuel + 3 peak-demand (drops 2) + 1 ATC + 1 per-capita consumption = ~16 shards |
| **P.1.B** | DISCOM finance + demand/supply extension | `state_distribution_efficiency_pct` (3-facet), `state_electricity_requirement_gwh`, `state_electricity_availability_gwh`, `state_acs_arr_gap_inr_per_kwh`, `state_per_capita_electricity_availability_kwh`, `state_installed_capacity_total_mw` retire-or-splice (Q-c) | ~9 shards |
| **P.1.C** | Fuel + macro + renewable detail | `state_coal_consumption_mt` (re-anchor to Coal Controller), `state_oil_product_consumption_kt` (product-faceted, PPAC), `national_primary_energy_supply_mtoe` (source-faceted), `national_final_energy_consumption_mtoe` (sector-faceted), `national_capacity_pipeline_gw`, `national_thermal_capacity_retired_mw`, `state_renewable_grid_capacity_mw` (source-faceted, includes rooftop), `state_plant_load_factor_pct` (fuel-faceted), `national_renewable_potential_vs_installed_mw` | ~10 shards |
| **P.1.D** | Sweep, retire, validate | `state_electricity_sales_mu` (acquire from CEA), `state_power_purchase_mix_pct` (acquire from PFC + FoR), `state_rpo_compliance_pct` (acquire); confirm 11 retire-list shards deleted; Tier-B allowlist scrubbed for the whole family | ~3 acquires + retirement audit |

**P.1.A pre-flight checklist** (before code):
- Q-a Q-b Q-c resolved (Hans + Max + Gregor)
- New facet-axes registered in `backend/yen_gov/canonical/facet_axes_seed.py` per §8.3 — `fuel_type` enum (`coal, gas, hydro, nuclear, renewable, lignite, diesel`) + extras for P.1.B/C as that PR opens
- 8 new `(producer, title, vintage)` triples authored for `taxonomy/sources.parquet` via `backend.yen_gov.canonical.citation.derive_source_id` — never hand-author the id (CLAUDE.md §10 + ADR-0032)
- Pre-stage grep for the 41 legacy filenames across `backend/`, `frontend/`, `tools/`, `admin/`, `docs/` — quoted file references in frontend loaders ARE production consumers (lesson 2026-05-21 G.1.c)
- `canonical-store.md §2b` amended in the SAME commit as P.1.A (Q-b)

## §5. Corrections-to-on-disk (not new design)

Hans's audit surfaced two categories of defect that lifting bytes to Parquet without fixing would cement into the canonical store:

- **9 of 41 shards have WRONG `attribution_geography`** today. `where_administered` is overused as a catch-all. High-risk citizen-misreading: `state_installed_capacity_geographical_mw` is tagged `where_administered` (citizen sees Chhattisgarh-as-administrator); should be `where_produced`. `state_installed_capacity_with_alloc_mw` is tagged `where_administered`; should be `where_allocated`. `state_electricity_generation_mu` is tagged `where_administered`; should be `where_produced`. Re-tag during P.1; defend each value in catalogue `notes` (one sentence: "this counts plants by physical site, not by allocation").

- **~⅔ of indicators get `implementing_authority` re-labelled.** Distribution-side metrics move from `state` to `concurrent` (UDAY transferred discom-debt burden to centre; ATC/billing/collection improvements cannot be attributed cleanly to state utility management). Per-capita availability moves from `state` to `concurrent`. RPO compliance moves from `state` to `concurrent`. Capacity (capacity-by-fuel) moves from mixed labels to uniform `joint`.

These are factual corrections; lifting them to Parquet under the old labels would cement Hans's blame-instinct + single-perspective Rosling failures into the citizen surface.

## §6. Hard drops

| Shard | Reason |
| --- | --- |
| `installed_mw_by_state.json` | Community-curated GeoJSON, 4 of 35 states (TN, KL, AS, WB). Holy Law #9 issuing-authority fail. Already covered by `state_installed_capacity_geographical_mw`. |
| `state_peak_electricity_demand_mw.json` (ICED 1-year snapshot) | Strictly a subset of the RBI Handbook 12-year canonical (`state_peak_electricity_demand_mw`). |
| `state_electricity_peak_demand_mw.json` (ICED 9-year tail) | Same noun as RBI Handbook canonical; tail-end years (FY24 onward) reconcile into the canonical RBI indicator as additional observation rows, not a separate indicator. |
| `state_electricity_generation_mu.json` | MU = GWh equivalence; alias of `state_electricity_generation_gwh` (kept as `id_aliases[]` entry for one release). |
| `installed_capacity_total_mw.json` | Aggregate; compute-on-read per D33.8. |
| `installed_capacity_thermal_mw.json` | Aggregate; compute-on-read per D33.8. |
| `installed_capacity_by_source_mw.json` | Composer (pipeline UNION of 7 per-fuel shards); writer rebuilds at emit. |
| `state_installed_capacity_total_mw.json` | Aggregate; compute-on-read. Long-arc FY04–FY14 history is preserved or dropped per Q-c. |
| `state_installed_capacity_with_alloc_mw.json` | Total-row of `state_installed_capacity_allocated_mw` (fuel-faceted version); retire after fuel-faceted version is validated. |

## §7. Tests + verification gates (Tier-A + Tier-B per CLAUDE.md §15)

- **Tier-A (mandatory at P.1.A commit)**: `pytest -q` in `backend/` green; `npm test` in `frontend/` green; `npm run test:e2e` in `frontend/` green; schema-bump compliance check (`indicator.schema.json` `x-version` matches `$schema_version` on all 41 → ~22 catalogue rows).
- **Tier-B (mandatory before commit)**: `python -m yen_gov validate --root .` clean — no schema violations, no Tier-B forbidden-path matches on the legacy-folded-indicator-shards allowlist after P.1.A's retire-list is scrubbed.
- **§13 browser smoke**: minimum 3 routes — `/topic/energy` landing + 2 state pages (Tamil Nadu = energy-heavy producer with capacity-vs-consumption story; Bihar = high-AT&C-loss DISCOM story). Snapshot read-page + screenshot. New console errors / 404s = blocker.
- **Parity oracle** (custom for P.1.A — pattern from /memories/lessons.md 2026-05-19): for each surviving canonical indicator, assert one observation row from canonical Parquet equals the corresponding pre-pivot JSON shard row for ≥3 state-year cells per indicator. ~50 cells total; ~5s wall-clock. Catches any silent scramble during the lift.
- **Manifest regen + byte-stable check** (lesson 2026-05-20 P.0e): after P.1.A's writer run, `python -c "from yen_gov.canonical.writer import _regenerate_manifest; _regenerate_manifest(Path('datasets'))"` then `git diff datasets/manifest.json` to confirm on-disk size matches manifest claims.

## §8. Strangler-fig handoff

P.1.A lands additive (new Parquet emitted; legacy JSON shards still on disk). P.1.A reader switch (`/topic/energy` route flips to canonical Parquet via DuckDB-WASM). P.1.A retire (`git rm` the 16 shards consumed by P.1.A + scrub Tier-B allowlist). Done in **one commit** per the elections-pivot precedent — all consumers in this repo are yen-gov-owned, no external readers, no strangler ceremony beyond the additive-first-then-rm pattern.

## §9. Cross-refs

- [Slim plan-doc §0e.7 P.1 row](20260517-canonical-long-format-pivot.md)
- [canonical-store.md §2a + §2b](../docs/architecture/data/canonical-store.md)
- [ADR-0030 D26 / D29 / D33.8](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md) (facet-explode + atomic-fuel + compute-on-read)
- [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) (sources v2.0)
- [topic-taxonomy.md](../docs/concepts/topic-taxonomy.md)
- [indicator-naming.md](../docs/concepts/indicator-naming.md) (slug rules, esp. §2.4 entity-scope-as-identity)
- [G.1 closeout lesson](/memories/lessons.md 2026-05-22) — strangler-fig 3-PR discipline + pre-stage repo-wide grep
- [P.0e closeout lesson](/memories/lessons.md 2026-05-20) — manifest regen byte-stable check
- [PR-R.2 lesson](/memories/lessons.md 2026-05-19) — parity-oracle pattern for consumer-data-layer swaps
