# Data quality stance

**Last Updated**: 2026-05-17

yen-gov is a **re-publisher** of Indian governance and statistical
data. We are not a statistical agency. This page exists so that
everyone working in or on the repo — and every citizen who reads the
site — knows what we will and will not do to a number.

## What we do

- Preserve publisher values byte-faithfully where possible.
- Document every transformation we perform: parsing tables, mapping
  geographies, choosing revision vintages, computing declared rollups.
- Annotate every break, caveat, and definitional shift the publisher
  has disclosed (under [`methodology`](folded-indicator.md) on each
  indicator).
- Be loud about gaps. Missing cells are marked **Not collected yet**
  (source expected to publish; we haven't fetched it yet) or
  **Not published by source** (publisher does not separately report
  this geography or period). See [collection-inventory](collection-inventory.md).

## What we do not do

- **No adjustment, smoothing, imputation, correction, or estimation.**
  Errors in the original publication appear here. We update when the
  publisher updates.
- **No filling in of empty cells.** Estimation looks helpful and is
  dishonest. Empty stays empty.
- **No composite "best state" index.** Composites hide trade-offs.
  Citizens compare on one indicator at a time, with the right
  denominator.
- **No "we corrected this row" rows.** If the publisher revised, we
  re-collect and the methodology break is recorded; the original is
  preserved in `.runtime/raw/` until the operator deletes it.

## Trust, in one sentence

Trust the data exactly as far as you trust the publisher. yen-gov's
job is to make their data more accessible without changing what they
said.

## Where this shows up in code

- Indicator schema forbids deriving the published value at any step:
  see [`datasets/schemas/indicator.schema.json`](../../datasets/schemas/indicator.schema.json).
  `rows[].value` is what the publisher said, with conversion only when
  unit and base-year are explicit in the artifact.
- Composers union `sources[]` per-`url`, never per-`(url, fetched_at)`,
  so a re-fetch of the same upstream doesn't multiply the citation —
  the artifact still says "we got this from these N publishers".
- `methodology_breaks: []` means "no breaks documented yet", NOT "no
  breaks exist". The [`/data-completeness`](/data-completeness) view
  flags indicators with documentation_status `stub` so the team can
  prioritise backfill instead of pretending coverage is uniform.

## Companion docs

- [folded-indicator](folded-indicator.md)
- [collection-inventory](collection-inventory.md)
- [data-provenance](data-provenance.md)
- `frontend/src/routes/About.svelte` and `Disclaimer.svelte` mirror
  this page in citizen-facing voice.
