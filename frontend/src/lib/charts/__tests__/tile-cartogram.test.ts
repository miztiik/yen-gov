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
  stateCodeFromUnitId,
  withStateCodes,
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
    source_id: "boundaries/electoral/delim=2024/ac/all.topojson",
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
    // Row 5: the hex tooltip is now the shared hover card (byte-identical to
    // the PC / AC map card) - grain chip + party short + 3-band margin value.
    expect(r1.tooltip_html).toContain('class="yen-tip"');
    expect(r1.tooltip_html).toContain(">AC</span>"); // [AC] grain chip
    expect(r1.tooltip_html).toContain(">INC</span>"); // winning party short
    expect(r1.tooltip_html).toContain("+25.0%"); // signed 3-band margin value
    expect(r1.tooltip_html).not.toContain("Winner:");
    expect(r1.tooltip_html).not.toContain("Margin:");
  });

  it("renders an unmatched tile as the neutral pending card", () => {
    const rows = buildTileRows(acTiles, [winners[0]]); // only AC-1 has a winner
    const r2 = rows.find((r) => r.unit_id === "IN-S13-AC-2008-2")!;
    expect(r2.pending).toBe(true);
    expect(r2.fill).toBe("#e2e8f0");
    // Pending -> the shared card: grain chip + affordance, but no margin value.
    expect(r2.tooltip_html).toContain('class="yen-tip"');
    expect(r2.tooltip_html).toContain(">AC</span>");
    expect(r2.tooltip_html).toContain("Click to view");
    expect(r2.tooltip_html).not.toMatch(/\+\d/); // no margin value when pending
    expect(r2.tooltip_html).not.toContain("Results pending");
  });

  it("renders the parent-state line when a stateNameForCode resolver is given", () => {
    const rows = buildTileRows(acTiles, winners, {
      stateNameForCode: (code) => (code === "S13" ? "Maharashtra" : null),
    });
    const r1 = rows.find((r) => r.unit_id === "IN-S13-AC-2008-1")!;
    expect(r1.tooltip_html).toContain("Maharashtra"); // parent-state row (R-A row 1)
  });

  it("omits the parent-state line when no resolver is given (back-compat)", () => {
    const rows = buildTileRows(acTiles, winners);
    const r1 = rows.find((r) => r.unit_id === "IN-S13-AC-2008-1")!;
    expect(r1.tooltip_html).not.toContain("Maharashtra");
  });

  it("emits the shared card with no legacy Winner:/Margin: text", () => {
    const rows = buildTileRows(acTiles, winners);
    for (const r of rows) {
      expect(r.tooltip_html).toContain('class="yen-tip"');
      expect(r.tooltip_html).not.toContain("Winner:");
      expect(r.tooltip_html).not.toContain("Margin:");
      expect(r.tooltip_html).not.toContain("Results pending");
    }
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
    expect(rows[0].tooltip_html).toContain(">PC</span>"); // grain chip derived from layout_kind
  });
});

describe("stateCodeFromUnitId", () => {
  it("parses the state segment from an AC unit_id", () => {
    expect(stateCodeFromUnitId("IN-S13-AC-2008-1")).toBe("S13");
    expect(stateCodeFromUnitId("IN-U05-AC-2008-3")).toBe("U05");
  });

  it("parses the state segment from a PC unit_id (different position)", () => {
    expect(stateCodeFromUnitId("IN-PC-2008-S13-1")).toBe("S13");
    expect(stateCodeFromUnitId("IN-PC-2008-S01-25")).toBe("S01");
  });

  it("returns null when no state segment is present", () => {
    expect(stateCodeFromUnitId("synthetic-tile-7")).toBeNull();
    expect(stateCodeFromUnitId("")).toBeNull();
  });
});

describe("withStateCodes (US-style in-hex 2-letter label)", () => {
  const iso = (eci: string): string | null =>
    ({ S13: "IN-MH", S01: "IN-AP", S22: "IN-TN" })[eci] ?? null;

  function pcTile(state: string, eci: number, q: number): TileLayoutRow {
    return tile({
      layout_kind: "pc",
      scope: "national",
      unit_id: `IN-PC-2008-${state}-${eci}`,
      eci_no: eci,
      q,
      r: 0,
      label: `${state}-${eci}`,
      source_id: "boundaries/electoral/delim=2024/pc/all.geojson",
    });
  }

  it("stamps each tile's 2-letter state code when the board spans >1 state", () => {
    const rows = buildTileRows(
      [pcTile("S13", 1, 0), pcTile("S01", 1, 1), pcTile("S22", 1, 2)],
      [],
    );
    const coded = withStateCodes(rows, iso);
    expect(coded.map((r) => r.code)).toEqual(["MH", "AP", "TN"]);
  });

  it("omits codes on a single-state board (every tile would read the same)", () => {
    const rows = buildTileRows(
      selectLayout(doc, { layout_kind: "ac", scope: "S13", delim_year: 2008 }),
      [],
    );
    const coded = withStateCodes(rows, iso);
    expect(coded.every((r) => r.code == null)).toBe(true);
  });

  it("leaves a tile label-free when its state code does not resolve", () => {
    const rows = buildTileRows([pcTile("S13", 1, 0), pcTile("S99", 1, 1)], []);
    const coded = withStateCodes(rows, iso);
    expect(coded.find((r) => r.unit_id.includes("S13"))!.code).toBe("MH");
    expect(coded.find((r) => r.unit_id.includes("S99"))!.code).toBeNull();
  });

  it("does not mutate the input rows", () => {
    const rows = buildTileRows([pcTile("S13", 1, 0), pcTile("S01", 1, 1)], []);
    withStateCodes(rows, iso);
    expect(rows.every((r) => r.code === undefined)).toBe(true);
  });
});
