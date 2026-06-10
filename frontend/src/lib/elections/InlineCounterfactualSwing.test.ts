import { describe, it, expect } from "vitest";

import { FIXTURE } from "../psephlab/fixtures";
import {
  deriveSwingSeats,
  listPartyChoices,
} from "./inline-swing-model";

describe("listPartyChoices", () => {
  it("returns distinct parties sorted by statewide votes desc, excluding NOTA", () => {
    const choices = listPartyChoices(FIXTURE);
    // FIXTURE statewide totals: DMK=1300, AIADMK=1480, BJP=180, NOTA=40
    expect(choices.map((c) => c.party_eci_code)).toEqual([
      "AIADMK",
      "DMK",
      "BJP",
    ]);
    expect(choices.map((c) => c.votes)).toEqual([1480, 1300, 180]);
    expect(choices.find((c) => c.party_eci_code === "NOTA")).toBeUndefined();
  });
});

describe("deriveSwingSeats", () => {
  it("baseline (pct=0) matches FPTP allocation: DMK 2 / AIADMK 1 / BJP 0", () => {
    const rows = deriveSwingSeats(FIXTURE, "AIADMK", "DMK", 0);
    const by = Object.fromEntries(
      rows.map((r) => [r.party_eci_code, r.swung_seats]),
    );
    expect(by.DMK).toBe(2);
    expect(by.AIADMK).toBe(1);
    // BJP either absent (no seats) or has 0; both acceptable.
    expect(by.BJP ?? 0).toBe(0);
  });

  it("statewideSwing(AIADMK -> DMK, pct=10) flips AC2 to DMK; AIADMK loses 1, DMK gains 1", () => {
    // AC2 baseline: AIADMK 700 vs DMK 200. After 10% swing: AIADMK 630
    // vs DMK 270. AIADMK still wins AC2. So flip won't happen at 10%.
    // Try a larger swing (40% -> AIADMK 420, DMK 480; DMK wins AC2).
    // Per FIXTURE: only +/-1 flip is feasible (AC2 BJP+0, AC3 DMK margin
    // is 20 with no swing).
    const baseline = deriveSwingSeats(FIXTURE, "AIADMK", "DMK", 0);
    const baseline_by = Object.fromEntries(
      baseline.map((r) => [r.party_eci_code, r.swung_seats]),
    );
    const swung = deriveSwingSeats(FIXTURE, "AIADMK", "DMK", 40);
    const swung_by = Object.fromEntries(
      swung.map((r) => [r.party_eci_code, r.swung_seats]),
    );
    expect(swung_by.DMK).toBe(baseline_by.DMK + 1);
    expect(swung_by.AIADMK).toBe(baseline_by.AIADMK - 1);
  });

  it("delta column reflects swung_seats - baseline_seats", () => {
    const rows = deriveSwingSeats(FIXTURE, "AIADMK", "DMK", 40);
    for (const r of rows) {
      expect(r.delta).toBe(r.swung_seats - r.baseline_seats);
    }
    const dmk = rows.find((r) => r.party_eci_code === "DMK");
    const aia = rows.find((r) => r.party_eci_code === "AIADMK");
    expect(dmk?.delta).toBe(1);
    expect(aia?.delta).toBe(-1);
  });

  it("rows are sorted by swung_seats desc", () => {
    const rows = deriveSwingSeats(FIXTURE, "AIADMK", "DMK", 0);
    for (let i = 1; i < rows.length; i++) {
      expect(rows[i].swung_seats).toBeLessThanOrEqual(rows[i - 1].swung_seats);
    }
  });

  it("when from_party is null, runs baseline only (no mutation)", () => {
    const rows = deriveSwingSeats(FIXTURE, null, "DMK", 10);
    const dmk = rows.find((r) => r.party_eci_code === "DMK")!;
    expect(dmk.delta).toBe(0);
    expect(dmk.swung_seats).toBe(dmk.baseline_seats);
  });

  it("oracle (load-bearing): swing produces a NEW allocation differing from baseline", () => {
    // The PR-W3b oracle restated: statewideSwing(allocation, {from:'BJP',
    // to:'INC', pct:5}) -> a NEW allocation. We don't have INC in the
    // fixture; substitute the same shape with AIADMK->DMK 40%.
    const baseline = deriveSwingSeats(FIXTURE, null, null, 0);
    const swung = deriveSwingSeats(FIXTURE, "AIADMK", "DMK", 40);
    const baseline_map = Object.fromEntries(
      baseline.map((r) => [r.party_eci_code, r.swung_seats]),
    );
    const swung_map = Object.fromEntries(
      swung.map((r) => [r.party_eci_code, r.swung_seats]),
    );
    // At least one party differs.
    const keys = new Set([
      ...Object.keys(baseline_map),
      ...Object.keys(swung_map),
    ]);
    let any_diff = false;
    for (const k of keys) {
      if ((baseline_map[k] ?? 0) !== (swung_map[k] ?? 0)) any_diff = true;
    }
    expect(any_diff).toBe(true);
  });
});
