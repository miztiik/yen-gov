# `frontend/src/lib/sources/`

**Last Updated**: 2026-06-11

The publisher-pill view-model + render component for the citizen-facing
sources footer on every chart card.

Doctrine: [docs/concepts/data-provenance.md](../../../../docs/concepts/data-provenance.md)
(see inline `ADR-NNNN citation-ledger-5col`, 2026-06-11). Plan: [docs/archive/plans/20260611-sources-simplification-plan.md](../../../../docs/archive/plans/20260611-sources-simplification-plan.md).

## The contract

The on-disk citation ledger at `datasets/data/entities/source.csv` has
exactly 5 columns:

```
source_id, producer, title, vintage, url
```

The frontend reads this table via DuckDB-WASM (`frontend/src/lib/duckdb.ts`).
The `SourceRow` type in [types.ts](./types.ts) mirrors the 5-col shape
exactly. The 6 v2.0 fields (`license`, `confidence_tier`,
`is_issuing_authority`, `verification_method`, `citation_full`, `notes`)
are retired per `citation-ledger-5col`; the matching v2 component
the prior v2 render surface + 11-col helper package were deleted
in PR-1 of the sources simplification plan (2026-06-11).

## The render shape

ONE pill per `(producer x series_family)`. Multiple citation-ledger rows
with the same `(producer, series_family)` collapse to one pill via
`dedupeToPills(rows)`. Pill text:

- `"RBI State Finances (2025-26)"` when producer + series_family + vintage
  all fit the soft 30-char budget
- `"RBI"` when the series_family overflows (Jony rule: prefer brevity over
  truth-precision at the card level; the info-icon expand carries full
  citation detail)
- `"Wikipedia"` when the producer's only series is its sole entry

Multiple pills render plain-text middot-separated:

```
Source: RBI State Finances (2025-26) . ECI Statistical Reports . MoSPI (i)
```

Where `(i)` is the existing `AboutThisData` info-icon (owned by that
component, NOT this one). When pills.length > 3, the tail collapses
behind a "+N more" inline-expand button.

Empty pills array renders NOTHING - no row, no whitespace, no
"Hand-authored - see commit history" copy.

## What this package owns

| File | Role |
|------|------|
| [types.ts](./types.ts) | `SourceRow` (5-col mirror of source.csv) + `PublisherPill` (view-model output: dedup grain). |
| [format.ts](./format.ts) | Pure helpers: `publisherDisplay(producer)`, `seriesFamily(title)`, `summarizeVintages(vintages)`, `dedupeToPills(rows)`. No DOM, no Svelte. |
| [format.test.ts](./format.test.ts) | Unit tests for the 4 helpers. ~20 cases. |
| [SourceList.svelte](./SourceList.svelte) | Render component. Consumes `PublisherPill[]`, emits one paragraph or nothing. |
| [index.ts](./index.ts) | Barrel export. |

## What this package does NOT own

- The info-icon ("About this data"). It lives in [AboutThisData.svelte](../AboutThisData.svelte).
- The DuckDB SQL projection of source.csv. It lives in [duckdb.ts](../duckdb.ts).
- The view-model JOINs that assemble `SourceRow[]` for each chart. They live in `view-models/`, `charts/composition-bar/adapter-*.ts`, and `canonical/indicator-from-canonical.ts`.
- The methodology / scope / caveats expansion content. It lives in `AboutThisData.svelte`.
- The `IndicatorDoc.svelte` route's hand-authored Markdown overflow. The pill row CAN appear on `IndicatorDoc` too; the route adds its own surrounding chrome.

## Adding a new publisher abbreviation

Add a row to the `PUBLISHER_DISPLAY` map in [format.ts](./format.ts) and a
matching test case in [format.test.ts](./format.test.ts). The abbreviation
MUST be a proper-noun the Indian citizen recognises (RBI, ECI, MoSPI).
Invented acronyms break recognition.

## Migration notes

PR-0 (2026-06-11) shipped this package dark - no caller imports yet.
PR-1 (2026-06-11) migrated the 6 live v2-render-surface callers + the 1
v1 caller to consume `SourceList` from this package; view-models
shifted from the 11-col v2 row type to `PublisherPill[]` (deduped).
After PR-1, the legacy render surfaces + the 11-col helper package are
all deleted.
