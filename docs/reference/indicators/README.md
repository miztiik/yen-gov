# Per-indicator markdown tree — retired 2026-05-17

The auto-generated tree that previously lived here
(`docs/reference/indicators/<topic>/<id>.md`, ~111 files across 9 topics) was
retired in Phase #4a of
[`TODO/20260517-coverage-temporal-range-plan.md`](../../../TODO/20260517-coverage-temporal-range-plan.md).
Per-indicator depth now lives in two places only:

- **Operator overview** — [`docs/reference/data-inventory.md` § 1](../data-inventory.md#1-indicators-by-category)
  carries one row per artifact: id (linked to the JSON), unit, time grain,
  span, row/entity counts, Temporal Richness meter, source host.
- **Definition, methodology, breaks, sources, notes** — the artifact JSON
  itself, browsable on github.com at
  [`datasets/indicators/in/<topic>/<id>.json`](../../../datasets/indicators/in/).
  The JSON is the single source of truth (CLAUDE.md §5); the markdown tree
  was a derived surface that ended up consuming `coverage.temporal` as
  free-text — see the plan doc for the full rationale.

If a link landed you here from an external page or an old commit message,
substitute the `<topic>/<id>.md` portion of that URL with
`datasets/indicators/in/<topic>/<id>.json` to reach the JSON the markdown
was rendered from.
