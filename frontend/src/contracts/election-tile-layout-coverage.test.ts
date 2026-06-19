// election-tile-layout-coverage contract test (UK-style elections plan PR-B1;
// generalised in the gap-closure plan EGC-C2).
//
// Two tiers guard the persisted tile-cartogram at
// `datasets/grapher/election_tile_layouts.json`:
//
//   Tier-1 (always-on, every shipped scope): for EVERY (layout_kind, scope,
//     delim_year) present in the layout, no two tiles share a hex cell (q,r)
//     and no unit_id repeats. A missing tile drops a seat from the equal-area
//     view; a duplicate cell overlaps two seats.
//
//   Tier-2 (ship-dark coverage ledger): every state/UT with an elected
//     assembly and a standard `ac_no` boundary corpus MUST ship exactly one AC
//     layout whose tile set equals the boundary's constituency set. The
//     COVERED_AC_SCOPES allowlist IS the progress ledger — a scope only enters
//     once its layout lands. When the last holdout (J&K, non-standard boundary
//     schema) lands, delete the allowlist and assert REQUIRED_AC_SCOPES
//     unconditionally.

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { feature as topojsonFeature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";
import type { FeatureCollection } from "geojson";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const layoutPath = resolve(repoRoot, "datasets", "grapher", "election_tile_layouts.json");
// Row 3 (2026-06-16 map-geometry rip): the 31 per-state delim=2008 AC geojson
// shards were consolidated into ONE national TopoJSON (object `ac`, each
// feature stamped `state_ut_code`); AC coverage is now checked by decoding it
// + grouping by `state_ut_code` instead of reading per-state shards. PC is
// unchanged (the single delim=2024 geojson corpus).
const acTopojsonPath = resolve(
  repoRoot,
  "datasets",
  "boundaries",
  "electoral",
  "delim=2024",
  "ac",
  "all.topojson",
);
const pcBndPath = resolve(repoRoot, "datasets", "boundaries", "electoral", "delim=2024", "pc", "all.geojson");

// The delimitation ERA baked into every unit_id (IN-<code>-AC-2008-<n>,
// IN-PC-2008-<sc>-<ls>). It is NOT the geometry vintage - the 2024 snapshot
// carries the 2008-delimitation seats for LS 2009-2019 + AE contests.
const DELIM_YEAR = 2008;

// Per-state PC equal-seats layouts are only authored for states with at
// least this many seats (mirrors MIN_PCS_FOR_STATE_LAYOUT in
// tools/gen_election_tile_layouts.py). Smaller states stay geo-only.
const MIN_PCS_FOR_STATE_LAYOUT = 4;

// Boundary partition slug -> ECI state/UT code (mirrors the generator's
// SLUG_TO_CODE in tools/gen_election_tile_layouts.py).
const SLUG_TO_CODE: Record<string, string> = {
  "andhra-pradesh": "S01",
  "arunachal-pradesh": "S02",
  assam: "S03",
  bihar: "S04",
  goa: "S05",
  gujarat: "S06",
  haryana: "S07",
  "himachal-pradesh": "S08",
  karnataka: "S10",
  kerala: "S11",
  "madhya-pradesh": "S12",
  maharashtra: "S13",
  manipur: "S14",
  meghalaya: "S15",
  mizoram: "S16",
  nagaland: "S17",
  odisha: "S18",
  punjab: "S19",
  rajasthan: "S20",
  sikkim: "S21",
  "tamil-nadu": "S22",
  tripura: "S23",
  "uttar-pradesh": "S24",
  "west-bengal": "S25",
  chhattisgarh: "S26",
  jharkhand: "S27",
  uttarakhand: "S28",
  telangana: "S29",
  delhi: "U05",
  puducherry: "U07",
  "jammu-and-kashmir": "U08",
};

// State partitions whose boundary geojson lacks the standard `ac_no` property.
// These cannot yet be covered by the centroid-hexbin generator.
const NON_STANDARD_AC_SLUGS = new Set(["jammu-and-kashmir"]);

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
  return JSON.parse(readFileSync(layoutPath, "utf-8")).tiles as Tile[];
}

function loadGeojson(p: string): { features: { properties: Record<string, unknown> }[] } {
  return JSON.parse(readFileSync(p, "utf-8"));
}

