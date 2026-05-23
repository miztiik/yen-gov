# Ranked-comparison helpers

Pure helpers for ranked-comparison renderers (Phase 3 of
`docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md`).

## Exports

| Symbol                  | Purpose                                                                 |
| ----------------------- | ----------------------------------------------------------------------- |
| `computePeerBand`       | Median / IQR / p10_p90 over an array of numeric values (nulls ignored). |
| `projectPeerBandMarker` | Project a `PeerBand` onto `[0, 1]` relative to a bar-area max.          |
| `computeGapLine`        | Citizen-facing gap wording for a home + compare pair.                   |

## Rules

- **No DOM, no Svelte runes** — pure functions only.
- **Honesty**: wording NEVER says "better" or "worse" — direction is in
  `verdict` for renderers to badge separately. Preserves the
  "suppress dominance verbs" rule from `config/processing.json` in
  spirit.
- **Closed enums**: `IndicatorDirection`, `PeerBandKind`, `direction`,
  `verdict` are all closed unions (CLAUDE.md §10 three-place lock).
- **No fetch telemetry** (R-24).
- **No state hardcoding**: the home / compare names are caller-supplied
  strings.

## Plan trace

| Plan task                                   | Helper                                       |
| ------------------------------------------- | -------------------------------------------- |
| "median marker or peer-band marker"         | `computePeerBand` + `projectPeerBandMarker`  |
| "direction-aware gap line"                  | `computeGapLine`                             |
| "preserve honesty: never say better/worse"  | `verdict` field (not in `wording`)           |

## Tests

`helpers.test.ts` covers:

- Median collapse, IQR widening, p10_p90 widest envelope.
- Null / undefined / NaN handling.
- Empty input.
- Bar-area max clamp + overflow + zero.
- All four direction × verdict combinations.
- Equal values.
- Neutral direction never claims goodness.
- Missing endpoints in either slot.
- Wording assertion: never contains "better" or "worse".
