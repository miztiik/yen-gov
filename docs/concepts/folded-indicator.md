# Folded indicator

**Last Updated**: 2026-05-16
**Status**: canonical (since `indicator.schema.json` v4.0, [ADR-0026](../architecture/decisions/0026-lift-collection-inventory-out-of-indicator-artifact.md))

## What it is

Every indicator yen-gov publishes lives in a **single JSON file** at
`datasets/indicators/in/<topic>/<id>.json`. That file carries the
existing rendering contract — `indicator` block, `rows[]` long-form
observations, `license`, `coverage`, `sources[]` — plus three folded
sections that used to be implicit, scattered, or sidecar:

- `series_spec` — `{description}` only since v4.0. A one-sentence
  editorial summary of what the series IS. The pre-v4 fields
  (`expected_geographies`, `expected_periods`,
  `expected_periods_inference`) were lifted out per [ADR-0026](../architecture/decisions/0026-lift-collection-inventory-out-of-indicator-artifact.md).
- `methodology` — `definition`, `publisher`,
  `publisher_methodology_url`, `documentation_status`,
  `methodology_breaks`, `known_caveats`, `notes`,
  `related_indicators`, `editor_note_md`, `policy_context`,
  `chart_defaults`.
- `divergence` — reserved for Max's divergence-band methodology
  (deferred). Always `null`.

There are **no sidecars**. The previous `<id>.notes.json` files were
folded losslessly into typed inline `methodology` fields and deleted;
`datasets/schemas/indicator-notes.schema.json` is gone too.

Schema: [`datasets/schemas/indicator.schema.json`](../../datasets/schemas/indicator.schema.json) @ `x-version 4.0`.

## What is NOT in the artifact (since v4.0)

Three surfaces that used to live inside the artifact now live
beside it. The split is documented in
[ADR-0026](../architecture/decisions/0026-lift-collection-inventory-out-of-indicator-artifact.md);
[collection-inventory](collection-inventory.md) covers the day-to-day
shape.

| Was in artifact (v3.0) | Lives now (v4.0)                                                                 |
| ---------------------- | -------------------------------------------------------------------------------- |
| `collection_inventory.status` / `observed_periods` / `last_collected_at` | Derived index [`datasets/reference/in/indicators-completeness.json`](../../datasets/reference/in/indicators-completeness.json). |
| `collection_inventory.frozen` / `refetch_requested` / `unavailable_periods` | Hand-edited overlay [`datasets/reference/in/indicators-operator-state.json`](../../datasets/reference/in/indicators-operator-state.json). |
| `series_spec.expected_geographies` / `expected_periods` / `expected_periods_inference` | Not in any file today. The framework no longer pretends to know a publisher-promised cell universe; if a publisher commitment exists, the adapter authors it directly into `methodology`. |

## Why folded

Three rejected alternatives clarified the choice:

1. **A `.data-card.json` sidecar per indicator.** Smushes lifecycles —
   methodology (slow, hand-authored), inventory (per-collect-run,
   derived), and source provenance (per-fetch) end up in one file
   anyway. The fix is fewer files, not more.
2. **A global mutable `_inventory.json`.** The underscore is a
   confession that it's second-class. Inventory truth belongs *with*
   the indicator (where it can be derived from its own `rows[]`), not
   in a parallel state file that drifts.
3. **A SHA-gate on the Fetcher + `.meta.json` per URL.** Bytes ≠ data.
   Re-publishing the same Excel file with the same numbers in a
   slightly different layout would defeat byte-equality; meaningful
   gates live higher up.

The folded model lets a single `git diff <indicator>.json` tell you
everything that changed about that indicator — what we promise to
collect, what we have, what's missing, what the publisher's known
caveats are, and what bytes we fetched.

## As-published fidelity, not correctness

yen-gov preserves publisher values and documents every transformation
we perform: parsing tables, mapping geographies, choosing revision
vintages, computing declared rollups. No adjustment, smoothing,
imputation, correction, or estimation. Errors in the original appear
here; we update when the publisher does. Empty cells stay empty. See
[data-quality](data-quality.md).

## Glossary

> **Folded indicator.** A single JSON file per indicator at
> `datasets/indicators/in/<topic>/<id>.json` holding the existing
> `indicator + rows[] + license + coverage + sources` contract plus
> `methodology + series_spec + divergence` inline. Per-indicator
> operator state and citizen completeness live in the two sibling
> files described above.
>
> **Series cell.** A single observation, identified by
> `(entity_id, period_label)`. For "state GSDP, annual FY, 2011-12 to
> 2024-25" with `all_states_and_uts` geographies, the universe is
> 36 × 14 = 504 cells.
>
> **`series_spec`.** Since v4.0 a one-key object — `{description}` —
> giving a citizen-readable summary of what the series IS. The
> publisher-promise fields (`expected_*`) were lifted out; see
> [ADR-0026](../architecture/decisions/0026-lift-collection-inventory-out-of-indicator-artifact.md)
> for rationale.
>
> **`fetched_at`.** Wall-clock time at which yen-gov last successfully
> read bytes from the listed URL. Operational provenance. NOT a claim
> about when upstream content changed. Stable across re-runs
> (fetch-once-freeze).
>
> **Methodology break.** A documented point where the publisher
> changed definition, base year, geographic boundary, classification,
> or sampling frame such that pre- and post-break values are not
> directly comparable. `methodology_breaks: []` means "no breaks
> documented yet," NOT "no breaks exist."
>
> **Known caveat.** A documented limitation below break threshold but
> relevant for interpretation. `known_caveats: []` means "no caveats
> documented yet," NOT "data is caveat-free."
>
> **Stub methodology.** An indicator where `methodology_breaks` AND
> `known_caveats` are both empty AND `definition` is the default
> placeholder. The [`/data-completeness`](/data-completeness) view
> flags stubs so the team can prioritise backfill.
>
> **Divergence.** Reserved (Max-led, deferred). Always `null`.
>
> **Adapter ownership of labels.** The adapter is the single authority
> on its source's period vocabulary. It writes labels in the
> publisher's own form and recognises them on the return trip. The
> planner never parses. No normaliser, no LLM, no canonical-form
> transformer anywhere in the path.

## Companion docs

- [collection-inventory](collection-inventory.md) — derivation rules,
  operator flags, `{key, label, frequency}` period tokens.
- [data-quality](data-quality.md) — re-publisher stance.
- [data-provenance](data-provenance.md) — `sources[]` rules.
- [How-to: force re-collection](../how-to/force-recollect.md) — `rm`
  is the only force mechanism.
- ADR-0003 [no fetch cache](../architecture/decisions/0003-no-fetch-cache.md)
  — clarifies relationship to the folded model.
- ADR-0026 [lift collection-inventory out of indicator artifact](../architecture/decisions/0026-lift-collection-inventory-out-of-indicator-artifact.md)
  — full rationale for the v3.0 → v4.0 split.