// Decode the national AC TopoJSON ONCE and group features by the stamped
// `state_ut_code` (ECI code). Mirrors the runtime StateAcMapD3 decode +
// per-state filter so the coverage check runs over the SAME geometry the
// map renders.
function loadAcFeaturesByState(): Map<string, { properties: Record<string, unknown> }[]> {
  const topo = JSON.parse(readFileSync(acTopojsonPath, "utf-8")) as Topology;
  const fc = topojsonFeature(topo, topo.objects.ac as GeometryCollection) as FeatureCollection;
  const byState = new Map<string, { properties: Record<string, unknown> }[]>();
  for (const f of fc.features) {
    const code = String(
      (f.properties as Record<string, unknown> | null)?.state_ut_code ?? "",
    );
    if (!code) continue;
    const bucket = byState.get(code);
    if (bucket) bucket.push(f as { properties: Record<string, unknown> });
    else byState.set(code, [f as { properties: Record<string, unknown> }]);
  }
  return byState;
}
const AC_BY_STATE = loadAcFeaturesByState();

function tilesFor(tiles: Tile[], kind: "ac" | "pc", scope: string, delim: number): Tile[] {
  return tiles.filter((t) => t.layout_kind === kind && t.scope === scope && t.delim_year === delim);
}

// Expected canonical AC unit_ids for one ECI state code.
function expectedAcUnitIds(code: string): Set<string> {
  const feats = AC_BY_STATE.get(code) ?? [];
  const acNos = new Set<number>();
  for (const f of feats) {
    const acNo = Number(f.properties.ac_no);
    if (Number.isFinite(acNo) && acNo > 0) acNos.add(acNo);
  }
  return new Set([...acNos].map((n) => `IN-${code}-AC-${DELIM_YEAR}-${n}`));
}

function expectedPcUnitIds(): Set<string> {
  const gj = loadGeojson(pcBndPath);
  const ids = new Set<string>();
  for (const f of gj.features) {
    const sc = String(f.properties.state_ut_code);
    const ls = Number(f.properties.ls_seat_code);
    ids.add(`IN-PC-${DELIM_YEAR}-${sc}-${ls}`);
  }
  return ids;
}

// Group the boundary PC seats by their stamped `state_ut_code` (ECI code),
// mirroring the generator's per-state filter so the per-state PC coverage
// check runs over the SAME geometry the per-state cartograms are built from.
function expectedPcUnitIdsByState(): Map<string, Set<string>> {
  const gj = loadGeojson(pcBndPath);
  const byState = new Map<string, Set<string>>();
  for (const f of gj.features) {
    const sc = String(f.properties.state_ut_code);
    const ls = Number(f.properties.ls_seat_code);
    const set = byState.get(sc) ?? new Set<string>();
    set.add(`IN-PC-${DELIM_YEAR}-${sc}-${ls}`);
    byState.set(sc, set);
  }
  return byState;
}

// Every state with a standard `ac_no` corpus in the national AC topojson =
// the elected-assembly AC scopes the cartogram is REQUIRED to cover. J&K
// (non-standard seat_id schema) is excluded via NON_STANDARD_AC_SLUGS; any
// other state lacking ac_no is auto-excluded by the ac_no>0 probe.
const REQUIRED_AC_SCOPES: { slug: string; code: string }[] = Object.entries(SLUG_TO_CODE)
  .filter(([slug]) => !NON_STANDARD_AC_SLUGS.has(slug))
  .filter(([, code]) =>
    (AC_BY_STATE.get(code) ?? []).some((f) => {
      const n = Number(f.properties.ac_no);
      return Number.isFinite(n) && n > 0;
    }),
  )
  .map(([slug, code]) => ({ slug, code }))
  .sort((a, b) => a.code.localeCompare(b.code));

// Ship-dark ledger: scopes whose layout has landed. Every standard-schema AC
// scope is now covered; J&K (non-standard schema) is the lone uncovered scope
// and is excluded from REQUIRED_AC_SCOPES above. When J&K lands, drop this
// allowlist and assert REQUIRED_AC_SCOPES directly.
const COVERED_AC_SCOPES = new Set<string>(REQUIRED_AC_SCOPES.map((s) => s.code));

