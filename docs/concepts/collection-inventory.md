# Collection inventory

**Last Updated**: 2026-05-17
**Status**: canonical (since `indicator.schema.json` v2.0)

The `collection_inventory` block on every folded indicator answers
"where do we stand on collecting this series?". It is the only piece
of state the planner reads, and it is mostly **derived** from the
indicator's own `series_spec`, `rows[]`, and `sources[]` — not stored
in a parallel mutable file. See
[folded-indicator](folded-indicator.md) for the file shape.

## Field ownership

| Field                 | Written by                                | Read by                                                  |
| --------------------- | ----------------------------------------- | -------------------------------------------------------- |
| `status`              | Derived on emit                           | Citizen UI, `/data-completeness` index, admin Indicators |
| `frozen`              | **Operator** (admin Indicators panel)     | Planner (skip whole indicator), citizen UI               |
| `last_collected_at`   | Derived: `max(sources[].fetched_at)`      | Citizen UI; planner ignores                              |
| `refetch_requested`   | **Operator** triage flag                  | Admin Indicators; planner clears after re-collect        |
| `observed_periods`    | Derived from `rows[].time` + `period_label` | Citizen UI, derivation of `pending_periods`              |
| `pending_periods`     | Derived: `expected − observed − unavailable` | Planner (passes back to adapter verbatim), citizen UI    |
| `unavailable_periods` | **Adapter or operator** structured exclusion | Derivation (subtract from expected), citizen UI         |

Derivation is in [`backend/yen_gov/inventory/derive.py`](../../backend/yen_gov/inventory/derive.py).
Storage at the write seam is in
[`backend/yen_gov/core/io.py`](../../backend/yen_gov/core/io.py) —
`write_artifact` re-derives the inventory on every emit while
splicing the operator-set fields (`frozen`, `refetch_requested`,
`unavailable_periods`) from the prior version on disk so they survive
across runs.

## Period tokens — `{key, label, frequency}`

Every period in `expected_periods`, `observed_periods`,
`pending_periods`, and `unavailable_periods[].period` carries the same
three-field shape:

- `key` — stable equality token. Normally equals `rows[].time`. Not
  citizen-facing. Used for set membership only.
- `label` — the **publisher's exact period string**: `"FY 2024-25"`,
  `"as on 31.03.2025"`, `"Census 2011"`, `"Q3 2024-25"`. MUST be
  citizen-readable without unwrapping. The adapter is the single
  authority on these labels.
- `frequency` — one of nine enum values:
  `annual_fy`, `annual_cy`, `quarterly_fy`, `quarterly_cy`, `monthly`,
  `weekly`, `daily`, `decennial`, `ad_hoc`.

The planner round-trips tokens **opaquely**: it stores them, displays
them, and hands them back to the adapter unchanged. There is no
normaliser, no LLM, no canonical-form transformer anywhere in this
path. The Indian publisher vocabulary is irreducibly diverse; any
attempt to flatten it loses information and creates a new round-tripping
class of bugs.

## `expected_periods` vs `expected_periods_inference`

`series_spec.expected_periods` is **materialized**: an array of the
exact periods the indicator promises to cover. The planner enumerates
this against `expected_geographies` to compute the
(state × period) cell universe.

`series_spec.expected_periods_inference` explains *how* that array was
arrived at:

- `authored_from_publisher_catalogue` — the publisher publishes a list
  of releases; the adapter mirrored it.
- `authored_from_source_schedule` — the publisher commits to a cadence
  (monthly CPI, quarterly GDP); the adapter enumerated it.
- `seeded_from_observed_rows` — the indicator was bootstrapped from
  the rows already collected; the array MAY be incomplete.
- `not_inferable` — ad-hoc release pattern; the array is best-effort.

Public surfaces should label this as "Planned coverage" or "Draft
coverage", not "inferred".

## Adapter writes citizen-readable labels

Documentation rule, not validator rule: the adapter — the only code
that knows what the publisher actually printed — MUST write labels in
the publisher's own form. If the adapter writes `"2024-Q3"` when the
publisher printed `"Q3 2024-25"`, then citizens see the adapter's
abbreviation and the round-trip back to upstream breaks. The schema
cannot enforce this; review must.

## `rm` is the only force-recollect

There is no force-refetch flag. To re-collect an indicator from
scratch, the operator deletes the relevant `.runtime/raw/` files (per
[ADR-0003](../architecture/decisions/0003-no-fetch-cache.md)) and
re-runs the collector. See [How-to: force re-collection](../how-to/force-recollect.md).

`refetch_requested` is **triage status**, not a second force mechanism.
An operator marks an indicator `refetch_requested: true` to flag "this
needs a re-pull on the next operator pass"; the planner clears the
flag to `false` after a successful re-collect, so the absence of a
flag is also signal.

## Companion docs

- [folded-indicator](folded-indicator.md)
- [data-provenance](data-provenance.md)
- [How-to: force re-collection](../how-to/force-recollect.md)
- ADR-0003 [no fetch cache](../architecture/decisions/0003-no-fetch-cache.md)
