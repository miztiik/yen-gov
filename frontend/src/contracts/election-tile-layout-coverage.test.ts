// election-tile-layout-coverage contract test (UK-style elections plan, PR-B1).
//
// Invariant: the persisted tile-cartogram layout at
// `datasets/grapher/election_tile_layouts.json` MUST carry exactly one tile per
// real constituency for every shipped (layout_kind, scope, delim_year), and no
// two tiles in a layout may share a hex cell (q, r). The cartogram and the
// boundary corpus are two halves of the same contract: a missing tile drops a
// seat from the equal-area view; a duplicate cell overlaps two seats.
//
// Source-of-truth (read whichever exists, per the plan): both layouts are
// geometry-derived, so coverage is asserted against the boundary geojson —
//   - S13 AC layout  -> `datasets/boundaries/in/ac/state=in_s13/all.geojson`
//     real ACs (ac_no in 1..288, deduped; ac_no=0 junk excluded). This set is
//     1:1 with dim_acs S13 delim-2008 (eci_no 1..288).
//   - national PC layout -> `datasets/boundaries/in/pc/delim=2024/all.geojson`
//     all 545 features (the full geographic seat universe; results light up the
//     contested subset later).

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const layoutPath = resolve(repoRoot, "datasets", "grapher", "election_tile_layouts.json");
const acBndPath = resolve(repoRoot, "datasets", "boundaries", "in", "ac", "state=in_s13", "all.geojson");
const pcBndPath = resolve(repoRoot, "datasets", "boundaries", "in", "pc", "delim=2024", "all.geojson");

interface Tile {
  layout_kind: "ac" | "pc";
  scope: string;
  delim_year: number;
  unit_id: string;
  eci_no: number;
  q: number;
  r: number;
}

function loadTiles(): Tile[] {
  const doc = JSON.parse(readFileSync(layoutPath, "utf-8"));
  return doc.tiles as Tile[];
}

function loadGeojson(p: string): { features: { properties: Record<string, unknown> }[] } {
  return JSON.parse(readFileSync(p, "utf-8"));
}

// Expected canonical unit_ids for the S13 AC layout from the boundary corpus.
function expectedAcUnitIds(): Set<string> {
  const gj = loadGeojson(acBndPath);
  const acNos = new Set<number>();
  for (const f of gj.features) {
    const acNo = Number(f.properties.ac_no);
    if (Number.isFinite(acNo) && acNo > 0) acNos.add(acNo);
  }
  return new Set([...acNos].map((n) => `IN-S13-AC-2008-${n}`));
}

// Expected canonical unit_ids for the national PC layout from the boundary corpus.
function expectedPcUnitIds(): Set<string> {
  const gj = loadGeojson(pcBndPath);
  const ids = new Set<string>();
  for (const f of gj.features) {
    const sc = String(f.properties.state_ut_code);
    const ls = Number(f.properties.ls_seat_code);
    ids.add(`IN-PC-2008-${sc}-${ls}`);
  }
  return ids;
}

function tilesFor(tiles: Tile[], kind: "ac" | "pc", scope: string, delim: number): Tile[] {
  return tiles.filter((t) => t.layout_kind === kind && t.scope === scope && t.delim_year === delim);
}

describe("election tile-layout coverage", () => {
  const tiles = loadTiles();

  it("layout file exists and is non-empty", () => {
    expect(existsSync(layoutPath)).toBe(true);
    expect(tiles.length).toBeGreaterThan(0);
  });

  describe("S13 AC layout (assembly, delim 2008)", () => {
    const acTiles = tilesFor(tiles, "ac", "S13", 2008);
    const expected = expectedAcUnitIds();

    it("ships 288 tiles", () => {
      expect(acTiles.length).toBe(288);
      expect(expected.size).toBe(288);
    });

    it("has exactly one tile per real AC (no missing, no extra)", () => {
      const got = new Set(acTiles.map((t) => t.unit_id));
      const missing = [...expected].filter((id) => !got.has(id));
      const extra = [...got].filter((id) => !expected.has(id));
      expect(missing).toEqual([]);
      expect(extra).toEqual([]);
    });

    it("has no duplicate unit_id", () => {
      const ids = acTiles.map((t) => t.unit_id);
      expect(new Set(ids).size).toBe(ids.length);
    });

    it("has no two tiles sharing a hex cell (q,r)", () => {
      const cells = acTiles.map((t) => `${t.q},${t.r}`);
      expect(new Set(cells).size).toBe(cells.length);
    });
  });

  describe("national PC layout (parliamentary, delim 2008)", () => {
    const pcTiles = tilesFor(tiles, "pc", "national", 2008);
    const expected = expectedPcUnitIds();

    it("ships one tile per PC boundary feature (545)", () => {
      expect(pcTiles.length).toBe(545);
      expect(expected.size).toBe(545);
    });

    it("has exactly one tile per boundary PC (no missing, no extra)", () => {
      const got = new Set(pcTiles.map((t) => t.unit_id));
      const missing = [...expected].filter((id) => !got.has(id));
      const extra = [...got].filter((id) => !expected.has(id));
      expect(missing).toEqual([]);
      expect(extra).toEqual([]);
    });

    it("has no duplicate unit_id", () => {
      const ids = pcTiles.map((t) => t.unit_id);
      expect(new Set(ids).size).toBe(ids.length);
    });

    it("has no two tiles sharing a hex cell (q,r)", () => {
      const cells = pcTiles.map((t) => `${t.q},${t.r}`);
      expect(new Set(cells).size).toBe(cells.length);
    });
  });
});