describe("election tile-layout coverage", () => {
  const tiles = loadTiles();

  it("layout file exists and is non-empty", () => {
    expect(existsSync(layoutPath)).toBe(true);
    expect(tiles.length).toBeGreaterThan(0);
  });

  // ---- Tier-1: structural invariants on every shipped scope ----------------
  describe("Tier-1: per-scope structural invariants", () => {
    const scopeKeys = [...new Set(tiles.map((t) => `${t.layout_kind}|${t.scope}|${t.delim_year}`))].sort();

    it.each(scopeKeys)("%s has no duplicate unit_id and no shared hex cell", (key) => {
      const [kind, scope, delim] = key.split("|");
      const group = tilesFor(tiles, kind as "ac" | "pc", scope, Number(delim));
      const ids = group.map((t) => t.unit_id);
      expect(new Set(ids).size).toBe(ids.length);
      const cells = group.map((t) => `${t.q},${t.r}`);
      expect(new Set(cells).size).toBe(cells.length);
    });
  });

  // ---- Tier-2: ship-dark coverage ledger -----------------------------------
  describe("Tier-2: required AC scope coverage (ship-dark)", () => {
    for (const { slug, code } of REQUIRED_AC_SCOPES) {
      const covered = COVERED_AC_SCOPES.has(code);
      const label = `${code} (${slug})${covered ? "" : " [ship-dark: not yet covered]"}`;
      it(label, () => {
        if (!covered) return; // ledger holdout — skip until its layout lands
        const got = new Set(tilesFor(tiles, "ac", code, DELIM_YEAR).map((t) => t.unit_id));
        const expected = expectedAcUnitIds(code);
        expect(got.size).toBeGreaterThan(0);
        const missing = [...expected].filter((id) => !got.has(id));
        const extra = [...got].filter((id) => !expected.has(id));
        expect(missing).toEqual([]);
        expect(extra).toEqual([]);
      });
    }

    it("allowlist never claims an uncovered scope", () => {
      const requiredCodes = new Set(REQUIRED_AC_SCOPES.map((s) => s.code));
      for (const code of COVERED_AC_SCOPES) {
        expect(requiredCodes.has(code)).toBe(true);
      }
    });
  });

  // ---- Tier-2 PC: per-state PC scope coverage ------------------------------
  // Per-state PC equal-seats layouts (feat/state-pc-equal-seats) cover every
  // state with >= MIN_PCS_FOR_STATE_LAYOUT seats; below that threshold the
  // state PC page stays geographic-only (no pc/<code> scope is emitted, so the
  // equal-seats toggle never appears). Each covered scope's tile set MUST
  // equal that state's boundary PC seat set; each below-threshold state MUST
  // have NO per-state PC layout. The eligibility split is derived from the
  // same boundary corpus the generator reads, so the test tracks the corpus.
  describe("Tier-2: per-state PC scope coverage", () => {
    const byState = expectedPcUnitIdsByState();
    const eligible = [...byState.entries()]
      .filter(([, ids]) => ids.size >= MIN_PCS_FOR_STATE_LAYOUT)
      .map(([code]) => code)
      .sort();
    const ineligible = [...byState.entries()]
      .filter(([, ids]) => ids.size < MIN_PCS_FOR_STATE_LAYOUT)
      .map(([code]) => code)
      .sort();

    it("at least one eligible and one ineligible PC state exist", () => {
      expect(eligible.length).toBeGreaterThan(0);
      expect(ineligible.length).toBeGreaterThan(0);
    });

    it.each(eligible)("pc/%s tile set equals the boundary PC seat set", (code) => {
      const got = new Set(
        tilesFor(tiles, "pc", code, DELIM_YEAR).map((t) => t.unit_id),
      );
      const expected = byState.get(code) ?? new Set<string>();
      expect(got.size).toBeGreaterThanOrEqual(MIN_PCS_FOR_STATE_LAYOUT);
      expect([...expected].filter((id) => !got.has(id))).toEqual([]);
      expect([...got].filter((id) => !expected.has(id))).toEqual([]);
    });

    it.each(ineligible)("pc/%s is geo-only (no per-state PC layout)", (code) => {
      expect(tilesFor(tiles, "pc", code, DELIM_YEAR)).toEqual([]);
    });
  });

  // ---- Count pins (regression guard for the two seed layouts) --------------
  describe("count pins", () => {
    it("S13 AC ships 288 tiles", () => {
      expect(tilesFor(tiles, "ac", "S13", DELIM_YEAR).length).toBe(288);
    });
    it("national PC ships 545 tiles matching the boundary corpus", () => {
      const pcTiles = tilesFor(tiles, "pc", "national", DELIM_YEAR);
      expect(pcTiles.length).toBe(545);
      const got = new Set(pcTiles.map((t) => t.unit_id));
      const expected = expectedPcUnitIds();
      expect([...expected].filter((id) => !got.has(id))).toEqual([]);
      expect([...got].filter((id) => !expected.has(id))).toEqual([]);
    });
    it("per-state PC scopes ship the expected seat counts", () => {
      // Bihar 40, Tamil Nadu 39, Uttar Pradesh 80, Delhi 7, Himachal 4.
      expect(tilesFor(tiles, "pc", "S04", DELIM_YEAR).length).toBe(40);
      expect(tilesFor(tiles, "pc", "S22", DELIM_YEAR).length).toBe(39);
      expect(tilesFor(tiles, "pc", "S24", DELIM_YEAR).length).toBe(80);
      expect(tilesFor(tiles, "pc", "U05", DELIM_YEAR).length).toBe(7);
      expect(tilesFor(tiles, "pc", "S08", DELIM_YEAR).length).toBe(4);
    });
  });
});
