# Colour system

> **Status**: live as of 2026-05-08 (party colours), 2026-05-11 (indicator ramps). Module: [`frontend/src/lib/colors/`](../../../frontend/src/lib/colors/). 15 vitest cases across `party-colour.test.ts`.

## Why this exists

A polychromatic civic site has two colour problems:
1. **Party colours** must be recognisable (BJP saffron, INC light-blue, DMK red, AIADMK two-tone green) but also have to scale to ~80 active parties without becoming unreadable.
2. **Indicator ramps** must be perceptually uniform so a 10% darker swatch reads as ~10% more of the thing — across all hues.

Both problems reduce to "do colour math in a perceptual space, not in sRGB". yen-gov uses **OkLCh** (Björn Ottosson's improved Lab) as the working colour space.

## OkLCh in 90 seconds

OkLCh has three coordinates:

- **L (lightness)** 0..1, perceptually linear. `L=0.5` looks half as bright as `L=1.0` to the human eye, regardless of hue. sRGB's `#808080` is `L≈0.6` in OkLCh — sRGB is *not* perceptually linear.
- **C (chroma)** 0..~0.4, perceptual saturation. Roughly the same chroma at any hue means roughly the same colourfulness. sRGB saturation does *not* — pure sRGB blue is far less colourful than pure sRGB green.
- **h (hue)** 0..360°, an angle around the colour wheel. `h=30` is reddish-orange; `h=160` is teal; `h=250` is blue.

The yen-gov module uses Björn Ottosson's published transfer matrices (Oklab→linear-sRGB→sRGB) — the exact published constants, not approximations. See [`frontend/src/lib/colors/oklch.ts`](../../../frontend/src/lib/colors/oklch.ts).

The two operations we use everywhere:

```ts
oklchToHex({ L, C, h }) → "#rrggbb"     // forward, with sRGB clipping
hexToOklch("#rrggbb")    → { L, C, h }   // inverse, for ANCHORS calibration
```

## Three-layer party-colour resolver

Source: [`frontend/src/lib/colors/party-colour.ts`](../../../frontend/src/lib/colors/party-colour.ts).

When the UI needs a colour for party code `BJP`, it asks `colors.for("BJP")` (or `colors.forSet([...])`), which walks three layers:

### Layer 1 — Override

A party row can declare `display.colour: "#fa8b3e"` in `parties.json`. This wins over everything; used for parties whose ECI-published or self-declared colour is iconic and must be honoured exactly.

### Layer 2 — Anchor

`ANCHORS` in [`anchors.ts`](../../../frontend/src/lib/colors/anchors.ts) maps party codes to a tuned `{L, C, h}` triple. These are the parties citizens recognise by colour without thinking. Examples:

- `BJP` → saffron (h≈45°)
- `INC` → light-blue (h≈230°)
- `DMK` → red (h≈25°)
- `AITC` → grass-green (h≈135°)
- `AAP` → cyan (h≈195°)

Anchors aren't free-form hex codes; they're the perceptual coordinates. This means the same `BJP` swatch at L=0.55 and at L=0.78 (e.g. for hover or for a paler "neutral race" state) stay recognisably saffron, not drifting toward orange or yellow as sRGB scaling would.

### Layer 3 — Algorithmic

For unknown parties, hash the code to a hue, exclude reserved hue bands occupied by anchored parties (so a fresh regional party never gets BJP-saffron by accident), and emit `{L: 0.55, C: 0.16, h}`. The resulting colour is guaranteed:
- distinct from every anchor,
- consistent across reloads (deterministic on code),
- legible against white at L=0.55 (clarity rule — a11y is a project-level non-goal per CLAUDE.md §0).

`forSet([codes])` runs the algorithmic layer in *batch* mode: when the input set has multiple unanchored parties, hue allocation is round-robin across the available bands so the parties are maximally visually separated *within the chart*, rather than each computed in isolation.

### When to use `for` vs `forSet`

- `colors.for(code)` — single-party badges, candidate cards, "this party's tab" highlighting. Order-independent, returns a stable colour for that code.
- `colors.forSet(codes)` — multi-party charts (PartyBar, RacesBoard, IndiaMap, StateAcMap). The set context is what enables the round-robin hue allocation.

Migration of hot paths from `for` to `forSet` is queued in Phase 6A — see PLAN.md.

## Indicator sequential ramps

Indicator chropoleths use a sequential OkLCh ramp parameterised by hue:

```ts
sequentialSwatch(t, hue)   // t ∈ [0, 1] → hex
// L: 0.94 → 0.44   (very pale → mid-dark)
// C: 0.04 → 0.17   (low chroma → moderate chroma)
// h: constant
```

Hue is selected by the indicator's declared `direction`:

| `direction` | hue | meaning |
|---|---|---|
| `higher_is_better` | 160° | teal — clean, growth-coded |
| `lower_is_better` | 25° | red — alarm-coded |
| `neutral` | 250° | blue — descriptive only |

Crucially: **dark always means "more of the thing"**, regardless of direction. Colour intensity = quantity. Colour hue = whether-more-is-good. A citizen reading a darker patch on a `lower_is_better` (red) map reads "this state has *more* of the bad thing" without having to remember a per-chart legend convention. This is the inverse of the diverging palette ("dark green good, dark red bad") which forces the eye to do two interpretations at once.

## Reserved hue bands

To prevent algorithmic Layer-3 colours from clashing with iconic anchors, certain hue bands are reserved:

```
30..60°   — BJP saffron
20..30°   — DMK / SP / RJD red
220..245° — INC / NCP light-blue
195..210° — AAP cyan
130..150° — AITC / JD(U) green
```

A widening of any anchor's reserved band shows up as a vitest failure (`anchor reserves its band` in `party-colour.test.ts`), since the test enumerates 200 random codes and asserts none lands in any reserved band.

## Why not pre-pick 30 hex codes?

Tempting answer: "just hand-pick a Tableau-style palette of 30 distinct hex codes and assign them in order." Three reasons we didn't:

1. **Civic recognition cost**. BJP-saffron is not negotiable; INC-light-blue is not negotiable; AITC-green is not negotiable. A pre-picked palette either has to embed those (and then it's not arbitrary) or violate them (and confuse every citizen).
2. **Perceptual uniformity at variable lightness**. Hover states, highlighted-row states, and "this party's row in a sub-chart" states all need lighter/darker variants of the same colour. sRGB lightening of `#fa8b3e` drifts toward yellow; OkLCh lightening of the same swatch stays saffron.
3. **Long tail**. Indian elections have hundreds of registered parties, and the long tail genuinely matters in by-election charts. A perceptual generator handles the long tail; a hand-picked palette runs out at ~12.

## Files

| File | Role |
|---|---|
| [`oklch.ts`](../../../frontend/src/lib/colors/oklch.ts) | OkLCh ↔ hex conversions (Ottosson coefficients). |
| [`anchors.ts`](../../../frontend/src/lib/colors/anchors.ts) | The hand-tuned anchor table. |
| [`party-colour.ts`](../../../frontend/src/lib/colors/party-colour.ts) | Three-layer resolver; `for` and `forSet`. |
| [`store.svelte.ts`](../../../frontend/src/lib/colors/store.svelte.ts) | Svelte 5 rune wrapper exposed as `colors` to components. |
| [`party-colour.test.ts`](../../../frontend/src/lib/colors/party-colour.test.ts) | 15 vitest cases. |

## Decisions log

- **2026-05-08 — OkLCh adopted over HSL.** HSL's "saturation" is non-perceptual (HSL-pure-blue and HSL-pure-yellow have wildly different luminance and chroma). OkLCh's L is genuinely linear; this is what lets us share the same module between party colours and indicator ramps without two different lightness conventions.
- **2026-05-08 — Three-layer resolver, not "all hand-picked" or "all algorithmic".** Hand-picked-only doesn't scale to 80+ parties; algorithmic-only insults BJP/INC/DMK voters who recognise their party by colour at a glance.
- **2026-05-08 — `parties.default.ts` deleted.** Used to ship a hardcoded fallback colour table; superseded by the algorithmic layer.
- **2026-05-11 — `forSet` introduced.** Single-element calls (`colors.for(code)`) compute each colour in isolation; for charts with multiple unanchored parties this can produce hues that happen to be 30° apart and look "almost the same". `forSet` batches and round-robins hue allocation in the available bands.
- **2026-05-11 — Indicator ramps use sequential, not diverging.** Diverging ramps (red↔green centred on a midpoint) require a meaningful midpoint, which most civic indicators don't have. They also overload colour with both intensity and direction-of-goodness, which the sequential-with-direction-hue scheme separates cleanly.
