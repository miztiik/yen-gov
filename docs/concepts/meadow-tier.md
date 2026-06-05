# Meadow tier

**Last Updated**: 2026-05-25

## What it is

The **meadow tier** is the third of yen-gov's five data layers, adopting the OWID `etl/meadow/` vocabulary verbatim per CLAUDE.md §0a "The One Rule." Meadow files are **typed, schema-validated, deterministic, FK-bearing JSON rows parsed from upstream — but pre-canonical**.

They are NOT citizen-facing. They are the backend canonical adapter's input. The frontend MUST NOT fetch them.

## The five tiers

| Tier | Location | Lifecycle | Frontend reads? |
| :-: | --- | --- | :-: |
| 1. Upstream | Publisher servers (ECI, RBI, CEA, MoSPI, …) | External; outside repo | No |
| 2. Snapshots | `.runtime/raw/<source>/...` (gitignored) | Ephemeral per-run | No |
| 3. **Meadow** | `datasets/<family>/_meadow/<source>/<vintage>/<file>.json` | Committed | **No** |
| 4. Canonical | `datasets/<family>/<family>_<role>.parquet` + `datasets/taxonomy/*.parquet` | Committed | **Yes** (via DuckDB-WASM) |
| 5. Grapher | `frontend/src/lib/**/*.svelte` + view-models | Committed | Yes (renders citizen UI) |

Snapshots → meadow is parsing + typing. Meadow → canonical is sub-fuel collapse, methodology splice, axis join, dimension lift — the editorial work that earns the citizen-facing badge.

## Why a named layer

The meadow tier existed in yen-gov from day one — under the misleading path `datasets/indicators/in/<topic>/<id>.json`. It looked citizen-facing (no underscore prefix, no `_ops/` segregation, lived under `datasets/`) but was always backend-internal. The mismatch produced three structural problems:

1. **Three-way node ambiguity** — same file was ingest output + canonical input + (deprecated) frontend reader input.
2. **Phase-C blast-radius trap** — `git rm` of a "legacy" shard silently broke canonical adapter input; only signal was the next lift emitting an empty Parquet.
3. **Naming imprecision** — "legacy folded-indicator shard" is project-specific archaeology; "meadow" is OWID's exact name for the role.

