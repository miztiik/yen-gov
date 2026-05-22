// Contract tier (CLAUDE.md §15): the loader's *consumer* contract over the
// shipped boundary files. Post-T.0d (ADR-0031 Amendment 2026-05-22) the
// per-shard sidecar files are gone — provenance now lives once in
// `datasets/boundaries/boundary_layers.parquet` (FK to
// `datasets/taxonomy/sources.parquet`), and the per-state villages-index
// manifest was retired in favour of the parquet ledger. The two consumer
// invariants left for this tier:
//
//   1. Every shard the loader can resolve via `boundaryRelPath` exists on
//      disk under the Hive tree.
//   2. Every feature on each LGD-keyed shard carries the join-key property
//      the loader names in JOIN_KEYS — otherwise the choropleth would
//      silently drop features at join time and we'd never know.
//
// Orphan/inventory checks (every disk file is reachable from a contract
// path) now live in `frontend/src/contracts/boundaries-conform.test.ts`,
// alongside the rest of the dataset-shape contracts.
import { describe, it, expect } from "vitest";
import { readFileSync, existsSync, statSync } from "node:fs";
import { resolve, sep, posix } from "node:path";
import { fileURLToPath } from "node:url";
import { globSync } from "glob";
import { boundaryRelPath, joinKeyFor, type GeoLevel } from "./boundaries";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const boundariesRoot = resolve(repoRoot, "datasets", "boundaries", "in");

// Glob the Hive tree; normalize to POSIX separators on Windows.
const ALL_SHARDS = globSync("**/all.geojson", { cwd: boundariesRoot, absolute: false })
  .map(p => p.split(sep).join(posix.sep))
  .sort();

// Recover (level, district_lgd) from a Hive relative path. Returns null
// when the path is outside the loader's level taxonomy.
function levelForRelPath(relPath: string): { level: GeoLevel; districtLgd?: string } | null {
  if (relPath === "country/all.geojson") return { level: "country" };
  if (relPath === "states/all.geojson") return { level: "state" };
  if (relPath === "districts/all.geojson") return { level: "district" };
  const m1 = relPath.match(/^subdistricts\/state=in_[a-z0-9]+\/all\.geojson$/);
  if (m1) return { level: "subdistrict" };
  const m2 = relPath.match(/^villages\/state=in_[a-z0-9]+\/district=(\d+)\/all\.geojson$/);
  if (m2) return { level: "village", districtLgd: m2[1] };
  return null;
}

describe("contract — every classified shard carries the join-key on sample features", () => {
  // Sample a tight subset rather than every feature in every shard — at
  // ~50 MB across ~73 shards, validating each property exhaustively would
  // dominate test runtime. Assert the key is present on the first, middle,
  // and last features of each LGD-keyed shard, which catches a
  // missing-property regression at snapshot time.
  for (const relPath of ALL_SHARDS) {
    const info = levelForRelPath(relPath);
    if (!info) continue;
    const joinKey = joinKeyFor(info.level);
    if (joinKey === null) continue; // country has no key

    it(`${relPath} (level=${info.level}, key=${joinKey})`, () => {
      const path = resolve(boundariesRoot, relPath);
      expect(existsSync(path)).toBe(true);
      expect(statSync(path).size).toBeGreaterThan(0);
      const fc = JSON.parse(readFileSync(path, "utf-8")) as {
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
          `${relPath}: feature missing join-key property '${joinKey}'`,
        ).toBeDefined();
      }
    });
  }
});

describe("contract — boundaryRelPath round-trips against on-disk shards", () => {
  it("country resolves to an existing shard", () => {
    const path = resolve(boundariesRoot, boundaryRelPath("country"));
    expect(existsSync(path)).toBe(true);
  });

  it("state resolves to an existing shard", () => {
    const path = resolve(boundariesRoot, boundaryRelPath("state"));
    expect(existsSync(path)).toBe(true);
  });

  it("district resolves to an existing shard", () => {
    const path = resolve(boundariesRoot, boundaryRelPath("district"));
    expect(existsSync(path)).toBe(true);
  });

  it("subdistrict for TN resolves to an existing shard", () => {
    const path = resolve(boundariesRoot, boundaryRelPath("subdistrict", undefined, "33"));
    expect(existsSync(path)).toBe(true);
  });

  it("every TN village shard on disk is reachable via boundaryRelPath", () => {
    // Walk every villages/state=in_s22/district=N/all.geojson present on
    // disk and confirm the loader's path resolver lands on the same file.
    const tnVillages = ALL_SHARDS.filter(p => p.startsWith("villages/state=in_s22/"));
    expect(tnVillages.length).toBeGreaterThan(0);
    for (const relPath of tnVillages) {
      const info = levelForRelPath(relPath);
      expect(info?.level).toBe("village");
      const resolved = boundaryRelPath("village", info!.districtLgd!, "33");
      expect(resolved).toBe(relPath);
    }
  });
});
