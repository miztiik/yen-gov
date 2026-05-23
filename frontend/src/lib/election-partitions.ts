// Table-specific physical partition helpers for the current elections store.
// ADR-0036 keeps these out of registerSlice itself: route/view-model code
// resolves logical state identity into the partition value required by the
// elections fact table.

export function electionStatePartition(stateCode: string): string {
  return `in_${stateCode.toLowerCase()}`;
}
