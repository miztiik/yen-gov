// Pure-helper tests for map-highlight-utils.ts (parent plan section 25.5).
//
// Component-level shape (legend renders, party-pill tap, slider step) is
// covered by Playwright in `frontend/e2e/e4-highlight-modes.spec.ts`
// (per repo vitest doctrine - node-env, no jsdom canvas, no
// @testing-library/svelte). This file covers every branch of the pure
// helpers (`marginOpacity`, `cellTreatment`, `advanceLegendState`) +
// the four spec-named corners of `cellTreatment`.

import { describe, expect, test } from "vitest";

import {
  DEFAULT_HIGHLIGHT_STATE,
  MIN_MARGIN_STEPS,
  NEUTRAL_HEX_FALLBACK,
  RECEDE_OPACITY,
  advanceLegendState,
  cellTreatment,
  marginOpacity,
  type CellTreatmentInput,
} from "./map-highlight-utils";

const BJP_HEX = "#f59e0b";
const NEUTRAL = NEUTRAL_HEX_FALLBACK;
const BJP_PID = "parties.IN.BJP";
const INC_PID = "parties.IN.INC";

function bjpCell(overrides: Partial<CellTreatmentInput> = {}): CellTreatmentInput {
  return {
    mode: "margin",
    selected_party_id: null,
    min_margin: 0,
    winner_party_id: BJP_PID,
    margin_pct: 12,
    winner_party_hex: BJP_HEX,
    neutral_hex: NEUTRAL,
    ...overrides,
  };
}

describe("marginOpacity", () => {
  test("floor at 0pp - returns 0.35", () => {
    expect(marginOpacity(0)).toBeCloseTo(0.35, 6);
    expect(marginOpacity(null)).toBeCloseTo(0.35, 6);
    expect(marginOpacity(undefined)).toBeCloseTo(0.35, 6);
  });
  test("saturates at 30pp+ - returns 0.95", () => {
    expect(marginOpacity(30)).toBeCloseTo(0.95, 6);
    expect(marginOpacity(45)).toBeCloseTo(0.95, 6);
    expect(marginOpacity(100)).toBeCloseTo(0.95, 6);
  });
  test("linear ramp at 15pp - midpoint 0.65", () => {
    expect(marginOpacity(15)).toBeCloseTo(0.65, 6);
  });
  test("treats negative margin as |abs| - same as positive", () => {
    expect(marginOpacity(-15)).toBeCloseTo(0.65, 6);
    expect(marginOpacity(-30)).toBeCloseTo(0.95, 6);
  });
  test("knife-edge wins (0..1pp) read as the floor", () => {
    expect(marginOpacity(0.5)).toBeGreaterThanOrEqual(0.35);
    expect(marginOpacity(0.5)).toBeLessThan(0.4);
  });
});

describe("cellTreatment - mode === 'margin'", () => {
  test("narrow win (5pp) - winner colour, marginOpacity(5)", () => {
    const r = cellTreatment(bjpCell({ margin_pct: 5 }));
    expect(r.fill).toBe(BJP_HEX);
    expect(r.opacity).toBeCloseTo(0.35 + (5 / 30) * 0.6, 6);
    expect(r.stroke).toBeNull();
  });
  test("landslide (30pp+) - winner colour saturates @ 0.95", () => {
    const r = cellTreatment(bjpCell({ margin_pct: 35 }));
    expect(r.fill).toBe(BJP_HEX);
    expect(r.opacity).toBeCloseTo(0.95, 6);
    expect(r.stroke).toBeNull();
  });
  test("selected_party_id is IGNORED in margin mode", () => {
    const a = cellTreatment(bjpCell({ margin_pct: 10 }));
    const b = cellTreatment(
      bjpCell({ margin_pct: 10, selected_party_id: INC_PID }),
    );
    expect(a).toEqual(b);
  });
});

