# Livestock NDLM multi-vintage backfill — follow-up sprint plan

**Last Updated**: 2026-05-26
**Status**: ◻ QUEUED — predecessor plan [TODO/20260525-livestock-ndlm-ingest-plan.md](20260525-livestock-ndlm-ingest-plan.md) CLOSED 2026-05-26 on the FY 2024-25 single-vintage cut. This plan lifts the 32-vintage snapshot corpus already on disk into committed meadow + extends canonical adapters for time-series emission + adds frontend sparkline + year picker rendering.
**Predecessor**: [TODO/20260525-livestock-ndlm-ingest-plan.md](20260525-livestock-ndlm-ingest-plan.md) §11 (Phases 0-3 for FY 2024-25 single-vintage cut; SHIPPED).
**Doc-class routing**: **plan-doc** per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md). Carries phase status + active PRs + TBD only; rationale lives in the predecessor plan's §3-6 + the existing source adapters under `backend/yen_gov/canonical/adapters/livestock/`.

---

## 1. Inputs already on disk

The 2026-05-26 bulk download produced the full corpus and committed nothing yet:

- `.runtime/raw/ndlm/{2010..2025}/` — 16 calendar-year vintages
- `.runtime/raw/ndlm/{2010-11..2025-26}/` — 16 fiscal-year vintages
- 4519 snapshot files (Owner Reg + Pashu Aadhaar + NAIP IV + NADCP) across 36 states
- 18.36 MB total
- `.runtime/raw/ndlm/_summary.json` — per-cell provenance + 11 publisher HTTP 500 failures recorded (all `getOwnerRegLandHoldingByDistrict` on 2025-26 cells; small fraction; document as known-gap in meadow lifts)

All paths are gitignored per [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md) §3. Re-run [tools/ndlm_download.py](../tools/ndlm_download.py) on a clean checkout if the corpus has been purged; takes ~25 min.

## 2. Pre-conditions (BLOCKERS)

Both are Level 4-5 architectural calls per [CLAUDE.md](../CLAUDE.md) §6:

| # | Blocker | Owner | Discharge condition |
| --- | --- | --- | --- |
| 1 | **Sources-seed unfreeze** ([ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) FROZEN 5-row seed → ~48 new rows: 3 useful families × ~16 vintages each) | Hans (governance) + Gregor (architect) | ADR-0032 amended with multi-vintage carve-out; OR ADR-0032 superseded by a new ADR. |
| 2 | **Adapter time-series emit contract** (current adapters emit single-vintage rows; need to extend with vintage-aware lift loop) | Gregor (architect) | Pattern documented in [docs/architecture/data/canonical-store.md](../docs/architecture/data/canonical-store.md) §3 (observation row PK already supports it; what's missing is the adapter-side iteration contract). |

Until BOTH discharge, this plan stays QUEUED. Do not open Phase A PR.

## 3. Useful-vintage matrix (triage from `_summary.json`)

Vintages worth lifting (non-trivial row counts; see `.runtime/raw/ndlm/_summary.json` for per-cell evidence). NADCP + Breeding stay UNLIFTED per the upstream-gap finding in [docs/research/livestock-ndlm-source-availability.md](../docs/research/livestock-ndlm-source-availability.md).

| Family | Useful vintage range | Approx cells per vintage | Notes |
| --- | --- | --- | --- |
| Owner Reg + Land Holding | FY 2015-16 → FY 2025-26 (11 FYs) + CY 2015 → CY 2024 (10 CYs) | 35 states × ~22 districts avg | 11 HTTP 500 cells on FY 2025-26 (Rajasthan + Uttarakhand + others) — document as known-gap in meadow lift |
| Pashu Aadhaar (Animal Registration) | FY 2015-16 → FY 2025-26 (11 FYs) + CY 2015 → CY 2024 (10 CYs) | 35 states × ~25 districts × 10 species facet | Largest corpus; will need per-species meadow shards |
| NAIP IV | CY 2023 → CY 2024 (2 CYs) + FY 2023-24 → FY 2025-26 (3 FYs) | 28 states × ~21 districts × 5 metric-family facet | Older vintages (pre-CY2023) return `totalAIs: 0`; do NOT lift |
| NADCP | (none — closed as TRUE GAP) | — | See [docs/research/livestock-ndlm-source-availability.md](../docs/research/livestock-ndlm-source-availability.md) |
| Breeding | (none — closed as NO PUBLIC API) | — | See [docs/research/livestock-ndlm-source-availability.md](../docs/research/livestock-ndlm-source-availability.md) |

## 4. Phase sketch

Each phase is one or more PRs. Phase A is the ADR work; Phases B-E lift + adapter + frontend in family order.

### Phase A — sources-seed unfreeze (1 ADR PR + 1 sources-seed PR)

1. Amend [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md) (or supersede) with multi-vintage carve-out. Hans + Gregor sign-off in the ADR body.
2. Extend `backend/yen_gov/canonical/livestock_sources_seed.py` from 5 → ~48 rows. One `source_id` per `(family × vintage)` cell that the lift will use. Vintage in the URL field; ledger keeps the FY/CY duality per [§4](#4-cy--fy-carve-out--operational-rule) of the predecessor plan.
3. Tier-A test: every new row resolves to a real `.runtime/raw/ndlm/<vintage>/<endpoint>_state-*.json` file (no orphan source rows).

### Phase B — Owner Reg multi-vintage lift (1 PR)

1. Extend `backend/yen_gov/canonical/adapters/livestock/owner_reg.py` adapter with vintage-aware lift loop iterating over the Useful-vintage range.
2. Write meadow shards at `datasets/livestock/_meadow/ndlm/<vintage>/owner_reg_land_holding_district.json` for each useful vintage.
3. Regenerate `datasets/livestock/livestock_owner_registration.parquet` with all rows.
4. Document the 11 HTTP 500 FY 2025-26 cells as a known-gap header in the relevant meadow files (or omit those states for that vintage and document the omission).
5. Tier-A test: vintage-axis row-count monotonicity (newer vintages have ≥ older vintage counts for the same state, modulo known-gaps).

### Phase C — Pashu Aadhaar multi-vintage lift (1 PR)

Same shape as Phase B but for `pashu_aadhaar.py`. 10-species facet; one meadow shard per (vintage × species) per the existing pattern.

### Phase D — NAIP IV multi-vintage lift (1 PR)

Same shape as Phase B but for `naip_iv.py`. Only 5 useful vintages (CY2023 + CY2024 + FY2023-24 + FY2024-25 + FY2025-26); skip older vintages where `totalAIs == 0`.

### Phase E — frontend time-series rendering (1-2 PRs)

1. Sparkline primitive in `frontend/src/lib/canonical/components/` (or extend existing big-number card with a sparkline). One row per (entity × indicator); X-axis = vintage; Y-axis = value.
2. Year-picker dropdown for the choropleth (defaults to most recent FY; rest of the time-series renders on hover or in detail panel).
3. §13 browser smoke on `/t/agriculture` for one indicator that now carries 5+ vintages.

## 5. NOT in scope

- **NADCP**: CLOSED as TRUE GAP. See research note.
- **Breeding**: CLOSED as NO PUBLIC API. See research note.
- **Pre-2015 vintages**: row counts are 1-2 digit on most states; not worth the meadow weight.
- **Frontend onboarding tour** (Joyride-style) for the new sparkline UX: separate Jony PR.

## 6. Status table

| Slice | Status | Notes |
| --- | :-: | --- |
| Pre-condition #1 (sources-seed unfreeze ADR) | ◻ BLOCKED | Hans + Gregor sign-off needed. |
| Pre-condition #2 (adapter time-series contract) | ◻ BLOCKED | Gregor sign-off needed. |
| Phase A.1 (ADR-0032 amendment) | ◻ QUEUED | After both pre-conditions discharge. |
| Phase A.2 (sources-seed expansion) | ◻ QUEUED | After A.1. |
| Phase B (Owner Reg multi-vintage lift) | ◻ QUEUED | After A.2. |
| Phase C (Pashu Aadhaar multi-vintage lift) | ◻ QUEUED | After A.2. |
| Phase D (NAIP IV multi-vintage lift) | ◻ QUEUED | After A.2; smallest scope. |
| Phase E (frontend time-series) | ◻ QUEUED | After at least one of B/C/D ships. |
