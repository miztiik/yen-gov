// Pure decision helper for the touch tap-to-pin interaction in
// MapChoropleth. Kept out of the component so the (otherwise maplibre-bound)
// logic has a unit-test surface — the same pattern as ac-reservation.ts and
// symbol-asset.ts.
//
// Without hover, a phone/tablet citizen can only reach the tooltip card by
// tapping a polygon, but a tap that also navigates flashes the card for a
// single frame. So on a coarse-pointer device the FIRST tap on a feature
// pins the card (no navigation); a SECOND tap on the SAME feature navigates.
// Desktop (fine pointer) and maps that don't opt in always navigate.

export type TapAction = "pin" | "navigate";

export interface TapDecisionInput {
  /** Whether the consumer opted into tap-to-pin. */
  tapToPin: boolean;
  /** Whether the device's primary pointer cannot hover (touch). */
  coarsePointer: boolean;
  /** The currently pinned feature key, or null when nothing is pinned. */
  pinnedKey: string | number | null;
  /** The key of the feature just tapped. */
  key: string | number;
}

/**
 * Decide whether a tap should pin the card or navigate.
 *
 * Returns `"pin"` only when tap-to-pin is on, the pointer is coarse, and the
 * tapped feature is not already the pinned one. Every other case (desktop,
 * opt-out, or a second tap on the same feature) returns `"navigate"`.
 */
export function resolveTapAction(input: TapDecisionInput): TapAction {
  const { tapToPin, coarsePointer, pinnedKey, key } = input;
  if (tapToPin && coarsePointer && pinnedKey !== key) {
    return "pin";
  }
  return "navigate";
}
