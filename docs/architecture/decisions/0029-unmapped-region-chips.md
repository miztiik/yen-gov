# ADR-0029: Replace Lakshadweep polygon inset with legend-strip value chips

**Last Updated**: 2026-05-17
**Status**: accepted
**Supersedes**: not formally — narrows the "Lakshadweep callout inset" decision in [docs/architecture/frontend/map.md §Lakshadweep callout inset](../frontend/map.md#lakshadweep-callout-inset-phase-3-c-of-tn-granular-geo-plan) (Phase 3 §c of TN-GRANULAR-GEO-PLAN). The earlier "no leader line" rationale is preserved; the polygon inset itself is removed.

## Context

The India choropleth in `frontend/src/lib/IndicatorChoropleth.svelte` previously rendered Lakshadweep as a separate 80×80 px SVG polygon inset at the bottom-left of the map. The inset acknowledged the islands' existence geographically but failed the **choropleth's actual job**: at 80×80 px scaled to a ~1 px polygon, the fill colour was sub-pixel, so a citizen could not read which legend bucket Lakshadweep falls into for any indicator (HDI, energy access, GDP per capita, etc.).

Two personas were consulted (Jony UI/UX, Hans Governance):

- **Jony**: the inset's job-to-be-done is *legend-bucket readability*, not *geographic acknowledgement*. The polygon inset solves the wrong job; delete it, surface the value through a chip in the legend area.
- **Hans**: a policy reader needs UT name + value + bucket-colour + a **population anchor** (Rosling's size instinct — Lakshadweep ~64k vs. A&N ~380k vs. Delhi ~20M is the comparability frame), and explicit "no data" honesty when the indicator is silent on the UT.

The user direction (verbatim, 2026-05-17): "we take the data that Hans says we should present and give it to Jony, and Jony finds a way to present it... add it behind the toggle so that tomorrow if you want to delete it or remove it. We can cleanly do that."

## Decision

Replace the polygon inset with a **horizontal value-chip strip** anchored to the legend area. Each chip carries:

1. UT display name (e.g. "Lakshadweep").
2. Indicator value, formatted with the indicator's unit (or `—` when no datum).
3. Colour swatch driven by the choropleth's own `fillForValue()` — so the chip swatch and a notional polygon fill would be identical.
4. Population anchor (e.g. "64k people"), loaded at runtime from `datasets/indicators/in/demography/state_population_lakhs.json`.
5. Null-data variant: dashed hollow swatch + em-dash value, chip still rendered (silence is data).

v0 scope: Lakshadweep (`U04`) + Andaman & Nicobar (`U01`). The list is hand-curated as an inline TypeScript literal (`UNMAPPED_REGIONS`) inside `frontend/src/lib/unmapped-region-chips.ts`. The original JSON artifact + schema (`datasets/reference/in/unmapped_regions.json` + `datasets/schemas/unmapped-regions.schema.json`) were inlined and deleted at T.0c-ii-B.1 (2026-05-21) — a 2-entry editorial constant did not earn its fetch+JSON+schema round-trip.

The chip strip is gated behind `VITE_UNMAPPED_REGION_CHIPS` (default `on`). The legacy polygon-inset code path is retained behind `{:else}` so flipping the env var to `off` restores prior behaviour byte-identically.

## Why a chip, not a bigger inset / leader line

- **Bigger inset.** Tried mentally — at any inset scale where the polygon outline is recognisable as Lakshadweep, the fill is still sub-pixel; you can't beat the aspect-ratio of a 32 km² archipelago at India zoom. The inset surfaces geography but cannot surface the legend bucket, which is what the choropleth is *for*.
- **Leader line + true location.** Explicitly rejected here AND in the earlier Phase 3 §c decision: a line implies geographic continuity that doesn't exist (Lakshadweep is 300 km offshore). The chip mechanism preserves the earlier "no false continuity" rationale because chips live OUTSIDE the map and make no geographic claim.
- **Status quo (inset).** Fails the job-to-be-done; users routinely lose the bucket reading.

## Why behind a flag, not a hard cutover

- The chip subsystem is new and depends on a runtime fetch of `state_population_lakhs.json` per page. If the loader regresses or the artifact's schema drifts, the flag lets the operator restore the prior surface without a revert PR.
- The legacy inset is non-trivial to reconstruct from git history (the `lakshadweep.ts` helpers + SVG projection live in three files); retaining the `{:else}` branch is a few lines and a free rollback path.
- Per user direction. The flag is the contract; we honour it.

## Why hand-curated, not auto-detect by polygon area

A "compute screen-pixel area of every polygon at current zoom and demote sub-pixel UTs into chips" mechanism is technically possible. Out of scope here because:

- The set of problem UTs is small (2 today, ≤4 in plausible futures: + Daman-and-Diu, + Ladakh's northern lobe).
- Auto-detection couples chip-set to viewport — chips appearing/vanishing on zoom is worse UX than a fixed strip.
- A config file with a schema is the lighter, more honest mechanism. When a third UT becomes a problem on a new indicator, a maintainer adds one entry.

## Rationale chain for the population formatter

Population is rendered through `formatPopulationShort(people)`:

- `<1_000 → "640"` (raw)
- `<1_000_000 → "64k"` (round to nearest k)
- `≥1_000_000 → "1.2M"` (one decimal, trim `.0`)

This matches the eye's read on a chip 110–140 px wide; tabular-nums keeps the column aligned across chips. The value is in absolute people; the input artifact stores `value` in lakhs (1 lakh = 100,000), converted at load time by `latestPopulationFromLakhs()`.

## Consequences

- New surface (chip strip) on every India-level choropleth route.
- The canonical list is an inline TS constant (`UNMAPPED_REGIONS` in `frontend/src/lib/unmapped-region-chips.ts`) after the T.0c-ii-B.1 inline-port; no schema, no fetch.
- One new runtime fetch per India choropleth page mount (small, the population indicator artifact only, browser-cached).
- The Phase 3 §c polygon-inset documentation in `docs/architecture/frontend/map.md` now ends with a pointer to this ADR.

## See also

- [docs/concepts/unmapped-regions.md](../../concepts/unmapped-regions.md) — concept definition + chip-vs-inset rationale.
- [docs/architecture/frontend/map.md §Lakshadweep callout inset](../frontend/map.md#lakshadweep-callout-inset-phase-3-c-of-tn-granular-geo-plan) — the predecessor decision.
- `frontend/src/lib/unmapped-region-chips.ts` + `frontend/src/lib/UnmappedRegionChips.svelte` — implementation + canonical `UNMAPPED_REGIONS` constant.
