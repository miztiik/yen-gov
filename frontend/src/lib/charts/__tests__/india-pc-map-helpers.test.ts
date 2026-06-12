// Pure helper tests for IndiaPcMapD3.svelte / StatePcMapD3.svelte
// (PR rows A + B; restoration of the PC choropleth deferred in
// PR #954). Per repo vitest doctrine the renderers themselves are
// covered by the Playwright @elections smoke; vitest covers the
// grain-agnostic join / paint formula in isolation.

import { describe, it, expect } from "vitest";
import {
  pcUniqueId,
  buildPcCellPaint,
  buildPartyKeyToPid,
  hiddenPidSet,
  type PcCellRow,
} from "../india-pc-map-helpers";
import {
  DEFAULT_HIGHLIGHT_STATE,
  NEUTRAL_HEX_FALLBACK,
} from "../map-highlight-utils";

const NEUTRAL = NEUTRAL_HEX_FALLBACK;

const sharedDefault = {
  mode: DEFAULT_HIGHLIGHT_STATE.mode,
  selected_party_id: DEFAULT_HIGHLIGHT_STATE.selected_party_id,
  min_margin: DEFAULT_HIGHLIGHT_STATE.min_margin,
  neutral_hex: NEUTRAL,
};

function row(over: Partial<PcCellRow> = {}): PcCellRow {
  return {
    unique_id: "S07_8",
    party_id: "parties.IN.BJP",
    margin_pct: 12,
    winner_party_hex: "#ff9933",
    ...over,
  };
}

describe("pcUniqueId", () => {
  it("joins state_code + eci_no with an underscore to match topojson properties.unique_id", () => {
    // Spot-checks against the on-disk format observed in
    // datasets/boundaries/electoral/delim=2024/pc/all.topojson:
    // first feature is "S07_8" (Bhiwani-Mahendragarh, Haryana).
    expect(pcUniqueId("S07", 8)).toBe("S07_8");
    expect(pcUniqueId("S24", 1)).toBe("S24_1");
    expect(pcUniqueId("U01", 1)).toBe("U01_1");
  });
});

describe("buildPcCellPaint - margin mode (default)", () => {
  it("produces one entry per row keyed by unique_id", () => {
    const rows: PcCellRow[] = [
      row({ unique_id: "S07_8" }),
      row({ unique_id: "S24_1" }),
      row({ unique_id: "S08_1" }),
    ];
    const map = buildPcCellPaint(rows, sharedDefault);
    expect(map.size).toBe(3);
    expect([...map.keys()].sort()).toEqual(["S07_8", "S08_1", "S24_1"]);
  });

  it("fill = winner_party_hex in margin mode", () => {
    const map = buildPcCellPaint(
      [row({ winner_party_hex: "#19aa56" })],
      sharedDefault,
    );
    expect(map.get("S07_8")?.fill).toBe("#19aa56");
  });

  it("opacity scales with margin (larger margin -> higher opacity)", () => {
    const small = buildPcCellPaint([row({ margin_pct: 2 })], sharedDefault);
    const large = buildPcCellPaint([row({ margin_pct: 25 })], sharedDefault);
    const big_o = large.get("S07_8")?.opacity ?? 0;
    const small_o = small.get("S07_8")?.opacity ?? 0;
    expect(big_o).toBeGreaterThan(small_o);
    // Floor + ceiling per the marginOpacity contract:
    expect(small_o).toBeGreaterThanOrEqual(0.35);
    expect(big_o).toBeLessThanOrEqual(0.95);
  });

  it("treats negative margins as |signed| (the winner is still the winner)", () => {
    const pos = buildPcCellPaint([row({ margin_pct: 10 })], sharedDefault);
    const neg = buildPcCellPaint([row({ margin_pct: -10 })], sharedDefault);
    expect(pos.get("S07_8")?.opacity).toBe(neg.get("S07_8")?.opacity);
  });
});

describe("buildPcCellPaint - party_won mode", () => {
  it("matches the selected party -> party hex at full opacity", () => {
    const map = buildPcCellPaint(
      [row({ party_id: "parties.IN.BJP", winner_party_hex: "#ff9933" })],
      {
        ...sharedDefault,
        mode: "party_won",
        selected_party_id: "parties.IN.BJP",
        min_margin: 0,
      },
    );
    const cell = map.get("S07_8")!;
    expect(cell.fill).toBe("#ff9933");
    expect(cell.opacity).toBe(1);
  });

  it("non-matching party recedes to neutral at low opacity", () => {
    const map = buildPcCellPaint(
      [row({ party_id: "parties.IN.INC", winner_party_hex: "#19aa56" })],
      {
        ...sharedDefault,
        mode: "party_won",
        selected_party_id: "parties.IN.BJP",
        min_margin: 0,
      },
    );
    const cell = map.get("S07_8")!;
    expect(cell.fill).toBe(NEUTRAL);
    expect(cell.opacity).toBeLessThan(0.35);
  });

  it("matched party with margin below min_margin still recedes", () => {
    const map = buildPcCellPaint(
      [row({ party_id: "parties.IN.BJP", margin_pct: 5 })],
      {
        ...sharedDefault,
        mode: "party_won",
        selected_party_id: "parties.IN.BJP",
        min_margin: 10,
      },
    );
    const cell = map.get("S07_8")!;
    expect(cell.fill).toBe(NEUTRAL);
    expect(cell.opacity).toBeLessThan(0.35);
  });
});

