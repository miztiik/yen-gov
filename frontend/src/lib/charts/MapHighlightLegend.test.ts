// Render-shape contract for MapHighlightLegend.svelte (parent plan
// section 25.5). Component-level DOM (party-pill click target, slider
// chip render) is covered by Playwright in
// `frontend/e2e/e4-highlight-modes.spec.ts` per repo vitest doctrine
// (node-env; no jsdom canvas; no @testing-library/svelte). This file
// covers the legend's reducer + the module re-exports so a refactor
// that breaks the reducer fails before the e2e gate.

import { describe, expect, test } from "vitest";

import {
  DEFAULT_HIGHLIGHT_STATE,
  MIN_MARGIN_STEPS,
  advanceLegendState,
  type HighlightMode,
  type HighlightState,
  type LegendAction,
} from "./MapHighlightLegend.svelte";

const BJP_PID = "parties.IN.BJP";
const INC_PID = "parties.IN.INC";

describe("MapHighlightLegend module re-exports", () => {
  test("DEFAULT_HIGHLIGHT_STATE seeds margin mode with no selection", () => {
    expect(DEFAULT_HIGHLIGHT_STATE).toEqual({
      mode: "margin",
      selected_party_id: null,
      min_margin: 0,
    });
  });

  test("MIN_MARGIN_STEPS is the spec's 0/10/20/30 set", () => {
    expect([...MIN_MARGIN_STEPS]).toEqual([0, 10, 20, 30]);
  });
});

describe("MapHighlightLegend reducer (party-pill tap dispatches the right action)", () => {
  test("tap from margin -> party_won mode, party selected (mirrors UI tap)", () => {
    // The Svelte component calls `tapParty(party_id)` -> reducer.
    const action: LegendAction = { kind: "tap_party", party_id: BJP_PID };
    const next = advanceLegendState(DEFAULT_HIGHLIGHT_STATE, action);
    expect(next.mode).toBe<HighlightMode>("party_won");
    expect(next.selected_party_id).toBe(BJP_PID);
  });

  test("tap selected party clears + reverts to margin (toggle-off semantics)", () => {
    const state: HighlightState = {
      mode: "party_won",
      selected_party_id: BJP_PID,
      min_margin: 10,
    };
    const next = advanceLegendState(state, {
      kind: "tap_party",
      party_id: BJP_PID,
    });
    expect(next).toEqual({
      mode: "margin",
      selected_party_id: null,
      min_margin: 10,
    });
  });

  test("tap a different party in party_won mode just switches selection", () => {
    const state: HighlightState = {
      mode: "party_won",
      selected_party_id: BJP_PID,
      min_margin: 20,
    };
    const next = advanceLegendState(state, {
      kind: "tap_party",
      party_id: INC_PID,
    });
    expect(next).toEqual({
      mode: "party_won",
      selected_party_id: INC_PID,
      min_margin: 20,
    });
  });
});

describe("MapHighlightLegend reducer (mode switcher dispatch)", () => {
  test("set_mode -> party_won auto-picks first_party_id on the flip", () => {
    const next = advanceLegendState(
      DEFAULT_HIGHLIGHT_STATE,
      { kind: "set_mode", next: "party_won" },
      { first_party_id: BJP_PID },
    );
    expect(next.mode).toBe("party_won");
    expect(next.selected_party_id).toBe(BJP_PID);
  });

  test("set_mode -> margin preserves the selection so a flip back round-trips", () => {
    const state: HighlightState = {
      mode: "party_won",
      selected_party_id: INC_PID,
      min_margin: 20,
    };
    const back = advanceLegendState(state, { kind: "set_mode", next: "margin" });
    expect(back).toEqual({
      mode: "margin",
      selected_party_id: INC_PID,
      min_margin: 20,
    });
    const forth = advanceLegendState(back, { kind: "set_mode", next: "party_won" });
    expect(forth).toEqual(state);
  });
});

describe("MapHighlightLegend reducer (margin slider dispatch)", () => {
  test("set_min_margin updates the step in party_won mode", () => {
    const state: HighlightState = {
      mode: "party_won",
      selected_party_id: BJP_PID,
      min_margin: 0,
    };
    const next = advanceLegendState(state, { kind: "set_min_margin", next: 20 });
    expect(next.min_margin).toBe(20);
    expect(next.mode).toBe("party_won");
    expect(next.selected_party_id).toBe(BJP_PID);
  });

  test("set_min_margin in margin mode still updates (slider is hidden, but state is durable)", () => {
    const next = advanceLegendState(
      DEFAULT_HIGHLIGHT_STATE,
      { kind: "set_min_margin", next: 30 },
    );
    expect(next.min_margin).toBe(30);
    expect(next.mode).toBe("margin");
  });
});
