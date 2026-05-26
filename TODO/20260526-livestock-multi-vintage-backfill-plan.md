# Livestock NDLM multi-vintage backfill — follow-up sprint plan

**Last Updated**: 2026-05-26 (Phases A+B+C+D SHIPPED for FY cut; CY cut and Phase E carried forward)
**Status**: 🟢 RESOLVED — single-PR ship; FY 2010-11..2025-26 (16 vintages) lifted into committed meadow + canonical regenerated + 44 indicator catalogue rows reframed to citizen-honest multi-vintage methodology. CY-vintage lift and frontend sparkline / year-picker (Phase E) carried forward as separate PRs.
**Predecessor**: [TODO/20260525-livestock-ndlm-ingest-plan.md](20260525-livestock-ndlm-ingest-plan.md) §13 (Phases 0-3 for FY 2024-25 single-vintage cut; SHIPPED earlier).
**Doc-class routing**: **plan-doc** per [ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md). Architectural verdict is folded inline below; rationale lives in the predecessor plan's §3-6 + the source adapters under `backend/yen_gov/canonical/adapters/livestock/`.

---

## 1. Inputs already on disk

The 2026-05-26 bulk download produced the full corpus:

- `.runtime/raw/ndlm/{2010..2025}/` — 16 calendar-year vintages
- `.runtime/raw/ndlm/{2010-11..2025-26}/` — 16 fiscal-year vintages
- 4519 snapshot files (Owner Reg + Pashu Aadhaar + NAIP IV + NADCP) across 36 states
- 18.36 MB total
- `.runtime/raw/ndlm/_summary.json` — per-cell provenance + 11 publisher HTTP 500 failures recorded (all `getOwnerRegLandHoldingByDistrict` on 2025-26 cells; small fraction; documented as known-gap)

All paths are gitignored per [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md) §3. Re-run [tools/ndlm_download.py](../tools/ndlm_download.py) on a clean checkout if the corpus has been purged; takes ~25 min.

## 2. Pre-conditions — RESOLVED (no ADR work needed)

Both pre-conditions were stress-tested with Hans (Governance) + Max (Indicator Scout) + Explore subagent (thorough recon) and converged on a single verdict: **the 5-row NDLM source ledger stays at 5 rows; the multi-vintage time-series is carried in observation-row `period_label`, not as new citation rows.**

| # | Pre-condition (queued 2026-05-26) | Verdict (2026-05-26) | Owner of verdict |
| --- | --- | --- | --- |
| 1 | Sources-seed unfreeze (5 → ~48 rows) | **NOT NEEDED.** [ADR-0042](../docs/architecture/decisions/0042-sources-schema-v3-vintage-as-period-anchor.md) v3.0 binds: for live-fetch endpoints, **one citation row per (producer, endpoint, operator snapshot window)**; the year-of-data is a column in the dataset, not a citation row axis. This matches OWID's `origin` convention verbatim (Max-verified, [docs/concepts/owid-alignment.md](../docs/concepts/owid-alignment.md)). The 5 NDLM citation rows (one per endpoint) keep `vintage="2026-05"` and serve all 16 FY data rows uniformly. | Hans + Max + Explore |
| 2 | Adapter time-series emit contract | **RESOLVED in-PR.** The 3 livestock adapters (`owner_reg.py`, `pashu_aadhaar.py`, `naip_iv.py`) now glob-discover snapshot dirs at lift time via `discover_meadow_snapshots(repo_root, source="ndlm")` in `_shared.py`. Per-vintage source_id is built via `source_id_for(nickname, vintage)` which calls `derive_source_id(producer, title, vintage)` per [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md). No hardcoded `MEADOW_VINTAGE` constants remain. | Gregor (folded into this PR) |

## 3. Useful-vintage matrix (FY-only this PR; CY deferred)

The FY cut shipped this PR; the CY cut is deferred until vintage-type CLI flags or separate CY-slug indicators are introduced (the canonical inventory deriver currently rejects mixing CY+FY in one indicator due to year vs year_month period shapes).