Per [ADR-0041](../architecture/data/canonical-store.md#adr-0041-meadow-tier) the layer is renamed in-place to its OWID identity.

## Meadow contract (one paragraph per guarantee)

1. **Schema-valid**: typed JSON conforming to an existing per-family schema under `datasets/schemas/`. No new schemas; meadow reuses what the legacy shards already validated against.
2. **Deterministic**: identical upstream bytes → identical meadow file bytes on re-run. No `datetime.now()` in content (CLAUDE.md §10 anti-pattern).
3. **FK-bearing**: every observation row carries a `source_id` FK to `datasets/taxonomy/sources.parquet` per CLAUDE.md §12 + [ADR-0032](data-provenance.md#adr-0032-sources-citation-ledger).
4. **Vintage-anchored**: the `<vintage>` segment in the path MUST match the `vintage` field of the citation-ledger row that the row's `source_id` resolves to. (Tier-B check, lands in PR 7c-4.)
5. **Backend-internal**: frontend MUST NOT `fetch()` meadow paths. Enforced by `_meadow/` underscore-prefix (CLAUDE.md §2 "private" convention) + CLAUDE.md §4 layer rule + Tier-B validator + Phase B allowlist routing all citizen reads to canonical Parquet.

## Path convention

```
datasets/<family>/_meadow/<source>/<vintage>/<file>.json
```

- `<family>` — indicator family, matches the canonical Parquet family name. Example: `energy`, `demography`, `fiscal`, `health`, `schemes`.
- `<source>` — short producer identifier, snake_case. Example: `rbi`, `cea`, `iced`, `eci`, `nfhs`, `pfms`.
- `<vintage>` — the source's own period label (publisher-native). Example: `2024-25` (RBI fiscal year), `2011` (Census vintage), `march-2024` (CEA monthly snapshot vintage).
- `<file>` — descriptor, snake_case `.json`. Example: `hbk_table_142_peak_demand.json`, `tn_distribution_acsarr.json`.

Worked examples:

```
datasets/energy/_meadow/rbi/2024-25/hbk_table_142_peak_demand.json
datasets/energy/_meadow/cea/2026-03/state_electricity_generation_mu.json
datasets/energy/_meadow/iced/2024-25/installed_capacity_coal_mw.json
datasets/demography/_meadow/nfhs/round-5/state_summary_indicators.json
datasets/fiscal/_meadow/rbi/2024-25/state_budget_outstanding_debt_pct_gsdp.json
```

## What goes in meadow vs canonical

| Question | Meadow | Canonical |
| --- | --- | --- |
| Row count | ~thousand-row per file typical | Family-wide (1k–500k rows) |
| Row shape | publisher-native (preserves fuel sub-categories, table layout) | long-format observation row per [ADR-0030 D5/D17](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm) |
| Time axis | publisher vintage (`2024-25`, `2011`, `march-2024`) | `year:int` + `period_label:text` (CLAUDE.md §0a OWID rule) |
| Identity | per-source path + filename | `(entity_id, year, period_label, indicator_id)` |
| Methodology splices | not yet applied (RBI Table 140 ↔ 142 rows present separately) | applied via canonical adapter + recorded in `methodology_breaks.parquet` |
| Reader | backend canonical adapter only | DuckDB-WASM in browser |
| FK closure | `source_id` only | `source_id` + `entity_id` + `indicator_id` (writer-enforced per [ADR-0030 D22](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm)) |

## "No frontend fetch" rule

The frontend's data-loader (`frontend/src/lib/canonical/indicator-from-canonical.ts` `loadIndicator()`) routes every indicator request through the Phase B canonical allowlist. Allowlisted IDs resolve via DuckDB-WASM against `datasets/<family>/<family>_<role>.parquet`. Non-allowlisted IDs fall through to legacy `fetch('/data/indicators/in/...')` paths — but as each family's 7c-N PR ships, those legacy paths cease to exist (the `git mv` to `_meadow/` deletes them), and the indicator joins the canonical allowlist in the same commit.

The result: any frontend code that bypasses the allowlist by hand-crafting a `fetch('/data/indicators/in/<topic>/<id>.json')` URL will 404 after the family's 7c-N PR. This is the forcing function for Phase B allowlist completion — `git mv` simultaneously closes Phase C (adapter input) + Phase D (legacy path retire) + Phase B (allowlist coverage).

## Migration sequence (energy family)

Per [ADR-0041](../architecture/data/canonical-store.md#adr-0041-meadow-tier):

| PR | Adapter | Shards | Notes |
| :-: | --- | :-: | --- |
| **7c-0** | — | 0 | This vocabulary + ADR-0041 + CLAUDE.md §4/§10 + canonical-store.md §2 amend. |
| 7c-1 | `generation.py` | 2 | Introduce `load_meadow()` helper. |
| 7c-2 | `distribution.py` | 6 | Parallel-safe with 7c-3. |
| 7c-3 | `demand_supply.py` | 7 | PR #174 inline-literal block unchanged. |
| 7c-4 | `installed_capacity.py` | 8 | Retire `load_shard()`; rename Tier-B fence; delete `datasets/indicators/in/energy/`. |

Future families (Phase 2 P.2+ — NFHS-5, PLFS, UDISE+, AISHE, NCRB, HCES, IMD, e-GramSwaraj-PFMS, TRAI, CAG) adopt the meadow-tier authoring path from day one. No per-family Phase-C debate.

## Completion criterion

`datasets/indicators/in/` does not exist on `main`. Single observable:

```bash
git ls-tree origin/main -- datasets/indicators/in/
# empty output = done
```

## See also

- [ADR-0041 — Meadow tier: parsed publisher rows as canonical input](../architecture/data/canonical-store.md#adr-0041-meadow-tier) — rationale + 5 rejected alternatives + non-negotiables
- [ADR-0030 — Canonical long-format store on Hive-partitioned Parquet read by DuckDB-WASM](../architecture/data/canonical-store.md#adr-0030-canonical-store-duckdb-wasm) — canonical-tier contract
- [ADR-0032 — Sources citation ledger](data-provenance.md#adr-0032-sources-citation-ledger) — `source_id` FK closure
- [`docs/architecture/data/canonical-store.md` §2b.5](../architecture/data/canonical-store.md) — per-family directory invariant (includes `_meadow/`)
- [`docs/concepts/data-provenance.md`](data-provenance.md) — provenance vocabulary that meadow rows participate in
- [`docs/concepts/owid-alignment.md`](owid-alignment.md) — broader OWID precedent (the five-tier pipeline is one piece)
- OWID ETL repository — `https://github.com/owid/etl` (canonical reference implementation)
