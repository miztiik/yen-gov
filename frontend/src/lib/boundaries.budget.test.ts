// Bundle-budget contract (Fowler v3 nit). Two ratchets:
//
//   1. Per-village-shard byte budget — the whole point of splitting villages
//      per-district was that a single click pulls a small shard. If a future
//      snapshot regression ships a 50 MB shard, this test catches it before
//      a citizen sits through the download.
//   2. Total chunk count ceiling — one shard per TN district, one national
//      silhouette, one states layer, one districts layer, one subdistricts
//      file per state, plus the existing AC layer files. The current count
//      should sit comfortably under 80; if it ever exceeds 80 we want a
//      conscious decision (split policy change, new state coverage), not
//      drift.
//
// Budgets here are a deliberate ceiling — well above today's largest file
// — so the test fails on a *snapshot regression*, not on routine growth.
import { describe, it, expect } from "vitest";
import { readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { globSync } from "glob";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const geoDir = resolve(repoRoot, "datasets", "boundaries", "in", "geojson");

// Per-shard ceiling: today's largest village shard is ~2.8 MB. 4 MB is the
// "this is genuinely large for one click but still tolerable" line. Bigger
// than that almost certainly means a coord_precision or filtering regression.
const VILLAGE_SHARD_MAX_BYTES = 4 * 1024 * 1024;

// Subdistrict per-state file: today's TN file is ~5 MB. 8 MB ceiling.
const SUBDISTRICT_MAX_BYTES = 8 * 1024 * 1024;

// National silhouettes (india-soi, india-states, india-districts) are large
// by nature — single national outlines at acceptable detail. 16 MB ceiling.
const NATIONAL_MAX_BYTES = 16 * 1024 * 1024;

// Total chunk-count ratchet — the loader's path table is finite; runaway
// growth means a split-policy regression.
const MAX_TOTAL_CHUNKS = 80;

const ALL_GEOJSON = globSync("*.geojson", { cwd: geoDir, absolute: false }).sort();

describe("budget — per-file byte ceilings", () => {
  for (const basename of ALL_GEOJSON) {
    const size = statSync(resolve(geoDir, basename)).size;

    if (/^S\d{2}-villages-\d+\.geojson$/.test(basename)) {
      it(`${basename} ≤ ${VILLAGE_SHARD_MAX_BYTES} bytes (got ${size})`, () => {
        expect(size).toBeLessThanOrEqual(VILLAGE_SHARD_MAX_BYTES);
      });
    } else if (/^S\d{2}-subdistricts\.geojson$/.test(basename)) {
      it(`${basename} ≤ ${SUBDISTRICT_MAX_BYTES} bytes (got ${size})`, () => {
        expect(size).toBeLessThanOrEqual(SUBDISTRICT_MAX_BYTES);
      });
    } else if (/^india-/.test(basename)) {
      it(`${basename} ≤ ${NATIONAL_MAX_BYTES} bytes (got ${size})`, () => {
        expect(size).toBeLessThanOrEqual(NATIONAL_MAX_BYTES);
      });
    }
    // ECI AC files are out of scope for this loader's budget.
  }
});

describe("budget — total chunk count ratchet", () => {
  it(`≤ ${MAX_TOTAL_CHUNKS} *.geojson chunks under boundaries/in/geojson/ (got ${ALL_GEOJSON.length})`, () => {
    expect(ALL_GEOJSON.length).toBeLessThanOrEqual(MAX_TOTAL_CHUNKS);
  });
});

describe("budget — index registers exactly the shards on disk", () => {
  // If the index says 38 shards and 39 are on disk, the 39th is dead weight
  // (no loader path reaches it); if the index says 38 and 37 are on disk,
  // the loader will 404 for the missing one.
  const indexPath = resolve(geoDir, "S22-villages-index.json");
  it("S22-villages-index.json count matches on-disk shard count", () => {
    const idx = JSON.parse(readFileSync(indexPath, "utf-8")) as { district_lgd_codes: string[] };
    const shards = ALL_GEOJSON.filter(b => /^S22-villages-\d+\.geojson$/.test(b));
    expect(shards.length).toBe(idx.district_lgd_codes.length);
  });
});
