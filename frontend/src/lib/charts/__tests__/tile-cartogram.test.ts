// TileCartogram / election-tile-layout view-model tests (PR-B2).
//
// vitest runs node-env (no jsdom) so these exercise the grain-agnostic
// join logic in `view-models/election-tile-layout.ts` — the contract the
// presentational <TileCartogram> renders. DOM/interaction parity is covered
// by the Playwright @elections spec (PR-B3).

import { describe, it, expect } from "vitest";
import {
  selectLayout,
  buildTileRows,
  type ElectionTileLayoutDoc,
  type TileLayoutRow,
  type TileWinnerInput,
} from "../../view-models/election-tile-layout";

function tile(over: Partial<TileLayoutRow>): TileLayoutRow {
  return {
    layout_kind: "ac",
    scope: "S13",
    delim_year: 2008,
    unit_id: "IN-S13-AC-2008-1",
    eci_no: 1,
    q: 0,
    r: 0,
    label: "Akkalkuwa",
    source_id: "boundaries/electoral/delim=2008/ac/state=maharashtra/all.geojson",
    derivation_method: "centroid-hexbin",
    ...over,
  };
}

const doc: ElectionTileLayoutDoc = {
  $schema: "x",
  $schema_version: "1.0",
  tiles: [
    tile({ unit_id: "IN-S13-AC-2008-1", eci_no: 1, q: 0, r: 0, label: "Akkalkuwa" }),
    tile({ unit_id: "IN-S13-AC-2008-2", eci_no: 2, q: 1, r: 0, label: "Shahada" }),
    tile({
      layout_kind: "pc",
      scope: "national",
      unit_id: "IN-PC-2008-S13-1",
      eci_no: 1,
      q: 5,
      r: 5,
      label: "Nandurbar",
      source_id: "boundaries/electoral/delim=2024/pc/all.geojson",
    }),
  ],
};

describe("selectLayout", () => {
  it("filters by layout_kind, scope and delim_year", () => {
    const ac = selectLayout(doc, { layout_kind: "ac", scope: "S13", delim_year: 2008 });
    expect(ac.map((t) => t.unit_id)).toEqual(["IN-S13-AC-2008-1", "IN-S13-AC-2008-2"]);
    const pc = selectLayout(doc, { layout_kind: "pc", scope: "national", delim_year: 2008 });
    expect(pc.map((t) => t.unit_id)).toEqual(["IN-PC-2008-S13-1"]);
  });

  it("returns empty when nothing matches", () => {
    expect(selectLayout(doc, { layout_kind: "ac", scope: "S99", delim_year: 2008 })).toEqual([]);
  });
});

describe("buildTileRows", () => {
  const acTiles = selectLayout(doc, { layout_kind: "ac", scope: "S13", delim_year: 2008 });

  const winners: TileWinnerInput[] = [
    { unit_id: "IN-S13-AC-2008-1", party_key: "INC", party_short: "INC", margin_pct: 25 },
    { unit_id: "IN-S13-AC-2008-2", party_key: "BJP", party_short: "BJP", margin_pct: 4 },
  ];

  it("produces exactly one row per tile (one tile = one unit)", () => {
    const rows = buildTileRows(acTiles, winners);
    expect(rows).toHaveLength(acTiles.length);
    expect(new Set(rows.map((r) => r.unit_id)).size).toBe(rows.length);
  });

  it("joins each winner onto its tile by unit_id with a valid colour", () => {
    const rows = buildTileRows(acTiles, winners);
    const r1 = rows.find((r) => r.unit_id === "IN-S13-AC-2008-1")!;
    expect(r1.pending).toBe(false);
    expect(r1.fill).toMatch(/^#[0-9a-f]{6}$/i);
    expect(r1.tooltip_html).toContain("Winner: INC");
    expect(r1.tooltip_html).toContain("25.0%");
  });

  it("renders an unmatched tile in the neutral pending style", () => {
    const rows = buildTileRows(acTiles, [winners[0]]); // only AC-1 has a winner
    const r2 = rows.find((r) => r.unit_id === "IN-S13-AC-2008-2")!;
    expect(r2.pending).toBe(true);
    expect(r2.fill).toBe("#e2e8f0");
    expect(r2.tooltip_html).toContain("Results pending");
  });

  it("maps larger margins to higher opacity", () => {
    const rows = buildTileRows(acTiles, winners);
    const big = rows.find((r) => r.unit_id === "IN-S13-AC-2008-1")!; // 25%
    const small = rows.find((r) => r.unit_id === "IN-S13-AC-2008-2")!; // 4%
    expect(big.opacity).toBeGreaterThan(small.opacity);
  });

  it("marks exactly the selected unit as selected", () => {
    const rows = buildTileRows(acTiles, winners, { selected_unit_id: "IN-S13-AC-2008-2" });
    const selected = rows.filter((r) => r.selected);
    expect(selected.map((r) => r.unit_id)).toEqual(["IN-S13-AC-2008-2"]);
  });

  it("works grain-agnostically for PC tiles too", () => {
    const pcTiles = selectLayout(doc, { layout_kind: "pc", scope: "national", delim_year: 2008 });
    const rows = buildTileRows(pcTiles, [
      { unit_id: "IN-PC-2008-S13-1", party_key: "BJP", party_short: "BJP", margin_pct: 10 },
    ]);
    expect(rows).toHaveLength(1);
    expect(rows[0].unit_id).toBe("IN-PC-2008-S13-1");
    expect(rows[0].pending).toBe(false);
  });
});
