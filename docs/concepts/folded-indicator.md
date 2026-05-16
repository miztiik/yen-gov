# Folded indicator

**Last Updated**: 2026-05-17
**Status**: canonical (since `indicator.schema.json` v2.0, PR feature/folded-indicator-inventory)

## What it is

Every indicator yen-gov publishes lives in a **single JSON file** at
`datasets/indicators/in/<topic>/<id>.json`. That file carries the
existing rendering contract — `indicator` block, `rows[]` long-form
observations, `license`, `coverage`, `sources[]` — plus four folded
sections that used to be implicit, scattered, or sidecar:

- `series_spec` — the editorial declaration of what the series IS:
  description, expected geographies, expected periods, and how those
  expectations were arrived at (`expected_periods_inference`).
- `collection_inventory` — derived + operator-flagged view of where we
  stand on collection: `status`, `frozen`, `last_collected_at`,
  `refetch_requested`, `observed_periods`, `pending_periods`,
  `unavailable_periods`.
- `methodology` — `definition`, `publisher`,
  `publisher_methodology_url`, `documentation_status`,
  `methodology_breaks`, `known_caveats`, `notes`,
  `related_indicators`, `editor_note_md`, `policy_context`,
  `chart_defaults`.
- `divergence` — reserved for Max's divergence-band methodology
  (deferred). Always `null` in v2.0.

There are **no sidecars**. The previous `<id>.notes.json` files were
folded losslessly into typed inline `methodology` fields and deleted;
`datasets/schemas/indicator-notes.schema.json` is gone too.

Schema: [`datasets/schemas/indicator.schema.json`](../../datasets/schemas/indicator.schema.json) @ `x-version 2.0`.

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
> `methodology + series_spec + collection_inventory + divergence`
> inline.
>
> **Series cell.** A single observation, identified by
> `(entity_id, period_label)`. For "state GSDP, annual FY, 2011-12 to
> 2024-25" with `all_states_and_uts` geographies, the universe is
> 36 × 14 = 504 cells.
>
> **`series_spec`.** Declares what the series IS — description,
> expected geographies, expected periods. The editorial source of
> truth for what we promise to track.
>
> **`expected_geographies`.** Array of geo codes (ECI state codes,
> district LGD, or `IN`). Inline or `$ref` into
> [`universes.json`](../../datasets/reference/in/universes.json).
>
> **`expected_periods`.** Materialized array of
> `{key, label, frequency}` period tokens. `key` is the equality
> token, normally matching `rows[].time`; `label` is the publisher's
> exact vocabulary ("FY 2024-25", "as on 31.03.2025",
> "Census 2011"); `frequency` is a fixed nine-value enum.
>
> **`expected_periods_inference`.** Explains how `expected_periods`
> was obtained: publisher catalogue, source schedule, observed rows,
> or not inferable. It may include an adapter-authored structured
> series (integer range/list, string list, month/date list) when the
> source vocabulary is clearly iterable. This is schema language;
> public pages say "Planned coverage" or "Draft coverage", not
> "inferred".
>
> **`collection_inventory`.** Derived + operator-flagged view of where
> we stand on this indicator. Fields: `status`, `frozen`,
> `last_collected_at`, `refetch_requested`, `observed_periods`,
> `pending_periods`, `unavailable_periods`.
>
> **`status`.** `complete` (zero pending, zero unexplained gaps) |
> `partial` (some pending) | `empty` (zero collected). Derived on
> emit.
>
> **`frozen`.** Operator flag. When true, planner skips this indicator
> entirely on next collect.
>
> **`last_collected_at`.** Derived: `max(sources[].fetched_at)`.
> Informational only. Planner does not read.
>
> **`refetch_requested`.** Operator triage flag. In this PR it is
> read-only status, not a second force-recollect mechanism. Public
> copy should say "Re-collect requested" only in admin/operator
> contexts.
>
> **`observed_periods`.** Derived array of period tokens actually
> present in `rows[]`. Never hand-edited.
>
> **`pending_periods`.** Derived array of period tokens for periods
> the indicator expects but has not yet collected and has not marked
> unavailable. Planner stores, displays, and passes back verbatim —
> never parses or normalises.
>
> **`unavailable_periods`.** Structured exclusions with
> `{period, geographies?, reason}`. Example: `Census 2011` for
> Ladakh, reason "Ladakh did not separately exist in Census 2011
> tables." Citizen-visible; used by derivation to avoid marking
> impossible cells as pending.
>
> **`fetched_at`.** Wall-clock time at which yen-gov last successfully
> read bytes from the listed URL. Operational provenance. NOT a claim
> about when upstream content changed. Stable across re-runs
> (fetch-once-freeze).
>
> **Universe.** A named set of geo codes in
> [`universes.json`](../../datasets/reference/in/universes.json),
> `$ref`-able from `series_spec.expected_geographies`. Inline arrays
> also allowed; the universes table is convenience for the common
> cases.
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
> **Divergence.** Reserved (Max-led, deferred). Always `null` in v2.0.
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
- Diagnosis archive: `TODO/20260517-folded-indicator-and-collection-inventory-handover.md`.
