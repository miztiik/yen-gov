# Meadow tier (retired)

**Last Updated**: 2026-06-11

**Status**: RETIRED. The meadow tier (per-family `datasets/<family>/_meadow/<source>/<vintage>/<file>.json`) served as the backend-internal parsed-input layer between upstream snapshots and the canonical store. It was defined by [ADR-0041](../architecture/data/canonical-store.md#adr-0041-meadow-tier). All per-family meadow directories were removed as of the B4 pivot (2026-06-07); new ingests write directly to long-format CSV under `datasets/data/`.

## What it was

The meadow tier was the third of five data layers (upstream -> snapshots -> meadow -> canonical -> grapher). Meadow files were schema-valid, FK-bearing JSON rows -- typed, deterministic, pre-canonical. They lived at `datasets/<family>/_meadow/<source>/<vintage>/<file>.json` and were consumed ONLY by the backend canonical adapter.

Five guarantees applied: (1) schema-valid, (2) deterministic, (3) FK-bearing (`source_id` -> `datasets/data/entities/source.csv`), (4) vintage-anchored (path `<vintage>` MUST equal citation row `vintage`), (5) backend-internal (no frontend fetch).

The legacy JSON predecessor to the meadow tier played the meadow role but lacked the underscore convention that segregated backend-internal files. [ADR-0041](../architecture/data/canonical-store.md#adr-0041-meadow-tier) formalised the `_meadow/` naming.

## Current state

`datasets/indicators/` is empty on `main`. Per-family `_meadow/` directories under `datasets/energy/`, `datasets/livestock/`, `datasets/fiscal/` etc. were deleted in the B4-pt2 and B4-pt3 pivot (2026-06-06/07). New ingests write observations directly to `datasets/data/datapoints/geo/<canonical_id>.csv` (long-format, 4-column shape per `datasets/data/_schema/columns.json`).

## Completion check

```bash
git ls-tree origin/main -- datasets/energy/_meadow/ datasets/fiscal/_meadow/ datasets/demography/_meadow/
# empty output = done
```

## See also

- [ADR-0041 -- Meadow tier](../architecture/data/canonical-store.md#adr-0041-meadow-tier) -- rationale and non-negotiables (historical receipt)
- [docs/architecture/data/canonical-store.md](../architecture/data/canonical-store.md) -- current canonical-store contract (long-format CSV)
- [data-provenance.md](data-provenance.md) -- `source_id` FK contract
