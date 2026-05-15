# Per-indicator pages — generation

**Last Updated**: 2026-05-15

The tree under [`docs/reference/indicators/`](indicators/) is **auto-generated** by:

```
python -m yen_gov indicator-pages
```

(also re-run as a side-effect of `python -m yen_gov coverage`).

Source: every JSON artifact under [`datasets/indicators/in/**`](../../datasets/indicators/in/) becomes one page at `docs/reference/indicators/<topic>/<basename>.md`. An alphabetised topic-grouped index lands at [`docs/reference/indicators/index.md`](indicators/index.md).

**Do not hand-edit the emitted tree.** Every page carries an `AUTO-GENERATED` banner; changes there are silently overwritten on next regen. Edits belong in the source artifact (for definition / methodology / sources / license) or — once the sidecar lands in Phase 4 — in the matching `<id>.notes.json`.

Generator: [`backend/yen_gov/coverage_indicator_pages.py`](../../backend/yen_gov/coverage_indicator_pages.py). Tests: [`backend/tests/test_coverage_indicator_pages.py`](../../backend/tests/test_coverage_indicator_pages.py). Plan: [`TODO/PER-INDICATOR-DOCS-PLAN.md`](../../TODO/PER-INDICATOR-DOCS-PLAN.md).

## What renders today (Phase 1, schema v1.4 surface only)

H1 + auto-gen banner · Title / one-line / Last Updated / source artifact link · Definition · Signature table · Coverage (temporal span / period count / entity count / row count) · Methodology vintage (when present) · Series breaks (when present) · Notes (when present) · Sources (full URL + fetched_at + host) · License · Citation (journalist-pasteable) · Schema footer.

Sections silently omitted when their underlying field is absent — no empty headings.

## What lands later

- **Phase 2** — Inventory linkifier + coverage-report trim (links the `id` cell in [`data-inventory.md`](data-inventory.md) to each page).
- **Phase 3** — Schema v1.5 governance fields (`revision_tier_by_period[]`, `denominator`, `excludes[]`, `renderer_rules[]`, 4-level `comparability` ladder); renderer picks them up automatically on next regen.
- **Phase 4** — Optional `<id>.notes.json` sidecar for hand-curated `related[]` / `editor_note_md` / `policy_context[]`.
- **Phase 5** — Topic spine pages (`fiscal`, `prices`, `health`, `energy`) hand-written under `docs/reference/topics/`.
