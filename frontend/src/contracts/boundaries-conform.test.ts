// Boundary-corpus conformance contract. Runs in frontend-vitest alongside
// the other frontend/src/contracts/*-conform.test.ts consumers of the
// committed dataset corpus.
//
// Cheap consumer-side invariants enforced here:
//
//   1. Hive-tree shape: every *.geojson under datasets/boundaries/in/ sits at
//      a well-formed path the frontend loaders know how to fetch.
//   2. No legacy sidecars: pre-T.0d sidecar shapes (*.sources.json,
//      *.unkeyed.json, *.metadata.json, *-index.json) are forbidden under
//      datasets/boundaries/ because the parquet ledger is the source of truth.
//   3. Parquet ledger exists: operator metadata stays adjacent to the shards.
//   4. The states layer still carries the State_LGD join key used by maps.
//
// Full gzip budget checks are intentionally not in this everyday frontend
// suite. Run tools/boundaries/simplify.py --dry-run --skip-parquet when a PR
// touches boundary geometry or simplification policy.

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve, sep, posix } from "node:path";
import { fileURLToPath } from "node:url";
import { globSync } from "glob";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const boundaryFamilyRoot = resolve(repoRoot, "datasets", "boundaries");
const boundariesRoot = resolve(repoRoot, "datasets", "boundaries", "in");

// All *.geojson under boundaries/in/, POSIX-normalized.
const ALL_GEOJSON = globSync("**/*.geojson", { cwd: boundariesRoot, absolute: false })
  .map(p => p.split(sep).join(posix.sep))
  .sort();

// Hive-path predicates: each kind has one well-formed shape.
const HIVE_SHAPES: { kind: string; pattern: RegExp }[] = [
  { kind: "country", pattern: /^country\/all\.geojson$/ },
  { kind: "states", pattern: /^states\/all\.geojson$/ },
  { kind: "districts", pattern: /^districts\/all\.geojson$/ },
  { kind: "subdistricts", pattern: /^subdistricts\/state=in_[a-z0-9]+\/all\.geojson$/ },
  // Development Blocks (LGD lineage). Per-state shards under the same
  // Hive layout as subdistricts. Shipped via C.1.b (TODO/20260529-
  // boundary-rip-and-replace-plan.md); registry lives in
  // `maplibre/sources.ts:BLOCK_BOUNDARY`. UP currently absent (12.8 MB
  // shard exceeds 12 MB budget; deferred to C.1.c).
  { kind: "blocks", pattern: /^blocks\/state=in_[a-z0-9]+\/all\.geojson$/ },
  // Gram Panchayats (LGD lineage). Per-(state, district) shards under
  // the same Hive layout as villages (nested district-keyed because
  // per-state GP counts would blow the 12 MB shard budget for any
  // high-density state). Shipped via C.2.b (TODO/20260529-boundary-
  // rip-and-replace-plan.md); registry will live in
  // `maplibre/sources.ts:PANCHAYAT_BOUNDARY_BY_DISTRICT` (C.2.c).
  { kind: "panchayats", pattern: /^panchayats\/state=in_[a-z0-9]+\/district=\d+\/all\.geojson$/ },
  { kind: "villages", pattern: /^villages\/state=in_[a-z0-9]+\/district=\d+\/all\.geojson$/ },
  // Assembly Constituencies (ECI/HTL lineage). Per-state shards under the
  // same Hive layout as subdistricts. Owned by `maplibre/sources.ts`, not
  // the `boundaries.ts` loader; included here so the orphan detector
  // doesn't flag them as legacy.
  { kind: "ac", pattern: /^ac\/state=in_[a-z0-9]+\/all\.geojson$/ },
  // Parliamentary Constituencies. Single-file national layout keyed on
  // delimitation_vintage (each delimitation order published by ECI/the
  // Delimitation Commission gets its own partition; the current ingest
  // is the 2024 General Election delimitation). The `delim=YYYY/` Hive
  // segment is mandatory because pre-2008 LS data will need pre-2008
  // boundaries when historical seats are added in a future PR.
  { kind: "pc", pattern: /^pc\/delim=\d{4}\/all\.geojson$/ },
  // Postal pincode polygons are orthogonal to the LGD hierarchy. They shard
  // by resolved state when possible, plus a synthetic unkeyed bucket for
  // pincodes whose state could not be resolved from the directory table.
  { kind: "postal", pattern: /^postal\/(state=in_[a-z0-9]+|scope=unkeyed)\/all\.geojson$/ },
];

