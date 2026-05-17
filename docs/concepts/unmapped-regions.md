# Unmapped regions

**Last Updated**: 2026-05-17

An **unmapped region** in yen-gov is an administrative unit whose polygon, at the India choropleth's default zoom, is too small to communicate a legend bucket — a sub-pixel fill cannot be read as a colour, so the choropleth fails its job for that region. Unmapped regions are surfaced as **value chips** on the legend strip instead of (or alongside) their polygons on the map.

This is a presentation concept, not a data concept. The region's polygon is still on the map (sub-pixel but unchanged); only the *reading mechanism* is supplemented.

## v0 set

The hand-curated v0 set lives at `datasets/reference/in/unmapped_regions.json`:

- `U04` — Lakshadweep (36 islands, ~300 km W of Kerala, ~32 km² total).
- `U01` — Andaman & Nicobar (Bay of Bengal island chain, ~8,250 km² but elongated and offshore).

Both are sub-pixel on the India choropleth at default zoom for **any** indicator. The list is editorial — extend it (via the same schema) when a new indicator surfaces another problem UT.

## What a chip carries

Per Hans's governance read of "what does a policy reader need to read this UT honestly":

1. **UT name** — the citizen-facing display name from the registry.
2. **Indicator value** — formatted via the indicator's own formatter, including unit. Or `—` when no datum.
3. **Bucket colour swatch** — the same `fillForValue()` the polygon would have used. The chip is the legend-bucket reading surface the polygon failed to provide.
4. **Population anchor** — absolute people count (e.g. "64k people"), loaded from `state_population_lakhs.json`. Rosling's size instinct: a per-capita rank for Lakshadweep means something different than the same rank for UP, and the chip says so.
5. **No-data honesty** — when the indicator has no row for the UT at the selected time, the swatch is a dashed hollow square and the value reads `—`. The chip still renders; silence is data.

## Why chips, not a bigger polygon inset

Tried and rejected (see [ADR-0029](../architecture/decisions/0029-unmapped-region-chips.md)):

- A bigger polygon inset surfaces *geography* but not *legend bucket* — the fill stays sub-pixel at any scale where the outline is still recognisable.
- A leader line connecting an inset to true location implies geographic continuity that doesn't exist (Lakshadweep is 300 km offshore).
- A chip lives outside the map, makes no geographic claim, and uses the same colour scale the polygon would have — so the citizen reads the same bucket they'd read off any state polygon.

## Implementation pointers

- Component: `frontend/src/lib/UnmappedRegionChips.svelte` (presentation-only).
- Pure helpers: `frontend/src/lib/unmapped-region-chips.ts` (chip model, population loader, fetch).
- Schema: `datasets/schemas/unmapped-regions.schema.json` (x-version 1.0).
- Config: `datasets/reference/in/unmapped_regions.json`.
- Feature flag: `VITE_UNMAPPED_REGION_CHIPS` (default `on`; set to `off` to restore the legacy polygon inset).

## See also

- [ADR-0029 — Unmapped region chips](../architecture/decisions/0029-unmapped-region-chips.md) — the decision + alternatives + flag rationale.
- [docs/architecture/frontend/map.md](../architecture/frontend/map.md) — choropleth layer composition and the legacy Lakshadweep inset.
- CLAUDE.md §11 (schema versioning), §12 (provenance) — the contracts the new artifact honours.
