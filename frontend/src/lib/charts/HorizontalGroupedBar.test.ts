import { describe, expect, it } from "vitest";

import {
  buildHorizontalGroupedBarViewModel,
  type GroupedBarViewModel,
} from "./multi-dim-view-models";
import { legendColour } from "./HorizontalGroupedBar.svelte";

// Component-level DOM assertions are deferred to Playwright (vitest is
// node-env without jsdom — see ChartShell rationale). This file
// exercises the renderer's pure module-scope `legendColour` helper +
// the contract between the Phase 1.6 builder and the renderer's
// expected shape.

interface Row {
  id: string;
  label: string;
  pinned_rank?: number | null;
  energy_solar: number | null;
  energy_wind: number | null;
  energy_coal: number | null;
}

const FIXTURE: readonly Row[] = [
  {
    id: "KA",
    label: "Karnataka",
    pinned_rank: 0,
    energy_solar: 7500,
    energy_wind: 5200,
    energy_coal: 9200,
  },
  {
    id: "TN",
    label: "Tamil Nadu",
    energy_solar: 6300,
    energy_wind: 9400,
    energy_coal: 4400,
  },
  {
    id: "GJ",
    label: "Gujarat",
    energy_solar: 10300,
    energy_wind: 8800,
    energy_coal: 8400,
  },
  {
    id: "MH",
    label: "Maharashtra",
    energy_solar: 4900,
    energy_wind: 5300,
    energy_coal: null, // missing — must still produce a cell
  },
];

function toRow(r: Row) {
  return {
    id: r.id,
    label: r.label,
    pinned_rank: r.pinned_rank ?? null,
    cells: [
      { group_id: "solar", group_label: "Solar", value: r.energy_solar, colour: "#facc15" },
      { group_id: "wind", group_label: "Wind", value: r.energy_wind, colour: "#22c55e" },
      { group_id: "coal", group_label: "Coal", value: r.energy_coal, colour: "#475569" },
    ],
  };
}

const VM: GroupedBarViewModel<Row> = buildHorizontalGroupedBarViewModel({
  rows: FIXTURE,
  toRow,
  policy: "pinned_then_value",
  options: { best_is_high: true },
  group_order: ["solar", "wind", "coal"],
});

describe("HorizontalGroupedBar renderer contract", () => {
  it("view-model emits rectangular grid with missing cells preserved", () => {
    expect(VM.rows.length).toBe(FIXTURE.length);
    for (const row of VM.rows) {
      expect(row.cells.length).toBe(3);
      expect(row.cells.map(c => c.group_id)).toEqual(["solar", "wind", "coal"]);
    }
    // MH's coal cell should be flagged missing.
    const mh = VM.rows.find(r => r.id === "MH")!;
    const mhCoal = mh.cells.find(c => c.group_id === "coal")!;
    expect(mhCoal.is_missing).toBe(true);
    expect(mhCoal.value).toBeNull();
  });

  it("pinned row sorts first under pinned_then_value", () => {
    expect(VM.rows[0].id).toBe("KA");
    expect(VM.rows[0].is_pinned).toBe(true);
  });

  it("global max ≥ largest single cell value (Gujarat solar 10300)", () => {
    expect(VM.max_cell_value).toBeGreaterThanOrEqual(10300);
  });

  it("legendColour picks the first non-null colour for a group", () => {
    expect(legendColour("solar", VM)).toBe("#facc15");
    expect(legendColour("wind", VM)).toBe("#22c55e");
    expect(legendColour("coal", VM)).toBe("#475569");
  });

  it("legendColour falls back to slate-400 for unknown group", () => {
    expect(legendColour("unknown_group_id", VM)).toBe("rgb(148 163 184)");
  });

  it("legendColour falls back when no cells carry colour", () => {
    const colourless = buildHorizontalGroupedBarViewModel({
      rows: [
        {
          id: "A",
          label: "A",
          pinned_rank: null,
          x: 1,
          y: 2,
        },
      ],
      toRow: (r: { id: string; label: string; pinned_rank: number | null; x: number; y: number }) => ({
        id: r.id,
        label: r.label,
        pinned_rank: r.pinned_rank,
        cells: [
          { group_id: "x", group_label: "x", value: r.x }, // no colour
          { group_id: "y", group_label: "y", value: r.y },
        ],
      }),
      policy: "alphabetical",
    });
    expect(legendColour("x", colourless)).toBe("rgb(148 163 184)");
  });
});
