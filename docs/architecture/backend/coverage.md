# Coverage report (data inventory)

**Last Updated**: 2026-05-14

`backend/yen_gov/coverage.py` produces the single source of truth at
[`docs/reference/data-inventory.md`](../../reference/data-inventory.md). It is
invoked by `python -m yen_gov coverage` and reads only from `datasets/` (no
network). Two surfaces are projected in one pass:

1. **Indicators** — every `*.json` under `datasets/indicators/in/` is parsed,
   its `coverage.temporal` span is read, and a 7-cell **Temporal Richness**
   meter is computed.
2. **Elections** — the existing on-disk slice catalogue is rendered both
   event-first (cohort tables, unchanged) and state-first (one row per state,
   the same 7-cell meter, but each cell is one election cycle).

The hand-authored
[`docs/reference/data-coverage-report.md`](../../reference/data-coverage-report.md)
no longer carries the per-indicator or per-election tables; it points at
`data-inventory.md` for the data and keeps only the narratives ("read this
as…", gaps, in-flight work).

## Why a 7×3 fiscal-year meter

The bucket layout is hardcoded in `BUCKET_EDGES`:

| Cell | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|------|---|---|---|---|---|---|---|
| FY span | FY06–FY08 | FY09–FY11 | FY12–FY14 | FY15–FY17 | FY18–FY20 | FY21–FY23 | FY24–FY26 |

Three reasons for the 7×3 shape:

- **7 cells = one screen-readable line.** A fixed-width meter (`● ● ● ○ ○ ○ ○ 3/7`)
  is comparable across rows in a Markdown table without horizontal scroll.
  More than 7 cells starts to wrap on hub-page widths.
- **3 fiscal years per cell ≈ one Indian Lok Sabha cycle / Finance Commission
  award gap.** Coarse enough that a one-year fetch hiccup doesn't move the
  needle; fine enough to expose multi-year publication freezes.
- **FY06 as the floor** — RBI national series start at FY07; one bucket of
  slack on the oldest side keeps a "complete since RBI's first year" series
  from rendering as 7/7 prematurely. The right edge stops at FY26 because
  FY27 is the next pending Finance Commission window — pushing right requires
  re-justifying the bucket count, not just shifting it.

If a future change demands a different window (e.g. one bucket per Lok Sabha,
or buckets keyed off the Finance Commission award periods), edit
`BUCKET_EDGES`/`BUCKET_LABELS` together and bump this rationale section.

## How spans are projected

`_parse_temporal(span)` accepts three written forms found in indicator JSONs:

- `"YYYY-MM..YYYY-MM"` — closed range (most fiscal/economy series).
- `"YYYY-MM"` — single point (CEA monthly snapshots).
- `"YYYY"` or `"YYYY..YYYY"` — annual / annual range (legacy).

A bare `"YYYY"` is treated as April-of-that-year (FY start), matching the rest
of the codebase's fiscal-year convention. Single points produce
`(start == end)` and are rendered with a trailing `(snapshot)` tag. The meter
fill rule is inclusive overlap: cell *k* is `●` iff
`[start, end] ∩ [bucket_lo, bucket_hi]` is non-empty.

## Why the election meter looks the same but counts differently

For state-first elections (`## 2a` in the inventory), each cell is **one
ingested election cycle**, not a year window. `_compute_election_meter(n)`
returns `n` rightmost cells filled (capped at 7). This intentionally does NOT
align election cells to year buckets:

- Different states poll at different cadences (5-year cycles staggered across
  the country); year-aligning them would surface noise about *when* a state
  votes, not *how many cycles* we've ingested.
- The reader question we're answering at §2a is "for which states do we have
  enough back-history to draw a swing chart?" — that's a *count* question,
  not a *date-alignment* question.
- The event-first cohort tables (`## 2b`) preserve the date dimension; §2a
  and §2b answer different questions on the same data and both ship.

The §2a row also lists every on-disk `event_id` for that state (newest →
oldest) in a single "On-disk event_ids" column, instead of separate
"Most recent" / "Oldest" columns. Reason: when a state has 3 of N possible
cycles ingested, the operator needs to see *which* cycles are present to
chase the missing ones — endpoints alone don't reveal interior gaps. The
column is for human triage, not for downstream consumers (no parser depends
on it).

## What the report does NOT do

- **It does not validate schemas.** That's `python -m yen_gov validate`. A
  schema-invalid indicator file will still appear in the inventory if it has
  a parseable `coverage.temporal`; severe parse errors (bad JSON, missing
  `coverage`) cause the file to be skipped silently — by design, so a single
  malformed file doesn't break the whole report.
- **It does not touch on-disk layout.** Per [Gregor's pushback during the
  IA reset](../../reference/data-coverage-report.md), elections stay
  event-keyed on disk; state-first is a read-time projection only.
- **It does not infer missing indicators.** Coverage for "indicators we
  *should* have but don't" lives in the hand-authored §5b ("loaded artifacts
  that need wider coverage") of `data-coverage-report.md` — the gaps story
  needs human judgement, not file-walking.

## Tests

`backend/tests/test_coverage.py` covers:

- `test_parse_temporal_handles_range_and_snapshot` — the three written forms
  plus malformed input.
- `test_compute_meter_buckets` — boundary cases (all-7, single rightmost,
  middle three).
- `test_scan_indicators_emits_meter` — synthetic JSONs hit the right cells.
- `test_render_includes_indicators_and_state_first` — end-to-end render
  contract, including header rename and §2a / §2b ordering.
- The two original reconciliation tests stay green (they exercise §2b and
  the inconsistencies section).

## See also

- [`docs/reference/data-inventory.md`](../../reference/data-inventory.md) —
  the rendered output (auto-generated; do not hand-edit).
- [`docs/reference/data-coverage-report.md`](../../reference/data-coverage-report.md)
  — the narrative companion (gaps, in-flight work, refresh recipes).
- [`backend/yen_gov/coverage.py`](../../../backend/yen_gov/coverage.py) — the
  module itself.