function isWellFormedHivePath(relPath: string): boolean {
  return HIVE_SHAPES.some(s => s.pattern.test(relPath));
}

describe("boundaries-conform — every shipped *.geojson is at a well-formed Hive path", () => {
  it("at least one shard present (sanity)", () => {
    expect(ALL_GEOJSON.length).toBeGreaterThan(0);
  });

  it("no orphan or legacy paths", () => {
    const orphans = ALL_GEOJSON.filter(p => !isWellFormedHivePath(p));
    expect(
      orphans,
      `unrecognised boundary paths (post-T.0d every *.geojson must match a Hive shape): ${orphans.join(", ")}`,
    ).toEqual([]);
  });
});

describe("boundaries-conform — legacy sidecars are gone (T.0d)", () => {
  // The T.0d migration deleted 115 sidecars (.sources.json, .metadata.json,
  // .unkeyed.json) and the S22-villages-index.json manifest. Any survivor
  // is debt that bypasses the parquet ledger.
  const SIDECAR_PATTERNS = [
    "**/*.sources.json",
    "**/*.unkeyed.json",
    "**/*.metadata.json",
    "**/*-index.json",
  ];

  for (const pattern of SIDECAR_PATTERNS) {
    it(`no ${pattern} survivors under datasets/boundaries/`, () => {
      const survivors = globSync(pattern, { cwd: boundaryFamilyRoot, absolute: false });
      expect(
        survivors,
        `legacy sidecar pattern ${pattern} reappeared under datasets/boundaries/ — provenance + simplification + inventory now live in boundary_layers.parquet (ADR-0031 Amendment 2026-05-22)`,
      ).toEqual([]);
    });
  }
});

describe("boundaries-conform — parquet ledger is on disk", () => {
  // The single source of truth for shard inventory. Per-row schema is
  // enforced by backend pytest; we only assert the file is present so the
  // DuckDB-WASM consumers in the SPA can register the view.
  it("datasets/boundaries/boundary_layers.parquet exists", () => {
    const path = resolve(repoRoot, "datasets", "boundaries", "boundary_layers.parquet");
    expect(existsSync(path)).toBe(true);
  });
});

describe("boundaries-conform — states/all.geojson carries LGD-keyed features (Phase D.0)", () => {
  // Post-D.0 the states layer is sourced from ramSeraph's LGD_States
  // release (BharatMaps lineage) and carries `State_LGD` (numeric LGD
  // state code) as the join property — replacing DataMeet's `ST_NM`
  // English name. The layer joins to taxonomy.entities.lgd_code via
  // MapChoropleth's `to-number` coercion in the SPA loader.
  //
  // We assert the on-disk shape directly rather than running the full
  // DuckDB-WASM FK resolution in node (that's covered by the unit test
  // `frontend/src/lib/view-models/states.test.ts::lgdCodeToEci` plus
  // the Playwright golden path). The two invariants here are the ones
  // that would silently break the choropleth fill without test signal.

  const path = resolve(boundariesRoot, "states", "all.geojson");
  const fc = JSON.parse(readFileSync(path, "utf8")) as {
    type: string;
    features: Array<{ properties: Record<string, unknown> }>;
  };

  it("contains 36 currently-valid state/UT polygons", () => {
    expect(fc.type).toBe("FeatureCollection");
    expect(fc.features.length).toBe(36);
  });

  it("every feature carries a positive-integer State_LGD join key", () => {
    const offenders = fc.features
      .map((f, i) => ({ i, lgd: f.properties?.State_LGD }))
      .filter(
        ({ lgd }) =>
          typeof lgd !== "number" || !Number.isInteger(lgd) || lgd < 1 || lgd > 99,
      );
    expect(
      offenders,
      `features missing or carrying malformed State_LGD: ${JSON.stringify(offenders)}`,
    ).toEqual([]);
  });

  it("every feature carries an STNAME label (display fallback)", () => {
    const missing = fc.features.filter(
      (f) => typeof f.properties?.STNAME !== "string" || (f.properties.STNAME as string).length === 0,
    );
    expect(missing.length).toBe(0);
  });

  it("State_LGD values are unique (one polygon per state/UT)", () => {
    const codes = fc.features.map((f) => f.properties.State_LGD as number);
    const unique = new Set(codes);
    expect(unique.size).toBe(codes.length);
  });
});
