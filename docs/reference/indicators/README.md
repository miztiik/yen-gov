# Per-indicator markdown tree -- retired 2026-05-17

The auto-generated tree that previously lived here
(`docs/reference/indicators/<topic>/<id>.md`, ~111 files across 9 topics) was
retired 2026-05-17. Per-indicator depth now lives in two places only:

- **Operator overview** -- [`docs/reference/data-inventory.md` sec 1](../data-inventory.md#1-indicators-by-category)
  carries one row per artifact: id, unit, time grain, span, row/entity counts,
  Temporal Richness meter, source host.
- **Canonical data** -- long-format CSV files under
  [`datasets/data/datapoints/geo/`](../../../datasets/data/datapoints/geo/)
  (one file per indicator id). Metadata (title, unit, entity_kind, sources) is
  declared in [`frontend/src/lib/canonical/indicator-allowlist.ts`](../../../frontend/src/lib/canonical/indicator-allowlist.ts).
  Provenance rows live in
  [`datasets/data/entities/source.csv`](../../../datasets/data/entities/source.csv).

If a link landed you here from an external page or an old commit message,
see [`data-inventory.md`](../data-inventory.md) for the current indicator
listing, or `datasets/data/datapoints/geo/<canonical-id>.csv` for the raw
data.
