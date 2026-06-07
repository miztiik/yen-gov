# Energy + livestock CSV migration sub-plan

**Date**: 2026-06-07
**Status**: **DESIGN-LOCKED** (per Explore subagent audit 2026-06-07; ship deferred to per-family PRs)
**Parent**: [TODO/20260603-data-and-charting-platform-reset-plan.md](20260603-data-and-charting-platform-reset-plan.md) "Energy + livestock family CSV migrations (out of original plan scope)" deferred item
**Companion**: [TODO/20260607-x1a-followup-2-residual-parquets-subplan.md](20260607-x1a-followup-2-residual-parquets-subplan.md) (same architectural shape question; coordinated rollout)

## Premise

The 9 energy + livestock parquets all carry the canonical observation shape (`entity_id, year, period_label, period_seq, indicator_id, value_numeric, value_text, source_id, derivation`). The CSV destination shape (4 columns `entity_id, time, value, source_id` per file class `datasets/data/datapoints/geo/*.csv`) requires a **fan-out** from one parquet (carrying many `indicator_id`s) to many CSVs (one per `indicator_id`).

**Verified 2026-06-07** (Explore subagent audit):
- All 9 parquets ALREADY have CSV siblings emitted at `datasets/data/datapoints/geo/<indicator_id>.csv` (67 energy CSVs + 20 livestock CSVs + ~30 others = 115 files total).
- The B2b parity tests at `backend/tests/test_csv_parquet_parity.py::test_energy` + `::test_livestock` GREEN on the existing tree.
- The reingest writers `backend/yen_gov/canonical/reingest/{energy,livestock}_datapoints.py` are PRODUCTION-READY (used by tests).
- **BUT**: the frontend reader path still queries the parquet via `loadSingleFromCanonical` → `registerTable(descriptor.table_id)` → `read_parquet(...)` → `WHERE indicator_id = <id>`. The CSV per-file shape (no `indicator_id` column inside each CSV) needs a different reader contract.

## The architectural fork

This is the same question that X1a-followup-2 sub-rows A + C + D + E face: **how does `loadSingleFromCanonical` resolve `descriptor.table_id` when the canonical store is per-indicator CSV instead of wide parquet?**

Three options:

| Option | Shape | Cost | Reversibility | Recommendation |
| --- | --- | --- | --- | --- |
| **R1**: extend `registerCsvAsTable` to UNION-ALL per-indicator CSVs into a synthetic wide view at registration time | Frontend executes `UNION ALL SELECT 'pashu-aadhaar-count-cattle' AS indicator_id, * FROM read_csv('...')` across N children at registration. View shape mirrors parquet. | High (N+1 HTTP fetches per family per session; significant SQL plan complexity in DuckDB-WASM) | Low (the synthetic-view shape becomes load-bearing) | **NO** - reintroduces the wide-parquet pattern with extra request overhead. |
| **R2**: rewrite `loadSingleFromCanonical` to resolve `descriptor.canonical_indicator_id` directly to a CSV URL (`datasets/data/datapoints/geo/<indicator_id>.csv`), drop the table_id indirection for canonical CSV indicators | Frontend executes `SELECT entity_id, time, value, source_id FROM read_csv('datasets/data/datapoints/geo/<id>.csv', columns={...})` directly. ONE fetch per indicator. | Medium (rewrite the adapter + extend allowlist descriptor with a per-CSV path; per-family ship is 1 file each per side) | High (per-indicator CSV is the canonical SoT; if a family ever needs the wide shape it's a new view) | **YES** - matches the per-file-class contract; OWID precedent; minimum HTTP. |
| **R3**: drop the canonical-allowlist + indicator-from-canonical adapter entirely; flip each consumer to read directly from `data/datapoints/geo/<id>.csv` | View-models query CSV directly; no `IndicatorArtifact` shape; renderer surface changes. | Very high (renderer rewrite) | High but blast radius is the renderer surface, not just the data path | **NO** - the existing IndicatorArtifact shape is load-bearing for IndicatorCard / IndicatorChoropleth / IndicatorRanked / IndicatorSmallMultiples; cannot retire without rewriting all 4 renderers. |

**Recommendation: R2** (the user-direct CSV path) is the destination per parent plan section 22.4 #4 "explicit `read_csv(columns=...)` + write-time validator; never `read_csv_auto`".

## Per-family ship sequence (after R2 lands)

R2 is a single architectural commit (estimated +200 LOC + tests + §13 smoke). Each family ships AFTER R2:

| Family | Indicators | Allowlist descriptors | Cost | Ship gate |
| --- | --- | --- | --- | --- |
| **Livestock - pashu_aadhaar** | 10 species + 1 parent | 1 existing (`pashu-aadhaar-count`) + 10 children | Trivial post-R2 (descriptor key swap from `table_id` to `csv_path`) | parity oracle + §13 smoke on `/india/karnataka` |
| **Livestock - owner_registration** | 6 landholding brackets + 1 parent | NEW allowlist entries (7 total) | Medium (new descriptors) | parity oracle + §13 smoke |
| **Livestock - naip_iv** | 4 NAIP IV indicators | NEW allowlist entries | Medium | parity oracle + §13 smoke |
| **Energy - demand_supply** | 7 indicators | 7+ existing descriptors | Trivial post-R2 | parity oracle + §13 smoke on welfare/energy pages |
| **Energy - generation** | 7 fuel facets + 1 parent | 8 existing descriptors | Trivial post-R2 | parity oracle + §13 smoke |
| **Energy - installed_capacity** | 7 fuel facets + 1 parent | 8 existing descriptors | Trivial post-R2 | parity oracle + §13 smoke |
| **Energy - distribution_performance** | 4+ indicators | 4 existing descriptors | Trivial post-R2 | parity oracle + §13 smoke |
| **Energy - fuel_consumption** | 5+ indicators | descriptor count TBD | Medium | parity oracle + §13 smoke |
| **Energy - capacity_pipeline** | thermal pipeline indicators | descriptor count TBD | Medium | parity oracle + §13 smoke |

After all 9 families ship: `git rm` the 9 parquets + drop the writer modules (`backend/yen_gov/canonical/adapters/{energy,livestock}/__init__.py::build_envelopes()`) + drop the parity tests (the wide-parquet they oracle-against will be gone).

## Out of THIS session's scope

This session's directive ("DO NOT WAIT FOR REMOTE PR MERGE. IF LOCAL testing is successful move forward") authorises shipping. But R2 itself is a Level-4 architectural change (per CLAUDE.md section 6 correction levels) — it changes the contract surface that 50+ allowlist descriptors depend on. Per umbrella plan section 22.3 #7 + the Status Reckoner discipline, R2 needs:
- Gregor verdict on the per-CSV path contract.
- Fowler verdict on the rollout safety (per-family or per-descriptor flip).
- §13 smoke on EVERY existing canonical-backed indicator before the final cutover.
- A `dual-read-parity` style harness that registers BOTH parquet and CSV per descriptor and asserts equality.

Each is 1-2 sessions of work. This sub-plan is the design hand-off; the SHIP is the next session.

## Status

**DESIGN-LOCKED** (R2 chosen). No code changes in this commit. Companion to X1a-followup-2 sub-rows A + C + D + E (same architectural shape question; R2 SHOULD subsume those reader-flip patterns too).

**Reopening trigger**: a session opens dedicated to R2; Gregor + Fowler + Hans + Max persona debate ratifies the per-CSV path contract; ship rolls out family-by-family per the table above.

**Estimated total session count after R2 lands**: 1 + 9 = 10 PRs (the R2 architectural one + 9 per-family) over ~3-5 sessions. Each per-family PR is small + sandbox-testable + reversible. Per the user's 2026-06-07 "no remote PR wait" directive, all 10 can ship locally.
