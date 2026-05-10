# Party-Colour System Rework

**Last Updated**: 2026-05-10
**Status**: Planned (Phase C.0 — must land before Phase C nav restructure)
**Trigger**: User raised the issue during the 2026-05-10 autopilot sign-off:

> "Each state will have at least 100 parties or at least let us say 30 parties and India has 30 states so 30 times 30 is going to be 900. Having maintaining 900 colors is not feasible. So we need to revert back or we need to let the system figure it out itself. … Same color for the same party is fine, but same color for different parties is not fine. … the human eye cannot discern one hex difference in color."

## Current state (audited 2026-05-10)

`frontend/src/lib/colors/parties.default.ts` is a hand-curated `Record<eci_code, { fill, text? }>` covering ~25 parties across the 4 states currently in scope (TN, KL, AS, WB). Unmapped parties hash into a 10-colour `d3.schemeTableau10` fallback. `colors/store.svelte.ts` overlays user overrides from localStorage.

### Why the current design doesn't scale

1. **Curation cost**: 30 states × ~30 parties ≈ 900 entries. Researching the iconic colour for each is real work and most state-level parties don't have a stable iconic colour.
2. **Fallback collisions**: ~880 parties hashed into 10 colours — almost any view of three or more parties will repeat colours.
3. **Perceptual distance**: even if we curated 900 unique hexes, hex-distance ≠ perceptual distance. Two browns differing by `#101010` are indistinguishable on a phone screen.
4. **Cross-state confusion**: the same hex used for an unrelated party in another state breaks recall when a user navigates between state pages.

### What's working and must be preserved

- **Iconic-colour anchors**: BJP saffron, INC blue, DMK red, AITC green, AAP broom-yellow are baked into citizen memory. These must override any algorithmic assignment.
- **ECI code as the key**: stable identifier, never invented. Same code → same colour everywhere.
- **User overrides via localStorage**: respect user preference; never overwrite.
- **NOTA / IND specials**: `NOTA` slate-grey, `IND` slate-light are reasonable conventions; keep.

## New direction

Adopt a **three-layer resolution model**:

```
override (user, localStorage)
    ↓ falls through to
anchor (curated iconic colour, ~30 nationally-recognised parties)
    ↓ falls through to
algorithm (deterministic perceptually-spaced assignment)
```

### Layer 1 — Anchors (curated, small set)

A short hand-curated list (~20-30 entries) for nationally or strongly regionally recognised parties whose flag/symbol colour is iconic:

- `369` BJP saffron, `742` INC blue, `582` DMK red, `75` ADMK green, `547` CPI(M) red, `544` CPI red, `140` AITC green, `1746` AAP broom-yellow, `369` (etc.) — keep the existing curated set; do not expand mechanically.