describe("buildPcCellPaint - overrides (Row F party-filter rail)", () => {
  it("fillsOverride wins over cellTreatment fill", () => {
    const map = buildPcCellPaint(
      [row({ winner_party_hex: "#19aa56" })],
      sharedDefault,
      { S07_8: NEUTRAL },
      undefined,
    );
    expect(map.get("S07_8")?.fill).toBe(NEUTRAL);
  });

  it("opacitiesOverride wins over cellTreatment opacity", () => {
    const map = buildPcCellPaint(
      [row({ margin_pct: 25 })], // large margin -> ~0.85 opacity
      sharedDefault,
      undefined,
      { S07_8: 0.18 }, // recede
    );
    expect(map.get("S07_8")?.opacity).toBe(0.18);
  });

  it("overrides apply per-unique_id only (non-matching rows untouched)", () => {
    const rows: PcCellRow[] = [
      row({ unique_id: "S07_8" }),
      row({ unique_id: "S24_1" }),
    ];
    const map = buildPcCellPaint(
      rows,
      sharedDefault,
      { S07_8: NEUTRAL }, // only S07_8 overridden
      { S07_8: 0.18 },
    );
    expect(map.get("S07_8")?.fill).toBe(NEUTRAL);
    expect(map.get("S07_8")?.opacity).toBe(0.18);
    expect(map.get("S24_1")?.fill).toBe("#ff9933"); // unchanged
    expect(map.get("S24_1")?.opacity).toBeGreaterThan(0.18);
  });
});

describe("buildPartyKeyToPid - PartyBar / cellTreatment identity bridge", () => {
  it("keys by party_eci_code when present", () => {
    const m = buildPartyKeyToPid([
      {
        party_eci_code: "BJP",
        party_short: "Bharatiya Janata Party",
        party_id: "parties.IN.BJP",
      },
    ]);
    expect(m.get("BJP")).toBe("parties.IN.BJP");
    expect(m.has("Bharatiya Janata Party")).toBe(false);
  });

  it("falls back to party_short when eci_code is null", () => {
    const m = buildPartyKeyToPid([
      {
        party_eci_code: null,
        party_short: "IND",
        party_id: "parties.IN.IND",
      },
    ]);
    expect(m.get("IND")).toBe("parties.IN.IND");
  });

  it("falls back to 'UNK' when both eci_code + party_short are null", () => {
    const m = buildPartyKeyToPid([
      { party_eci_code: null, party_short: null, party_id: "parties.IN.UNK" },
    ]);
    expect(m.get("UNK")).toBe("parties.IN.UNK");
  });

  it("ignores duplicate keys (first-write-wins)", () => {
    const m = buildPartyKeyToPid([
      { party_eci_code: "BJP", party_short: null, party_id: "parties.IN.BJP" },
      {
        party_eci_code: "BJP",
        party_short: null,
        party_id: "parties.IN.BJP2",
      },
    ]);
    expect(m.get("BJP")).toBe("parties.IN.BJP"); // first wins
  });
});

describe("hiddenPidSet - hidden_parties Set -> party_id Set", () => {
  it("translates each hidden key through key_to_pid", () => {
    const key_to_pid = new Map<string, string>([
      ["BJP", "parties.IN.BJP"],
      ["INC", "parties.IN.INC"],
      ["DMK", "parties.IN.DMK"],
    ]);
    const hidden = new Set(["BJP", "INC"]);
    const pids = hiddenPidSet(hidden, key_to_pid);
    expect(pids.has("parties.IN.BJP")).toBe(true);
    expect(pids.has("parties.IN.INC")).toBe(true);
    expect(pids.has("parties.IN.DMK")).toBe(false);
    expect(pids.size).toBe(2);
  });

  it("skips keys not present in the lookup (defensive)", () => {
    const key_to_pid = new Map<string, string>([["BJP", "parties.IN.BJP"]]);
    const hidden = new Set(["BJP", "UnknownParty"]);
    const pids = hiddenPidSet(hidden, key_to_pid);
    expect(pids.size).toBe(1);
    expect(pids.has("parties.IN.BJP")).toBe(true);
  });

  it("returns empty set when hidden_parties is empty", () => {
    const key_to_pid = new Map<string, string>([["BJP", "parties.IN.BJP"]]);
    const pids = hiddenPidSet(new Set(), key_to_pid);
    expect(pids.size).toBe(0);
  });
});
