// Table-specific physical partition helpers for the current elections store.
// ADR-0036 keeps these out of registerSlice itself: route/view-model code
// resolves logical state identity into the partition value required by the
// elections fact table. ADR-0050: partition values are LGD-name slugs
// (e.g. "tamil-nadu") sourced from `datasets/taxonomy/lgd_states.json`.
// Unknown ECI codes (e.g. test fixtures) fall back to lowercase to avoid
// breaking empty-result tests; real lookups always resolve through the map.

import { ECI_TO_LGD_SLUG } from "./maplibre/sources";

export function electionStatePartition(stateCode: string): string {
  return ECI_TO_LGD_SLUG[stateCode] ?? stateCode.toLowerCase();
}
