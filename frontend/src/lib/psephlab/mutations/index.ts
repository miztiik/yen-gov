// Mutation registry. Adding a new mutation = new file + one entry here.
// The UI's "+ Add mutation" menu reads `MUTATIONS`.

import type { MutationConfig, MutationPlugin } from "../types";
import { perAcSwing } from "./perAcSwing";
import { statewideSwing } from "./statewideSwing";
import { thresholdDrop } from "./thresholdDrop";
import { partyBag } from "./partyBag";

// Cast collapses the per-mutation generic into the base `MutationPlugin`
// surface so consumers can iterate without a discriminated-union switch
// (the per-mutation `apply` still receives its narrowed config thanks to
// the runtime id check in `applyMutation` below).
export const MUTATIONS: MutationPlugin[] = [
  perAcSwing as unknown as MutationPlugin,
  statewideSwing as unknown as MutationPlugin,
  thresholdDrop as unknown as MutationPlugin,
  partyBag as unknown as MutationPlugin,
];

const BY_ID = new Map<string, MutationPlugin>(MUTATIONS.map(m => [m.id, m]));

export function mutationById(id: string): MutationPlugin | null {
  return BY_ID.get(id) ?? null;
}
