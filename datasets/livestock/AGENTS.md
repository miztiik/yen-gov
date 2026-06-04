# AGENTS.md - datasets/livestock

**Last Updated**: 2026-05-26 (Path A PR 3 - Pashu Aadhaar end-to-end)

Module map for the livestock family. Canonical design and rationale live in [TODO/20260525-livestock-ndlm-ingest-plan.md](../../TODO/20260525-livestock-ndlm-ingest-plan.md) (Path A 9-PR sprint). Family-level ADRs: [ADR-0041 meadow tier](../../docs/architecture/adr/ADR-0041-meadow-tier-path-grammar.md), [ADR-0042 sources v3.0](../../docs/architecture/adr/ADR-0042-sources-v3-vintage-anchor.md).

ASCII only: use plain keyboard characters; write "-", "->", ">=", "section", and "INR" instead of fancy symbols.

> **MIGRATING (2026-06-04).** Per the [CLAUDE.md](../../CLAUDE.md) doctrine-in-migration banner + [the platform-reset plan](../../TODO/20260603-data-and-charting-platform-reset-plan.md), this family's canonical fact-table is moving from Parquet to long-format CSV under `datasets/data/datapoints/`, and provenance FK now targets `datasets/data/entities/source.csv`. Parquet/meadow references below are MIGRATING; the meadow tier retires as the local-CSV reingest lands (plan chunk B4). Do NOT add a new Parquet writer or a network fetcher.

## What's here

The livestock family captures National Digital Livestock Mission (NDLM, Bharat Pashudhan) telemetry at district granularity. NDLM publishes 5 distinct programmes; this PR ships the first (Pashu Aadhaar). The remaining 4 (owner registration, NADCP vaccination, breeding ABIP/RGM, NAIP-IV) ship in PRs 4-9.

### Subdirectories

```
datasets/livestock/
  _meadow/ndlm/2024-25/                   # ADR-0041 meadow tier - per-(programme, snapshot vintage) typed JSON
    district-pashu-aadhaar-count-<species>.json
  livestock_pashu_aadhaar.parquet         # canonical fact-table (PR 3+)
  livestock_pashu_aadhaar.parquet.meta.json
  AGENTS.md                               # this file
```

Citizen reads from frontend MUST go through the canonical store via DuckDB-WASM (MIGRATING from Parquet to long-format CSV under `datasets/data/`); `_meadow/**` is backend-internal (Phase B allowlist enforces this). The `2024-25` vintage segment in the meadow path matches the source citation seeded by PR #276 (per ADR-0041 nn4 + ADR-0042); CY 2024 and FY 2024-25 observation rows are interleaved within each per-species file with the period_label distinction carried on each row's `time` field.

## Invariants

