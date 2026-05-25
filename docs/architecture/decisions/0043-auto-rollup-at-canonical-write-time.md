# ADR-0043: Auto-rollup at canonical-write time for sub-state grains

**Last Updated**: 2026-05-25
**Status**: Accepted
**Deciders**: User (autonomous mandate, 2026-05-25 — "If we have, say, even district-level data, we want a state-level aggregated data as well to be shown on a state-level renderer ... if we have new sub-state data, automatically also create the state-level aggregated data") + Fowler (Engineering) + Gregor (Architect) + Max (Indicator Scout) — parallel custom-agent consult 2026-05-25; three-way convergence on SUM-and-COUNT-only policy with same `source_id` reuse.
**Refines**: [ADR-0030](0030-canonical-store-duckdb-wasm.md) §11.4 (D-elections aggressive-materialisation rule). §11.4 named SUM as the canonical use of `derivation="sum"` for elections only; this ADR generalises the policy to every sub-state-grain canonical adapter.
**Refines**: [ADR-0041](0041-meadow-tier.md) §non-negotiable #4 (meadow path vintage MUST equal citation row vintage). Rollup rows synthesise inside the same adapter that reads the district meadow shard; no separate meadow file is created; the same `source_id` / `vintage` flow through both branches verbatim.
**Refines**: [ADR-0042](0042-sources-schema-v3-vintage-as-period-anchor.md) (vintage as strongest period anchor available). The rollup row inherits its upstream district row's `period_label`, `year`, `period_seq`, AND `source_id` 1:1 — vintage is a deterministic function of the same upstream snapshot.
**Plan reference**: [`TODO/20260525-livestock-ndlm-path-a-9pr-sprint-plan.md` PR-B sub-PR breakdown (B.01 / B.02 / B.03)](../../../TODO/20260525-livestock-ndlm-path-a-9pr-sprint-plan.md)

## Context

### What this resolves

PR #281 (2026-05-25) shipped the first **district-grain** canonical family — `livestock_pashu_aadhaar.parquet` carries 3,383 rows × 758 districts × 10 species at FY 2024-25. The data exists; the frontend `indicator-from-canonical.ts` pipeline routes only `entity_kind="state"` descriptors (16 allowlist entries today, all stamped `admin_level: "state"`). Citizens see nothing on `/t/agriculture` despite the canonical rows being on disk.

Two structural problems compound:

1. **No district renderer.** `frontend/src/lib/canonical/indicator-allowlist.ts` has zero `entity_kind="district"` entries; `buildIndicatorArtifact()` hardcodes `admin_level: "state"`. Solving this is a frontend-craft change (Fowler's lane) — addressed by sibling sub-PR **B.02** (Extract Function `entityKindToAdminLevel()` + extend `canonicalEntityToLegacy()`).
2. **Even if (1) lands, the existing state-grain pipeline gains nothing from the district-grain ingest.** A future state-grain `/s/<state>` page that wants Pashu Aadhaar by state must either (a) compute state totals at query time in DuckDB-WASM (extra browser CPU + bandwidth per page-load) OR (b) consume pre-materialised state-rollup rows from the same Parquet.

The user's verbatim mandate is (b): "If we have new sub-state data, automatically also create the state-level aggregated data."

### Three options surfaced

- **α** — Compute-on-read at the state grain. The frontend issues a `SUM(value_numeric) GROUP BY state_prefix` query against district rows. No write-side change; every state-page load pays the aggregation cost. **Rejected**: pushes O(districts) per state-page query into the browser; bandwidth + CPU regression for what should be a constant-time read. ADR-0030 §11.4 already rejected this for elections; the same arithmetic applies here.
- **β** — Materialise at write time, mint NEW state-grain indicator IDs (`state-pashu-aadhaar-count-<species>` alongside `district-pashu-aadhaar-count-<species>`). Same `source_id`, same `vintage`, `derivation="sum"`. **Accepted**: zero browser cost; rollups are first-class observation rows; existing state pipeline picks them up free.
- **γ** — Grain-as-entity-axis (OWID convention). One indicator per (measure, facet); the grain rides on `entity_id`; catalogue stays at 11 not 22 rows; rollups are observation rows under the SAME `indicator_id` keyed by state-grain `entity_id`. **Deferred to a future ADR (Max's Path B research note)**: requires retiring [docs/concepts/indicator-naming.md](../../concepts/indicator-naming.md) §2.2 "entity-prefix mandatory" rule + 60-day deprecation window + 3-PR expand-migrate-contract sequence. Out of scope for the current sprint; the citizen-shipping path cannot wait on a multi-sprint naming convention flip.

### Why δ — the rollup primitive's hard limits

The policy below LOCKS to SUM and COUNT only at the rollup layer. Per-capita, per-area, ratio inversion, weighted means, composite indices, and any rate/share/percentage are **explicitly out of scope**. The moment a contributor wants per-capita-at-state-from-per-capita-at-district, they need a weighted average with population as the weight — that is a JOIN against a separate population indicator and belongs in a future garden-tier (OWID-style curated) layer, not in the same write-time helper that handles pure counts. The forcing function: a Phase 3 contributor who needs per-capita rollup hits "ADR-0043 says SUM and COUNT only — open a separate ADR" and pauses. That is the contract doing its job (Gregor verdict §closing).

### "The One Rule" (CLAUDE.md §0a) — OWID precedent

OWID's `etl/data_helpers/geo.py` (`add_regions_to_table` + per-indicator `aggregations: {region_name: {method: sum|weighted_mean|mean}}` config) auto-rolls sub-national → regional → global at ingest, but EXPLICITLY refuses to default-aggregate any rate/share/percentage. Three OWID conventions yen-gov inherits verbatim (Max verdict Q1):

1. **Coverage threshold + suppression** (out of scope for B.01; see "Out of scope" §3 below).
2. **Pure-count SUM is always safe; weighted-mean is required for rates** (Q3 + Q4).
3. **Aggregates are first-class ENTITIES, not new indicators** — γ above; deferred.

yen-gov implements (2) by enumerating `derivation="sum"` (already shipped in `observation.schema.json` v1.1) at the row level and recording the rollup-ness on a future indicator-catalogue field `rollup_to_parent_geography` (Max recommendation, deferred to a v1.2 additive schema bump). Today the rollup-ness signal lives in the row's `derivation` column + the indicator's `description_long` prose.

## Decision

**Every canonical adapter that lifts sub-state-grain observations MUST emit state-grain rollup rows in the SAME envelope as the district-grain rows it produces.** The rollup is computed inside the adapter by `SUM(value_numeric) GROUP BY (state_prefix, indicator_id, period_label, period_seq)`. Each rollup row:

| Column | Rule |
| --- | --- |
| `entity_id` | State-grain prefix derived by stripping the `-D<n>` (or AC/PC equivalent) suffix from the district `entity_id`. `IN-S01-D502` → `IN-S01`. |
| `indicator_id` | NEW state-grain id minted alongside the district id. Naming: `state-<measure>-<unit>-<facet>` per [D30 grammar](../../concepts/indicator-naming.md). For Pashu Aadhaar: `state-pashu-aadhaar-count-<species>` (10 species children) + `state-pashu-aadhaar-count` (compute-on-read parent, zero rows). |
| `value_numeric` | `SUM(district.value_numeric)` for that state + indicator + period. |
| `period_label` / `year` / `period_seq` | Inherited verbatim from the district rows being summed. All summed rows MUST share the same period triple (validator-enforceable invariant; the adapter raises if not). |
| `source_id` | Inherited verbatim from the district rows. Per [ADR-0032](0032-sources-citation-ledger.md) (citation ledger keyed on `(producer, title, vintage)`): rollup is the same producer's data summed, not a new fetch event → same `source_id`. **NO new citation row is minted for rollups.** |
| `derivation` | `"sum"` (already a legal enum value per [observation.schema.json](../../../datasets/schemas/observation.schema.json) v1.1 lines 76-92). |

### Rollup parent is compute-on-read

The state-grain PARENT indicator (`state-pashu-aadhaar-count`) is compute-on-read per Hans D33.8 — `parent_indicator_id: null`, zero observation rows on disk, frontend SUMs the 10 species children at query time. Mirrors the district parent's shape exactly. Materialising the parent at the state grain would (a) double on-disk footprint per facet axis and (b) break the established symmetry across the energy / iced AQ / livestock-district patterns that already use compute-on-read parents.

### Source_id reuse — citation ledger semantics unchanged

[ADR-0032](0032-sources-citation-ledger.md) v2.0 keys citation identity on `(producer, title, vintage)`. The rollup row's data IS the same producer's data, just summed; same triple → same row → same `source_id`. The derivation provenance lives in TWO places:

1. **The `derivation` column on the observation row.** Machine-checkable; the Tier-A test on this PR asserts every rollup row carries `derivation="sum"`. Citizen-invisible.
2. **The catalogue's `description_long` field on the state-grain indicator.** Citizen-readable prose: "Sum of district-level Pashu Aadhaar tagged-animal counts for animals registered to a district within this state. Aggregated by yen-gov at write time; the underlying citation is the same NDLM Bharat Pashudhan source as the district-grain rows."

A future v1.2 schema bump on `indicator-catalogue.schema.json` MAY add a structured `derivation_note` field for machine-checkable derivation prose; deferred per Max recommendation (rule of three not met yet).

### Catalogue impact

Pashu Aadhaar grows from 11 catalogue rows (1 district parent + 10 district species children) to 22 catalogue rows (+ 1 state parent + 10 state species children). The state-grain rows carry the same `comparability="directional_only"` + `renderer_rules=["no_rank_table"]` honesty surface as the district-grain rows — both flavours are TAGGING counts (NDLM coverage in progress), not population estimates; the rank-table suppression applies identically at both grains.

## Consequences

### Positive

- **Citizens see Pashu Aadhaar on `/t/agriculture` immediately** via the existing 16-entry state pipeline (10 new state-grain allowlist entries added in B.01 commit 2). Zero frontend code change required to ship state-grain rendering — the dispatch already supports it.
- **District-grain rendering remains available** (B.02 + B.03 in subsequent PRs). The two grains coexist as separate indicator IDs; the citizen-UI surfaces both via the standard topic-landing card mechanism.
- **Future district / AC / PC ingests inherit the same recipe.** Financial inclusion (RBI BSR district-grain), assembly election winners (ECI AC-grain), parliamentary election winners (ECI PC-grain), NFHS districts — all follow the same write-time SUM template. The Phase 2 / Phase 3 adapter authors copy-paste 15 lines from `pashu_aadhaar.py` and adapt.
- **No browser-side aggregation cost.** State-page loads issue a single point-query against the materialised state-rollup row; O(1) bandwidth + CPU per state per indicator.
- **OWID-aligned at the row level.** The `derivation="sum"` enum value + `source_id` reuse exactly matches OWID's `processing_level="processed"` semantics for aggregated rows that share an upstream citation.

### Negative

- **Each new sub-state-grain adapter MUST emit the rollup** — discipline cost. If a future adapter forgets, the state-page silently shows no data. Mitigation: every Pashu-Aadhaar-shaped adapter PR ships with a Tier-A test that asserts `state-` rollup rows exist for every district-row state. Pattern is enforced by code, not by reviewer vigilance.
- **Catalogue size grows ~2× for every sub-state-grain family** (11 → 22 for Pashu Aadhaar; comparable doublings for future families). Max's grain-as-entity-axis Path B (γ above) would avoid this at the cost of a multi-sprint naming-convention flip; the explicit trade-off is "ship citizens today, retire the entity-prefix in a future sprint" vs "delay citizens for a cleaner long-term catalogue." User mandate selects the former.
- **Coverage gaps silently undercount.** If 2 of 9 Delhi districts have unresolved entities (PR #281's known SHAHDARA + Mahamaya Nagar case), the Delhi state-rollup SUMs 7/9 districts and reports a value 22% lower than reality. Mitigation today is the `comparability="directional_only"` + `description_long` framing on the catalogue row (the citizen reads "tagged count, NOT actual population — coverage varies by state"); the Max coverage-banner work (3 new observation columns + 80% suppression threshold) is deferred to a v1.2 schema bump per the Out of scope §3 below.

### Out of scope (Hans / Gregor sign-off required to extend)

1. **Per-capita / rate / ratio rollups at the canonical-write layer.** Out of scope today. The moment one is needed, a NEW ADR explicitly enumerates the rollup_strategy enum (`population_weighted_mean`, `area_weighted_mean`, `do_not_rollup` — Max verdict Q3) and a `weight_indicator_id` FK gets added to the catalogue. Until then, indicators where SUM is arithmetically wrong (everything except absolute counts and currency-denominated stocks/flows) MUST stay at the grain the publisher ships them — no auto-rollup.
2. **A reusable `backend/yen_gov/canonical/rollup.py` helper.** Out of scope. Per Fowler's rule of three: Pashu Aadhaar is rollup #1. Inline the 15-line SUM in `pashu_aadhaar.py`. Extract a helper only when the SECOND district family (financial inclusion or election winners) lands AND the duplication is visible. Premature extraction would lock in a shape (`group_by` axis names, NaN handling, source_id inheritance, period alignment) that the second consumer may not fit.
3. **Coverage-banner columns on observation rows.** Out of scope. Max's verdict Q5 recommends a v1.2 schema bump adding `coverage_member_count_observed` / `_expected` / `_fraction` columns + an 80% suppression threshold per OWID convention. Deferred until a multi-family sample-size hand-tuning need surfaces. Today the 2-district Pashu Aadhaar gap is documented in the catalogue prose, not the row-level columns.
4. **Grain-as-entity-axis convention flip (Max Path B).** Out of scope. Filed as a research follow-up at [docs/research/](../../research/) (TBD note: "Path B grain-as-entity-axis indicator-naming.md §2.2 revision"). Hans + Max sign-off + 60-day alias window required. Future ADR.

### Rejected alternatives — preserved for the record

- **α — Compute-on-read at the state grain at query time.** Rejected because it pushes O(districts) work into the browser per state-page load; ADR-0030 §11.4 already rejected this for elections on the same arithmetic.
- **`computed_state_rollup` as a new `derivation` enum value.** Rejected because `derivation="sum"` already shipped in `observation.schema.json` v1.1 lines 76-92 for exactly this case; minting a new enum value would fragment the controlled vocab the schema was designed to avoid (Holy Law #8 "open source first" generalises — prefer the existing primitive over a new one).
- **Per-fetch citation row for the rollup ("a derived row deserves its own source")**. Rejected because [ADR-0032](0032-sources-citation-ledger.md) v2.0 "Rejected D" already settled this: citation ledger is keyed on `(producer, title, vintage)`, not per-fetch-event. Same triple = same row = same `source_id`.
- **`_rollup` suffix on the rollup indicator_id** (e.g. `district-pashu-aadhaar-count-cattle_rollup`). Rejected: the `state-` prefix is already the grain disclosure per D30 grammar; encoding "derivation method" as a suffix would mean three layers (id + entity-prefix + derivation column) carry the same signal — Canonical Data Model anti-pattern. CLAUDE.md §10 already bans encoding topic membership as a prefix on `indicator_id`; the same logic applies to derivation-method suffixes.
- **Optional `admin_level?` on `CanonicalIndicatorDescriptorBase` AND keep the dispatch field separate from `entity_kind`.** Partially rejected — Fowler verdict §"smells to avoid": two fields that must stay in lockstep = invitation to drift. The B.02 dispatch derives `admin_level` from `entity_kind` via a pure-function helper (`entityKindToAdminLevel(kind)`), so the descriptor stays at a single source of truth.

## Doc impact

- **NEW ADR-0043** — this file.
- **UPDATE [docs/architecture/decisions/README.md](README.md)** — append row for 0043.
- **NO change to schemas** — `observation.schema.json` (`derivation="sum"` already legal), `source.schema.json` (no new citation rows; vintage semantics already cover the same-snapshot case), `indicator-catalogue.schema.json` (no new fields). All `x-version` strings unchanged.
- **NO new ADR for the B.02 frontend `admin_level` dispatch** — that change is a subsystem mechanism update (optional-default pattern, precedented by PR-E's `caveats?` shape); per [ADR-0034](0034-documentation-routing-contract.md) routing it lives as a subsystem doc update at [docs/architecture/frontend/canonical-rendering.md](../frontend/canonical-rendering.md) (or the most appropriate existing doc; created in B.02 if absent).
- **FUTURE follow-up** — `docs/research/grain-as-entity-axis-owid-path-b.md` (TBD): Max's Path B verdict captured as a research note for the deferred indicator-naming.md §2.2 retirement.
