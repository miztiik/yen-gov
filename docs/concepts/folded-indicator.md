# Folded indicator (obsolete concept)

**Last Updated**: 2026-06-11

**Status**: OBSOLETE. This concept describes the pre-CSV-pivot per-shard JSON model (the legacy indicator artifact). That storage is retired on `main` (all families migrated to long-format CSV under `datasets/data/`). Do not use as guidance for new work.

## What it was

Every indicator lived in a **single JSON file** per indicator, carrying an `indicator` block, `rows[]` long-format observations, `license`, `coverage`, `sources[]`, plus folded `methodology`, `series_spec`, and `divergence` sections. Schema: `datasets/schemas/indicator.schema.json` @ `x-version 4.0`.

The folded shape solved three problems: it kept methodology + inventory + provenance co-located with the observations; it eliminated per-indicator sidecar files; it made `git diff <indicator>.json` a complete change summary.

## What replaced it

The canonical store now stores all observations as long-format CSV under `datasets/data/datapoints/` (4-column shape: `entity_id, year, period_label, value`). Indicator metadata lives in:

- `datasets/data/entities/source.csv` -- citation ledger (the `sources[]` array replacement).
- `datasets/grapher/indicator_render.json` -- render hints (the `chart_defaults` replacement).
- `datasets/taxonomy/concepts.json` -- concept identity (`indicator.id` replacement).
- `datasets/_ops/indicators-completeness.json` -- collection inventory (the `collection_inventory` replacement).

The legacy indicator tree is empty on `main`. Any such file found is an unmerged legacy artifact.

## See also

- [docs/architecture/data/canonical-store.md](../architecture/data/canonical-store.md) -- current canonical store contract.
- [data-provenance.md](data-provenance.md) -- `source_id` FK contract that replaced `sources[]`.
- [indicator-naming.md](indicator-naming.md) -- current `indicator_id` grammar.
- [docs/concepts/collection-inventory.md](collection-inventory.md) -- replaced collection inventory shape.
