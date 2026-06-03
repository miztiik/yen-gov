// Recover the citizen-facing eci_no from a map feature's hover/click/select
// key (Row B3, ADR-0049).
//
// MapChoropleth emits the canonical join property as the event key. After the
// Row B3 flip that property is `lgd_ac_id` for covered AC states, while the
// winner rows the tooltip / navigation consume are keyed by eci_no. Both the
// hover tooltip builder AND the click-to-navigate handler must reverse this
// the same way, or one drifts from the other — which is exactly how the geo
// tooltip silently went blank (the tooltip path missed the reverse-map the
// select path already had). Sharing this helper keeps the two in lockstep.
//
// Recovery order:
//   1. `reverse` (lgd_ac_id -> eci_no) for covered states once the crosswalk
//      has resolved.
//   2. the feature's `ac_no` label (eci_no-valued) during the brief pre-
//      crosswalk window and on covered features that carry the label.
//   3. the raw numeric key, for unmapped states (S03/Assam `ac_no`,
//      U08/J&K `seat_id`) whose join property is already eci_no/seat-valued.

export function recoverEciNo(
  key: string | number,
  props: Record<string, unknown> | undefined,
  reverse: Map<number, number> | null,
): number {
  const raw = Number(key);
  const acno = props?.ac_no;
  return (
    reverse?.get(raw) ??
    (acno != null && Number.isFinite(Number(acno)) ? Number(acno) : raw)
  );
}
