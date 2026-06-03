import { describe, it, expect } from "vitest";
import { recoverEciNo } from "./ac-key-recovery";

describe("recoverEciNo", () => {
  it("reverse-maps a covered-state lgd_ac_id key to eci_no", () => {
    // Covered state: MapChoropleth emits the canonical join (lgd_ac_id) as the
    // hover/select key. The crosswalk reverse map (lgd_ac_id -> eci_no) must
    // recover the eci_no the winner rows are keyed by. This is the exact path
    // that silently returned undefined in the tooltip before the fix.
    const reverse = new Map<number, number>([
      [900001, 1],
      [900002, 2],
    ]);
    expect(recoverEciNo(900001, { ac_no: 1 }, reverse)).toBe(1);
    expect(recoverEciNo(900002, { ac_no: 2 }, reverse)).toBe(2);
  });

  it("falls back to the ac_no label when the key is not in the reverse map", () => {
    // Pre-crosswalk window: reverse map empty/missing the key, but the feature
    // carries the eci_no-valued ac_no label.
    const reverse = new Map<number, number>();
    expect(recoverEciNo(900003, { ac_no: 7 }, reverse)).toBe(7);
    expect(recoverEciNo(900003, { ac_no: 7 }, null)).toBe(7);
  });

  it("falls back to the raw key for unmapped states (no reverse map, no label)", () => {
    // Unmapped states (S03/Assam, U08/J&K): the join property is already
    // eci_no/seat-valued, so the raw key passes through.
    expect(recoverEciNo(42, undefined, null)).toBe(42);
    expect(recoverEciNo("42", {}, null)).toBe(42);
  });

  it("prefers the reverse map over the ac_no label when both resolve", () => {
    const reverse = new Map<number, number>([[900004, 4]]);
    // The lgd key resolves via reverse; the (here intentionally different)
    // ac_no must not win.
    expect(recoverEciNo(900004, { ac_no: 99 }, reverse)).toBe(4);
  });
});
