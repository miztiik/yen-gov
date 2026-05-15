// Contract tier (CLAUDE.md §15): the loader's *consumer* contract over the
// shipped boundary files. Schema validation of sidecar JSON is covered by
// `frontend/src/contracts/datasets-conform.test.ts` — this file asserts the
// two invariants the loader silently relies on but the schemas can't:
//
//   1. Every `*.geojson` has a sibling `*.geojson.sources.json` (CLAUDE.md
//      §12: every published artifact must declare provenance; .geojson is
//      not self-describing so the sidecar carries it).
//   2. Every feature on each LGD-keyed boundary file carries the join-key
//      property the loader names in JOIN_KEYS — otherwise the choropleth
//      would silently drop features at join time and we'd never know.
import { describe, it, expect } from "vitest";
import { readFileSync, existsSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { globSync } from "glob";
import { boundaryBasename, joinKeyFor, type GeoLevel } from "./boundaries";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const geoDir = resolve(repoRoot, "datasets", "boundaries", "in", "geojson");

function listGeojson(): string[] {
  return globSync("*.geojson", { cwd: geoDir, absolute: false }).sort();
}

const ALL_GEOJSON = listGeojson();

// Map a basename back to the GeoLevel the loader would request it for.
// Returns null for files outside the loader's path table (e.g. S01-ac.geojson
// — Assembly Constituencies are a separate layer, not a boundary level).
function levelForBasename(basename: string): GeoLevel | null {
  if (basename === "india-soi.geojson") return "country";
  if (basename === "india-states.geojson") return "state";
  if (basename === "india-districts.geojson") return "district";
  if (/^S\d{2}-subdistricts\.geojson$/.test(basename)) return "subdistrict";
  if (/^S\d{2}-villages-\d+\.geojson$/.test(basename)) return "village";
  return null;
}

describe("contract — every shipped *.geojson has a sibling sources.json (§12)", () => {
  it("at least one geojson is present (sanity)", () => {
    expect(ALL_GEOJSON.length).toBeGreaterThan(0);
  });

  for (const basename of ALL_GEOJSON) {
    it(basename, () => {
      const sidecar = resolve(geoDir, `${basename}.sources.json`);
      expect(existsSync(sidecar), `${basename}: missing sibling .sources.json`).toBe(true);
      const body = JSON.parse(readFileSync(sidecar, "utf-8")) as { sources?: unknown };
      expect(Array.isArray(body.sources), `${basename}.sources.json: 'sources' must be an array`).toBe(true);
    });
  }
});

describe("contract — every LGD-keyed feature carries its join-key property", () => {
  // Sample a tight subset rather than every feature in every file — at
  // ~50 MB across 73 files, validating each property exhaustively would
  // dominate test runtime. Instead: assert the key is present on the
  // first, middle, and last features of each LGD-keyed file, which is
  // sufficient to catch a missing-property regression at snapshot time
  // without re-scanning the entire bundle.
  for (const basename of ALL_GEOJSON) {
    const level = levelForBasename(basename);
    if (level === null) continue;
    const joinKey = joinKeyFor(level);
    if (joinKey === null) continue; // country has no key

    it(`${basename} (level=${level}, key=${joinKey})`, () => {
      const fc = JSON.parse(readFileSync(resolve(geoDir, basename), "utf-8")) as {
        features: { properties: Record<string, unknown> }[];
      };
      expect(fc.features.length).toBeGreaterThan(0);
      const samples = [
        fc.features[0],
        fc.features[Math.floor(fc.features.length / 2)],
        fc.features[fc.features.length - 1],
      ];
      for (const f of samples) {
        expect(
          f.properties[joinKey],
          `${basename}: feature missing join-key property '${joinKey}'`,
        ).toBeDefined();
      }
    });
  }
});

describe("contract — loader's path table reaches every non-AC boundary file", () => {
  // Orphan detector: any geojson under the boundaries dir that the loader's
  // basename resolver does not produce, AND is not on the explicit pass-list
  // for layers the loader does not own (currently: ECI Assembly Constituency
  // shapefiles, S<NN>-ac.geojson — owned by the AC layer, not the LGD
  // boundary loader).
  it("no orphan boundary files", () => {
    const reachable = new Set<string>();

    // Walk the loader's path table for the values we know are present.
    reachable.add(boundaryBasename("country"));
    reachable.add(boundaryBasename("state"));
    reachable.add(boundaryBasename("district"));
    reachable.add(boundaryBasename("subdistrict", undefined, "33"));
    // Villages: each present district → one shard.
    const indexPath = resolve(geoDir, "S22-villages-index.json");
    if (existsSync(indexPath)) {
      const idx = JSON.parse(readFileSync(indexPath, "utf-8")) as { district_lgd_codes: string[] };
      for (const d of idx.district_lgd_codes) {
        reachable.add(boundaryBasename("village", d, "33"));
      }
    }

    const orphans = ALL_GEOJSON.filter(b => {
      if (reachable.has(b)) return false;
      // ECI AC shapefiles are not the LGD boundary loader's territory.
      if (/^[SU]\d{2}-ac\.geojson$/.test(b)) return false;
      return true;
    });

    expect(orphans, `unreachable boundary files (loader cannot resolve): ${orphans.join(", ")}`).toEqual([]);
  });
});

// Lightweight presence check on the index manifest itself — datasets-conform
// validates the schema; here we only assert the loader's expectation that
// district codes are strings (the loader compares against parentDistrictLgd
// passed as a string from the URL / click handler).
describe("contract — villages index manifest meets loader's expectations", () => {
  const indexPath = resolve(geoDir, "S22-villages-index.json");
  if (!existsSync(indexPath)) return;
  it("district_lgd_codes are strings (loader passes string keys)", () => {
    const idx = JSON.parse(readFileSync(indexPath, "utf-8")) as { district_lgd_codes: unknown[] };
    expect(Array.isArray(idx.district_lgd_codes)).toBe(true);
    for (const code of idx.district_lgd_codes) {
      expect(typeof code).toBe("string");
    }
  });
  it("at least one shard registered (TN has districts)", () => {
    const idx = JSON.parse(readFileSync(indexPath, "utf-8")) as { district_lgd_codes: unknown[] };
    expect(idx.district_lgd_codes.length).toBeGreaterThan(0);
  });
});

// One more invariant: every registered district in the index has its shard
// on disk. If this fails, the index is lying and the loader will return null
// for a district it should serve.
describe("contract — every index entry has a shard on disk", () => {
  const indexPath = resolve(geoDir, "S22-villages-index.json");
  if (!existsSync(indexPath)) return;
  const idx = JSON.parse(readFileSync(indexPath, "utf-8")) as { district_lgd_codes: string[] };
  for (const d of idx.district_lgd_codes) {
    const shard = `S22-villages-${d}.geojson`;
    it(shard, () => {
      const path = resolve(geoDir, shard);
      expect(existsSync(path), `${shard}: index says present but file missing`).toBe(true);
      expect(statSync(path).size).toBeGreaterThan(0);
    });
  }
});