These are anchors — they win over the algorithm. If two anchors collide perceptually (which they shouldn't), the curated set is wrong and we fix the curation.

Codify as `frontend/src/lib/colors/anchors.ts` (renaming `parties.default.ts` for clarity).

### Layer 2 — Algorithmic assignment (the new core)

A deterministic function `partyColour(eci_code, in_use_codes)` that:

1. If the code is in the **anchor map**, returns it.
2. Otherwise, picks a colour from a **large evenly-spaced palette** in OkLCh space (perceptually uniform), seeded by a hash of the ECI code. Same code always maps to the same colour.
3. **In-use de-duplication pass**: when called with the list of currently-visible parties, the function ensures no two visible parties share a colour. If a hash-collision would force two visibles to the same swatch, the second falls forward to the next free OkLCh slot (still deterministic given the call order, which is itself derived from the ECI code list).

Properties:

- Same party always same colour, **across the whole site**, by default.
- No two parties on the same chart will ever collide visually.
- Anchors always win — BJP is always saffron whether or not other parties are in the room.
- Grows to 30+ parties on a single chart without eyeballing.

### Layer 3 — User override (existing, retain)

Unchanged. `colors.set(eci_code, color)` writes localStorage. Wins over both anchor and algorithm. Settings page lets users `reset(code)` or `resetAll()`.

## Algorithm sketch

```ts
// OkLCh evenly spaced over hue (excluding red/saffron/Congress-blue bands reserved for anchors).
// Lightness varies in a small band to maintain WCAG AA contrast against white text.
// Total swatches: ~36 distinct hues × 2 lightness bands = ~72 slots.

const PALETTE_OKLCH = generateOkLChPalette({
  hueSlots: 36,
  reservedHueRanges: [/* anchor hues — saffron, Congress-blue, etc. */],
  lightnessBands: [0.55, 0.42],   // mid + slightly darker
  chroma: 0.16,
});

function partyColour(code: string, inUseCodes: string[]): PartyColor {
  if (overrides[code]) return overrides[code];
  if (ANCHORS[code])   return ANCHORS[code];

  // Sort in-use codes deterministically so independent renders agree.
  const sorted = [...inUseCodes].sort();
  const taken  = new Set<number>();
  let assignment: PartyColor | null = null;

  for (const c of sorted) {
    if (ANCHORS[c]) continue;                           // anchors don't consume palette slots
    let slot = hash(c) % PALETTE_OKLCH.length;
    while (taken.has(slot)) slot = (slot + 1) % PALETTE_OKLCH.length;
    taken.add(slot);
    if (c === code) { assignment = oklchToRgbHex(PALETTE_OKLCH[slot]); break; }
  }
  return assignment ?? oklchToRgbHex(PALETTE_OKLCH[hash(code) % PALETTE_OKLCH.length]);
}
```

A pure-function shape — easy to test. Visual diff against existing screenshots required at PR review.

## Implementation phases

**P1 — Spike & test harness** (single PR)
- Add OkLCh palette generator + `partyColour(code, inUseCodes)` pure function under `frontend/src/lib/colors/`.
- Vitest covers: anchor wins, deterministic across calls, no two in-use parties collide, override wins.
- No call-site changes yet.

**P2 — Migrate call sites** (single PR)
- Audit every component that imports from `colors/`. Each one passes the in-use code list (it already knows it — that's what it's rendering).
- Visual-diff each chart on TN, KL, AS, WB. Screenshot tests via Playwright.

**P3 — Retire stale entries** (small PR)
- Strip `DEFAULT_PARTY_COLORS` of any entry that's not iconic (i.e. anything that was curated only because the algorithm wasn't ready). Keep ~20–30 anchors.
- Update [`docs/architecture/frontend/`](../docs/architecture/frontend/) (if relevant) and [`docs/concepts/electoral-hierarchy.md`](../docs/concepts/electoral-hierarchy.md) to describe the three-layer model.

## Risks

- **OkLCh→sRGB clipping**: some OkLCh values fall outside sRGB; clip at generation time and verify.
- **Browser support**: OkLCh CSS isn't universally supported but we don't need it in CSS — we generate hexes server-side (well, build-side) from OkLCh maths and emit hex strings to the DOM. No runtime dependency.
- **Screenshot churn**: every existing chart will get new colours for non-anchor parties. Communicate clearly in the changelog and refresh any docs/screenshots that pin specific colours.

## Out of scope (for this rework)

- **Alliance colouring** (NDA / UPA / INDIA bloc / Third Front): a separate concept. Tracked under the ruling-party overlay in the umbrella plan (RP decision, Phase B+).
- **Religion/region colour symbolism**: do not attempt. Colour science only.
- **Custom palettes per state**: not needed if the algorithm guarantees no in-view collisions.

## See also

- `frontend/src/lib/colors/parties.default.ts` (current anchors)
- `frontend/src/lib/colors/store.svelte.ts` (override store, retain)
- [`TODO/SOCIO-ECONOMIC-EXPANSION.md`](SOCIO-ECONOMIC-EXPANSION.md) — umbrella plan (RP decision; Phase C nav restructure)
- OkLCh primer: <https://bottosson.github.io/posts/oklab/>
- WCAG contrast ratios: <https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html>