| Family | Vintage range this PR (FY) | Row count delta vs 1-vintage baseline |
| --- | --- | --- |
| Owner Reg + Land Holding | FY 2010-11 → FY 2025-26 (16 FYs) | 30,272 (was ~12,000; ~2.5x) |
| Pashu Aadhaar | FY 2010-11 → FY 2025-26 (16 FYs) | 27,360 (was ~3,000; ~9x) |
| NAIP IV | FY 2010-11 → FY 2025-26 (16 FYs) | 7,392 (was ~2,940; ~2.5x) |
| Total observation rows | — | **65,024** |

11 publisher HTTP-500 cells on FY 2025-26 are silently absent in the meadow (documented in the bulk-download summary); rows simply don't exist for those cells. NDLM portal rollout was ~2018, so earlier FY rows carry small or zero values where the registry was not yet operating — all 44 indicator descriptions now spell this out per Hans' citizen-honest framing.

## 4. Phase outcomes (single-PR ship)

| Phase (orig plan) | Outcome | Detail |
| --- | --- | --- |
| Phase A (sources-seed unfreeze ADR + expansion) | 🟢 SUPERSEDED | No ADR change; no seed expansion. ADR-0042 already binds. Hans + Max + OWID verdict in §2 above. |
| Phase B (Owner Reg multi-vintage lift) | 🟢 SHIPPED | 30,272 rows in `livestock_owner_registration.parquet`. |
| Phase C (Pashu Aadhaar multi-vintage lift) | 🟢 SHIPPED | 27,360 rows in `livestock_pashu_aadhaar.parquet`. |
| Phase D (NAIP IV multi-vintage lift) | 🟢 SHIPPED | 7,392 rows in `livestock_naip_iv.parquet`. |
| Phase E (frontend time-series UX) | ⏭ DEFERRED | Sparkline primitive + year-picker dropdown; separate Jony PR. The new rows render today via the existing big-number-of-most-recent-vintage flow; the additional vintages become visible when the picker ships. |
| CY-vintage lift (16 calendar-year vintages) | ⏭ DEFERRED | Inventory deriver rejects mixed CY+FY in one indicator (year vs year_month period shapes). Choose either (a) separate `*-cy-*` indicator slugs OR (b) vintage-type CLI flag on the meadow tools, then ship as Phase F. |

## 5. Architectural hardcode fixes folded into this PR

User mandate 2026-05-26: "I'm assuming you are fixing architecturally the hard coded values as well. So that we don't hard code and chase our tails in the future."

The following hardcoded values were eliminated in the same PR as the data lift (no separate follow-up needed):

- **3 livestock adapters** (`naip_iv.py`, `owner_reg.py`, `pashu_aadhaar.py`): `MEADOW_VINTAGE = "2024-25"` constant removed; replaced by `discover_meadow_snapshots(repo_root, source="ndlm")` glob-discovery + per-vintage `source_id_for(nickname, vintage)` lookup.
- **3 livestock meadow tools** (`tools/livestock_meadow_*.py`): `DEFAULT_RAW_VINTAGES` constant removed; auto-discovers FY-shaped raw vintage dirs from `.runtime/raw/ndlm/`. `MEADOW_VINTAGE` constant replaced by tunable `MEADOW_SNAPSHOT_DEFAULT` operator knob exposed as `--meadow-snapshot` CLI flag.
- **Sources seed** (`livestock_sources_seed.py`): hand-typed `SOURCE_IDS` dict in `_shared.py` replaced by `LIVESTOCK_NICKNAME_TO_PRODUCER_TITLE` export from the seed module (single source of truth for the 5 (producer, title) pairs); back-compat `SOURCE_IDS` alias retained as a transitional dict.

## 6. NOT in scope (carried forward as future PRs)

- **CY-vintage lift** (16 calendar-year vintages): see §4 deferred row.
- **NADCP**: CLOSED as TRUE GAP. See research note.
- **Breeding**: CLOSED as NO PUBLIC API. See research note.
- **Frontend Phase E (sparkline + year picker)**: separate Jony PR. The new vintages live on disk + in the parquets today; the year-picker UI exposes them to citizens.
- **`renderer_rules += ["annotate_programme_launch_year"]`** band-annotation primitive for pre-2018 NDLM rollout: Hans-flagged future Jony PR.

