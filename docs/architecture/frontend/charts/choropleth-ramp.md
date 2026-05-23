# Choropleth ramp contract (Phase 5)

**Last Updated**: 2026-05-25

Locks the existing sequential-choropleth ramp's contract without changing visible math. Promotes ramp endpoints to exported constants, adds an OkLCh-space accessor for future tuning work, and pins monotonicity via tests. Any actual tuning (visible math changes) requires screenshot review on a citizen route per the [plan §5](../../../../docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md).

## What it is

In [`frontend/src/lib/indicators.ts`](../../../../frontend/src/lib/indicators.ts) (and re-exported from the colour module):

- Four exported constants:
  - `SEQUENTIAL_RAMP_L_START` = 0.94 (light end of OkLCh L axis)
  - `SEQUENTIAL_RAMP_L_END` = 0.44 (dark end)
  - `SEQUENTIAL_RAMP_C_START` = 0.04 (low chroma)
  - `SEQUENTIAL_RAMP_C_END` = 0.17 (high chroma)
- `sequentialSwatchOkLCh(t, hue) → { l, c, h }` — returns the raw OkLCh triple BEFORE hex conversion. The primitive for tuning work (L/C in OkLCh space is perceptually uniform).
- `sequentialSwatch(t, hue) → "#rrggbb"` — now delegates to `sequentialSwatchOkLCh` + [`oklchToHex`](../../../../frontend/src/lib/colors/oklch.ts). Hex output is BYTE-IDENTICAL to the previous implementation.

## Doctrinal rules

- **Ramp endpoints are CONSTANTS.** Tuning them requires editing all four constants in the same commit, re-running the ramp-monotonicity tests, AND screenshot review on a real citizen choropleth route. The constants exist so the test contract can lock the safe band; the screenshot review exists because monotonicity does not prove perceptual quality on Indian-context maps.
- **OkLCh is the tuning surface.** Future tuning PRs operate on `sequentialSwatchOkLCh`'s L and C values, not on the hex output. Tuning in sRGB hex is forbidden: it breaks perceptual uniformity and can fail gamut.
- **Monotonicity tests are the lock.**
  - L must decrease strictly across the 5 stops at hue 160.
  - C must increase strictly across the 5 stops at hue 25.
  - Hex output must be unique across the 5 stops at hue 250 (no two stops collapse to the same colour).
  - Constants must remain inside the safe band (`L ∈ [0.4, 0.95]`, `C ∈ [0.04, 0.20]`).
- **No agent tunes the ramp unattended.** Per the plan, agents that detect "the ramp could be punchier" stop and ask the human for a screenshot review. Auto-tuning is structurally out of scope.

## Test surface

- [`frontend/src/lib/indicators.test.ts`](../../../../frontend/src/lib/indicators.test.ts) — 4 vitest cases added in Phase 5: L monotonicity (hue 160), C monotonicity (hue 25), hex uniqueness (hue 250), safe-band check for the four constants.

## See also

- [`../colours.md`](../colours.md) — the colour-system subsystem doc that surfaces `sequentialSwatchOkLCh` and the ramp contract.
- [`overview.md`](../overview.md) — visualization catalog (choropleth row).
- [docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md §5](../../../../docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md) — plan's "needs screenshot review" rule.

## Historical citations

Distils `.commit-msg-50.txt` and `.pr-body-50.md` (deleted on distillation). Merged as PR #162.
