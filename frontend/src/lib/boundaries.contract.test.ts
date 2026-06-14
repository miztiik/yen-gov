// Contract tier (CLAUDE.md section 15): the loader's consumer contract over
// representative boundary files. Post-T.0d (ADR-0031 Amendment 2026-05-22)
// the per-shard sidecar files are gone; provenance now lives once in
// `datasets/data/entities/boundary_layer.csv` (X1a-fu2-E rip 2026-06-07;
// pre-rip a parquet under datasets/boundaries/; FK to
// `datasets/data/entities/source.csv`), and the per-state villages-index
// manifest was retired in favour of the CSV ledger.
//
//   1. Resolver canaries prove `boundaryRelPath` still emits fetchable Hive
//      paths for each frontend GeoLevel.
//   2. Join-key canaries prove representative LGD-keyed shards carry the
//      property named in JOIN_KEYS; exhaustive shard proof is backend Tier-B.
//
// Default frontend tests must not scale with corpus cardinality. Do not add
// a loop that creates one test per boundary shard here.
import { describe, it, expect } from "vitest";
import { readFileSync, existsSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { boundaryRelPath, joinKeyFor, type GeoLevel } from "./boundaries";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const boundariesRoot = resolve(repoRoot, "datasets", "boundaries", "in");

const JOIN_KEY_CANARIES: { level: GeoLevel; relPath: string; risk: string }[] = [
  { level: "state", relPath: boundaryRelPath("state"), risk: "national state layer" },
  { level: "district", relPath: boundaryRelPath("district"), risk: "national district layer" },
  {
    level: "subdistrict",
    relPath: boundaryRelPath("subdistrict", undefined, "33"),
    risk: "state-partitioned subdistrict layer",
  },
  {
    level: "village",
    relPath: boundaryRelPath("village", "577", "33"),
    risk: "large Tamil Nadu village shard",
  },
];

describe("contract - representative shards carry the join-key on sample features", () => {
  it.each(JOIN_KEY_CANARIES)("$risk ($relPath)", ({ level, relPath }) => {
    const joinKey = joinKeyFor(level);
    expect(joinKey, level).not.toBeNull();
    const path = resolve(boundariesRoot, relPath);
    expect(existsSync(path), relPath).toBe(true);
    expect(statSync(path).size, relPath).toBeGreaterThan(0);
    const fc = JSON.parse(readFileSync(path, "utf-8")) as {
      features: { properties: Record<string, unknown> }[];
    };
    expect(fc.features.length, relPath).toBeGreaterThan(0);
    const samples = [
      fc.features[0],
      fc.features[Math.floor(fc.features.length / 2)],
      fc.features[fc.features.length - 1],
    ];
    for (const f of samples) {
      expect(
        f.properties[joinKey!],
        `${relPath}: feature missing join-key property '${joinKey}'`,
      ).toBeDefined();
    }
  });
});

describe("contract - boundaryRelPath round-trips against on-disk shards", () => {
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

  it("village for TN district 577 resolves to an existing large shard", () => {
    const relPath = boundaryRelPath("village", "577", "33");
    expect(relPath).toBe("villages/state=tamil-nadu/district=577/all.geojson");
    const path = resolve(boundariesRoot, relPath);
    expect(existsSync(path)).toBe(true);
    expect(statSync(path).size).toBeGreaterThan(1_000_000);
  });
});