- **District granularity is non-negotiable.** User mandate 2026-05-25: "do not lose the district level data. That is very, very important." All Pashu Aadhaar facet-children FK to a district entity_id (format `IN-S<sc>-D<dc>`); state-level aggregates are never persisted - the frontend sums children on read.
- **Species facet axis is preserved.** 10 species (cattle / buffalo / yak / mithun / sheep / goat / pig / horse / donkey / mule) each get their own facet-child indicator (`district-pashu-aadhaar-count-<species>`) with `dimension_values: {species: "<slug>"}`. A future vintage that adds an 11th species MUST extend the SPECIES tuple in [backend/yen_gov/canonical/adapters/livestock/_shared.py](../../backend/yen_gov/canonical/adapters/livestock/_shared.py) and the indicator catalogue in lockstep.
- **Gender axis retained in raw, deferred from lift.** NDLM responses carry `maleCount` / `femaleCount` per district per species. The lift currently sums these into a single `total` per (district, species). The raw responses live in `.runtime/raw/ndlm/<vintage>/` (gitignored - regenerable via `python tools/ndlm_download.py`); a follow-up PR may add `-male` / `-female` grandchildren without re-downloading raw data.
- **Compute-on-read parent (Hans D33.8).** The parent indicator `district-pashu-aadhaar-count` has `parent_indicator_id: null` and `source_id: null` and emits ZERO observation rows. The frontend sums the 10 species children at read time. A lift regression that emits a parent row will be caught by [backend/tests/test_livestock_pashu_aadhaar_lift.py::test_parent_indicator_has_no_observation_rows](../../backend/tests/test_livestock_pashu_aadhaar_lift.py).
- **Hans honest-renderer caveat.** ALL Pashu Aadhaar indicators carry `comparability: "directional_only"` and `renderer_rules: ["no_rank_table"]`. The count is the number of TAGS issued, NOT an estimate of the actual livestock population. Rollout coverage varies by state; ranking states by tag count is meaningless and the renderer suppresses rank-tables for this reason. The frontend labels choropleth views "illustrative, not a ranking".
- **Source provenance.** All Pashu Aadhaar rows FK to `src-7e5d4aac4995` (ndlm_pashu_aadhaar), seeded by PR #276 (`tools/livestock_sources_seed.py`). The writer's FK gate verifies closure against `datasets/data/entities/source.csv` (MIGRATING from `datasets/taxonomy/sources.parquet`) before bytes touch disk.
- **Two-vintage convention.** NDLM publishes a CY snapshot (`"2024"`) and an FY snapshot (`"2024-25"`); both are pulled by `tools/ndlm_download.py`. They share a single source citation row (PR #276 design: vintage="2024-25" as the operator's snapshot window per ADR-0042), so both vintages' rows live in the SAME meadow file (one per species). The per-row `time` field carries the CY/FY distinction. `parse_ndlm_period` in `_shared.py` is the single decoder; the resulting `period_label` is `"2024"` or `"2024-25"` in the canonical parquet.

## District FK closure caveat

99.7% (1527 / 1532) of NDLM district codes resolved to entities in `datasets/taxonomy/entities.json`. The 5 unmapped (raw_vintage, district) pairs represent < 0.1% of observations:

| raw_vintage | NDLM lgd_code | NDLM name      | State         | Why unmapped                                                  |
| ----------- | ------------- | -------------- | ------------- | ------------------------------------------------------------- |
| 2024        | 601           | YANAM          | Puducherry    | Pondicherry exclave; LGD has it under code 8 not yet in roster |
| 2024        | 671           | SHAHDARA       | Delhi         | NCT Delhi sub-district / not in district roster              |
| 2024        | 991248162     | Mahamaya Nagar | Uttar Pradesh | Bogus 9-digit LGD code; upstream data quality                |
| 2024-25     | 671           | SHAHDARA       | Delhi         | Same NCT-Delhi gap (FY snapshot)                              |
| 2024-25     | 991248162     | Mahamaya Nagar | Uttar Pradesh | Same bogus-code upstream issue                                |

These observations are skipped at meadow-generation time (see `tools/livestock_meadow_pashu_aadhaar.py` "unresolved district LGD codes" summary). Tracking ticket: a future district-roster expansion PR will fold in YANAM + SHAHDARA; Mahamaya Nagar is an upstream data-quality issue and may stay skipped.

## Module map (lift-side)

| File                                                                          | Purpose                                                              |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| `tools/ndlm_download.py`                                                      | Hits NDLM Bharat Pashudhan APIs; writes raw JSON to `.runtime/raw/ndlm/`. Gitignored output - run once per refresh. |
| `tools/livestock_meadow_pashu_aadhaar.py`                                     | Reads raw -> emits 20 typed meadow JSON shards under `_meadow/ndlm/<vintage>/`. ADR-0041 grammar. |
| `tools/livestock_sources_seed.py`                                             | Seeds the 5 NDLM citation rows; ran in PR #276.                      |
| `backend/yen_gov/canonical/adapters/livestock/_shared.py`                     | SOURCE_IDS dict + SPECIES tuple + `parse_ndlm_period` + `load_meadow`. |
| `backend/yen_gov/canonical/adapters/livestock/pashu_aadhaar.py`               | `build_envelope(repo_root) -> BatchEnvelope` for the pashu_aadhaar fact-table. |
| `backend/yen_gov/canonical/adapters/livestock/__init__.py`                    | `build_envelopes(repo_root) -> list[BatchEnvelope]` orchestrator.   |
| `backend/yen_gov/cli.py::lift_livestock`                                      | Operator entry point: `python -m yen_gov lift-livestock --root .`.  |
| `backend/tests/test_livestock_pashu_aadhaar_lift.py`                          | Tier-A contract tests (7 assertions; uses real on-disk shards).      |

## Refresh workflow

When NDLM publishes a new vintage:

```powershell
# 1. Download raw responses (one-shot; output gitignored)
python tools/ndlm_download.py --vintages 2025 2025-26

# 2. Regenerate meadow shards (committed). Note: --raw-vintages selects
# which raw snapshot windows to lift; the OUTPUT directory is always
# _meadow/ndlm/<seeded-source-vintage>/ (currently "2024-25" until a
# follow-up seed PR adds a new source-vintage row).
python tools/livestock_meadow_pashu_aadhaar.py --raw-vintages 2025,2025-26

# 3. Refresh taxonomy sidecars (manifest + entities/indicators/sources/topics parquets)
python -m yen_gov emit-taxonomy --root .

# 4. Rewrite the canonical fact-table (idempotent replace)
python -m yen_gov lift-livestock --root .

# 5. Validate
python -m yen_gov validate --root .
pytest -q backend/tests/test_livestock_pashu_aadhaar_lift.py
```

Every step is deterministic and reproducible from the gitignored `.runtime/raw/ndlm/`.
