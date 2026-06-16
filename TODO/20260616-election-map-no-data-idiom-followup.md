# Follow-up: align the election map's no-data idiom with the welfare dot-grid

**Created**: 2026-06-16
**Parent PR**: `fix/home-redesign-and-map-ux` (home redesign + map UX + elections URL base)
**Status**: NOT STARTED - deferred from the parent PR by user direction ("do only welfare,
document the rest as a follow-up").

## Context

The parent PR fixed the no-data idiom on the **welfare** choropleth primitive
[`frontend/src/lib/charts/GeoChoropleth.svelte`](../frontend/src/lib/charts/GeoChoropleth.svelte):
the old diagonal-stripe hatch (`<pattern id="geo-choropleth-hatch">`) read as
"broken / hazard", so it was replaced with a subtle gray **dot-grid**
(`<pattern id="geo-choropleth-nodata">`) plus a small **"No data"** legend chip.
This is the renderer behind every `IndicatorChoropleth` welfare map (the home
default-theme welfare maps, every `/t/<topic>` landing, the GHG / CPI / fiscal
maps in the screenshots).

The **election** map is a different renderer:
[`frontend/src/lib/charts/IndiaPartyMap.svelte`](../frontend/src/lib/charts/IndiaPartyMap.svelte)
(d3-geo SVG, the home "Winning party" default theme). It paints no-data states
(e.g. Jammu & Kashmir, Ladakh - no recent assembly/parliament winner on file)
with a FLAT light-gray fill `DEFAULT_FILL = "#e2e8f0"`. It does NOT use the ugly
stripe hatch, so it was never part of the reported bug - but it is also not
aligned with the new dot-grid + chip idiom, so the two home themes show
no-data differently.

## The gap

| Surface | Renderer | No-data today | Target (consistency) |
| --- | --- | --- | --- |
| Welfare maps | `GeoChoropleth` | dot-grid + "No data" chip (DONE) | - |
| Election map | `IndiaPartyMap` | flat `#e2e8f0`, no chip | dot-grid + "No data" chip |

## Proposed work (one small PR)

1. Add the same `<pattern id="india-party-map-nodata">` dot-grid to
   `IndiaPartyMap.svelte`'s `<defs>` (copy the 7x7 `#f8fafc` + `#cbd5e1` r=1
   pattern from `GeoChoropleth.svelte`).
2. Return the pattern fill from `fillForKey` (and the `DEFAULT_FILL` branch in
   the `<path>` / island-marker) when a state has no winner row, instead of the
   flat `#e2e8f0`.
3. Add a "No data" chip to the election map's legend/caption area, gated on
   `has_no_data` (mirror the `GeoChoropleth` `data-slot="nodata-key"` markup).
4. Confirm the legend strip (`IndiaPartyMap` party-swatch legend) has room for
   the chip without wrapping on mobile.

## Why deferred

- The election map's flat gray is NOT the reported "ugly stripes" bug - that was
  the welfare hatch, now fixed. This is a consistency polish, not a defect.
- Touching `IndiaPartyMap` (the home default theme) widens the blast radius;
  the user scoped the parent PR to welfare maps only.

## Out of scope for this follow-up

- Per-state AC / PC maps (`StateAcMapD3`, `StatePcMapD3`) - they have their own
  sub-threshold marker legend and a separate no-data story; assess separately if
  the dot-grid idiom should propagate there too.
