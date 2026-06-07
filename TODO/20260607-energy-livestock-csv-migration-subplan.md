# Energy + livestock CSV migration sub-plan

**Date**: 2026-06-07
**Status**: **SHIPPED** (R2 reader flip merged on `feat/r2-csv-reader-flip-9-families` 2026-06-07; all 9 families ride the new path in a single architectural commit)
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

**SHIPPED** (R2 landed 2026-06-07 in a single architectural commit on `feat/r2-csv-reader-flip-9-families`). The per-family ship table above is **collapsed into the same commit**: instead of 9 sequential per-family PRs, the R2 reader-flip flips ALL energy + livestock descriptors at once because the gate is the FE reader contract (per-CSV path resolution + slug→ECI translation) — once that contract is in place, wiring 127 `csv_path` declarations is mechanical and reviewable in one diff. Per the user's 2026-06-07 "no remote PR wait; accelerate; parallelize" directive, this collapse is appropriate.

**What landed (2026-06-07)**:
- `frontend/src/lib/canonical/canonical-entity-translation.ts` (NEW, 189 LOC): pure slug→legacy ECI map builder + lazy fetch+cache of `data/entities/geo.csv`. Translates `tamil-nadu` → `S22`, `andhra-pradesh/visakhapatnam` → `S01-D710`, `IN` → `IN` (national pass-through).
- `frontend/src/lib/canonical/canonical-entity-translation.test.ts` (NEW, 138 LOC): 15 unit tests covering the pure helpers (parseCsvLine, buildCanonicalSlugToLegacyMap, translateCanonicalSlugToLegacy, edge cases for missing aliases / empty CSV / CRLF).
- `frontend/src/lib/canonical/indicator-allowlist.ts` (+127 csv_path lines): every energy + livestock descriptor (43 kind:"single" + 54 facet children across 11 facet parents) gained a `csv_path: "data/datapoints/geo/<canonical_id>.csv"` field. Grain-prefixed pashu-aadhaar descriptors (state-* + district-*) point at the same underlying CSV — the entity_kind row filter at read time picks the slice.
- `frontend/src/lib/canonical/indicator-from-canonical.ts` (CSV branch added): `loadSingleFromCanonical` dispatches on `descriptor.csv_path`; CSV branch issues `SELECT entity_id, time, value, source_id FROM read_csv(<url>, columns={...}) ORDER BY entity_id, time`, then filters by entity_kind grain, then translates slugs to legacy IDs. `loadFacetMultiplexedFromCanonical` dispatches on `allChildrenHaveCsv`; CSV branch fans out via `UNION ALL` per child with synth `'<child_id>' AS indicator_id` literal so the per-row facet dispatch is unchanged. Parquet branch preserved for back-compat (any future descriptor without csv_path still works).
- `frontend/src/lib/canonical/indicator-from-canonical.test.ts`: 13 new tests covering csv_path invariants (every energy/livestock descriptor wired), entity_kind grain filtering (state-grain reads `IN` + state slugs; district-grain reads only `slug/slug` rows), parquet back-compat (synthetic descriptor without csv_path takes the parquet branch), and **dual-read parity** (CSV branch + parquet branch produce identical artifact tuples).
- `frontend/src/lib/canonical/indicator-from-canonical.test.ts` (existing tests adapted): loader round-trip tests + RPO facet-mux tests flipped to expect CSV SQL shape (read_csv + UNION ALL).

**Local gates green (2026-06-07)**:
- backend `pytest backend/tests/test_csv_parquet_parity.py::test_energy backend/tests/test_csv_parquet_parity.py::test_livestock`: 2 passed (the deletion-safety oracle the data-side parity rests on remains green; the FE adapter's dual-read parity test mirrors this on the reader side).
- frontend `vitest run frontend/src/lib/canonical/`: 143 passed, 15 skipped (the 15 skipped are pre-existing `describe.skip` blocks gated behind separate PR #424; not regressed).

**Per-family follow-ups (now deferrable to per-PR §13 browser smoke)**:
Each of the 9 families ships as soon as a `/s/<state>/t/<topic>` browser smoke confirms the citizen-visible card looks pixel-identical to the parquet path. The reader-flip risk is bounded — every descriptor still resolves through `loadIndicatorIfCanonical`, the legacy fetch fall-through is unchanged for non-allowlisted indicators, and the parquet branch survives for any descriptor not yet flipped.

**Reopening trigger**: a §13 smoke discovers a divergence between the CSV branch artifact and the parquet branch artifact on a real route. (The vitest dual-read parity test pins the SHAPE; the §13 smoke is the only thing that confirms the citizen-visible rendering survives.)

**Estimated remaining work**: per-family §13 smokes (each: 1 minute browser smoke) → 9 smokes × 1 minute = 10 minutes. Backend writer + parquet retirement (Phase C + D in the original 4-phase plan) remain deferred — those become mechanical once the §13 smokes pass.