describe("cellTreatment - mode === 'party_won'", () => {
  test("matches selected party + margin >= min_margin - full opacity, winner colour", () => {
    const r = cellTreatment(
      bjpCell({
        mode: "party_won",
        selected_party_id: BJP_PID,
        min_margin: 10,
        margin_pct: 15,
      }),
    );
    expect(r.fill).toBe(BJP_HEX);
    expect(r.opacity).toBe(1);
    expect(r.stroke).toBeNull();
  });
  test("matches selected party but margin < min_margin - recedes", () => {
    const r = cellTreatment(
      bjpCell({
        mode: "party_won",
        selected_party_id: BJP_PID,
        min_margin: 20,
        margin_pct: 8,
      }),
    );
    expect(r.fill).toBe(NEUTRAL);
    expect(r.opacity).toBe(RECEDE_OPACITY);
    expect(r.stroke).toBe(NEUTRAL);
  });
  test("does not match selected party - recedes", () => {
    const r = cellTreatment(
      bjpCell({
        mode: "party_won",
        selected_party_id: INC_PID,
        min_margin: 0,
        margin_pct: 25,
      }),
    );
    expect(r.fill).toBe(NEUTRAL);
    expect(r.opacity).toBe(RECEDE_OPACITY);
    expect(r.stroke).toBe(NEUTRAL);
  });
  test("matches when min_margin === 0 (no filter)", () => {
    const r = cellTreatment(
      bjpCell({
        mode: "party_won",
        selected_party_id: BJP_PID,
        min_margin: 0,
        margin_pct: 1,
      }),
    );
    expect(r.fill).toBe(BJP_HEX);
    expect(r.opacity).toBe(1);
  });
  test("negative margin treated as |abs| for the filter", () => {
    const r = cellTreatment(
      bjpCell({
        mode: "party_won",
        selected_party_id: BJP_PID,
        min_margin: 10,
        margin_pct: -15,
      }),
    );
    expect(r.fill).toBe(BJP_HEX);
    expect(r.opacity).toBe(1);
  });
  test("null selected_party_id - all cells recede", () => {
    const r = cellTreatment(
      bjpCell({
        mode: "party_won",
        selected_party_id: null,
        margin_pct: 30,
      }),
    );
    expect(r.fill).toBe(NEUTRAL);
    expect(r.opacity).toBe(RECEDE_OPACITY);
    expect(r.stroke).toBe(NEUTRAL);
  });
  test("null winner_party_id - cell recedes even if selected_party_id is set", () => {
    const r = cellTreatment(
      bjpCell({
        mode: "party_won",
        selected_party_id: BJP_PID,
        winner_party_id: null,
        margin_pct: 30,
      }),
    );
    expect(r.fill).toBe(NEUTRAL);
    expect(r.opacity).toBe(RECEDE_OPACITY);
  });
});

describe("advanceLegendState", () => {
  test("set_mode no-op when already at target mode", () => {
    const next = advanceLegendState(
      DEFAULT_HIGHLIGHT_STATE,
      { kind: "set_mode", next: "margin" },
    );
    expect(next).toBe(DEFAULT_HIGHLIGHT_STATE);
  });
  test("set_mode -> party_won auto-picks first_party_id when none selected", () => {
    const next = advanceLegendState(
      DEFAULT_HIGHLIGHT_STATE,
      { kind: "set_mode", next: "party_won" },
      { first_party_id: BJP_PID },
    );
    expect(next.mode).toBe("party_won");
    expect(next.selected_party_id).toBe(BJP_PID);
    expect(next.min_margin).toBe(0);
  });
  test("set_mode -> party_won leaves selected_party_id null when no first_party_id supplied", () => {
    const next = advanceLegendState(
      DEFAULT_HIGHLIGHT_STATE,
      { kind: "set_mode", next: "party_won" },
    );
    expect(next.mode).toBe("party_won");
    expect(next.selected_party_id).toBeNull();
  });
  test("set_mode -> margin preserves selected_party_id (round-trip)", () => {
    const next = advanceLegendState(
      { mode: "party_won", selected_party_id: BJP_PID, min_margin: 20 },
      { kind: "set_mode", next: "margin" },
    );
    expect(next).toEqual({
      mode: "margin",
      selected_party_id: BJP_PID,
      min_margin: 20,
    });
  });
  test("tap_party from margin mode -> flips to party_won + selects", () => {
    const next = advanceLegendState(
      DEFAULT_HIGHLIGHT_STATE,
      { kind: "tap_party", party_id: BJP_PID },
    );
    expect(next).toEqual({
      mode: "party_won",
      selected_party_id: BJP_PID,
      min_margin: 0,
    });
  });
  test("tap_party of currently-selected party -> clears + reverts to margin", () => {
    const next = advanceLegendState(
      { mode: "party_won", selected_party_id: BJP_PID, min_margin: 10 },
      { kind: "tap_party", party_id: BJP_PID },
    );
    expect(next).toEqual({
      mode: "margin",
      selected_party_id: null,
      min_margin: 10,
    });
  });
  test("tap_party of different party while in party_won -> switches selection", () => {
    const next = advanceLegendState(
      { mode: "party_won", selected_party_id: BJP_PID, min_margin: 20 },
      { kind: "tap_party", party_id: INC_PID },
    );
    expect(next).toEqual({
      mode: "party_won",
      selected_party_id: INC_PID,
      min_margin: 20,
    });
  });
  test("set_min_margin updates the step", () => {
    for (const step of MIN_MARGIN_STEPS) {
      const next = advanceLegendState(
        { mode: "party_won", selected_party_id: BJP_PID, min_margin: 0 },
        { kind: "set_min_margin", next: step },
      );
      expect(next.min_margin).toBe(step);
      expect(next.mode).toBe("party_won");
      expect(next.selected_party_id).toBe(BJP_PID);
    }
  });
  test("set_min_margin no-op when already at target step", () => {
    const before = { mode: "party_won" as const, selected_party_id: BJP_PID, min_margin: 20 as const };
    const next = advanceLegendState(before, { kind: "set_min_margin", next: 20 });
    expect(next).toBe(before);
  });
});

describe("contract - MIN_MARGIN_STEPS is the spec's 0/10/20/30 set", () => {
  test("matches the parent plan 25.5 stepped slider domain", () => {
    expect([...MIN_MARGIN_STEPS]).toEqual([0, 10, 20, 30]);
  });
});
