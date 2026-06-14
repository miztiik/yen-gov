// Boundary consumer canaries. Exhaustive boundary corpus validation lives in
// backend Tier-B (`python -m yen_gov validate --root .`). This frontend test
// stays constant-size: it proves representative loader-facing risks without
// creating one test per shard.
//
// Cheap consumer-side invariants enforced here:
//
//   1. Hive-tree shape: representative *.geojson/*.topojson paths still match
//      the path grammar the frontend loaders know how to fetch.
//   2. No legacy sidecars: representative retired sidecar shapes stay absent;
//      exhaustive sidecar rejection is backend Tier-B.
//   3. CSV ledger exists: operator metadata stays adjacent to the shards.
//   4. The states layer still carries the State_LGD join key used by maps.
//   5. A bounded TopoJSON set decodes and matches sibling GeoJSON counts.
//
// Full gzip budget checks are intentionally not in this everyday frontend
// suite. Run tools/boundaries/simplify.py --dry-run --skip-parquet when a PR
// touches boundary geometry or simplification policy.

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { feature as topojsonFeature } from "topojson-client";
import type { Topology, GeometryCollection } from "topojson-specification";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const boundaryFamilyRoot = resolve(repoRoot, "datasets", "boundaries");
const boundariesRoot = resolve(repoRoot, "datasets", "boundaries", "in");

// Hive-path predicates: each kind has one well-formed shape.
const HIVE_SHAPES: { kind: string; pattern: RegExp }[] = [
  { kind: "country", pattern: /^country\/all\.(?:geojson|topojson)$/ },
  { kind: "states", pattern: /^states\/all\.(?:geojson|topojson)$/ },
  { kind: "districts", pattern: /^districts\/all\.(?:geojson|topojson)$/ },
  { kind: "subdistricts", pattern: /^subdistricts\/state=[a-z0-9-]+\/all\.(?:geojson|topojson)$/ },
  // Development Blocks (LGD lineage). Per-state shards under the same
  // Hive layout as subdistricts. Shipped via C.1.b (TODO/20260529-
  // boundary-rip-and-replace-plan.md); registry lives in
  // `maplibre/sources.ts:BLOCK_BOUNDARY`. UP currently absent (12.8 MB
  // shard exceeds 12 MB budget; deferred to C.1.c).
  { kind: "blocks", pattern: /^blocks\/state=[a-z0-9-]+\/all\.(?:geojson|topojson)$/ },
  // Gram Panchayats (LGD lineage). Per-(state, district) shards under
  // the same Hive layout as villages (nested district-keyed because
  // per-state GP counts would blow the 12 MB shard budget for any
  // high-density state). Shipped via C.2.b (TODO/20260529-boundary-
  // rip-and-replace-plan.md); registry will live in
  // `maplibre/sources.ts:PANCHAYAT_BOUNDARY_BY_DISTRICT` (C.2.c).
  { kind: "panchayats", pattern: /^panchayats\/state=[a-z0-9-]+\/district=\d+\/all\.(?:geojson|topojson)$/ },
  // Villages. District segment is normally a numeric LGD code (645 of
  // 659 partitions today), but the C.4.a J&K + Ladakh lift
  // (PR #453, `tools/boundaries/lift_villages_jk_bhuvan.py`) ships
  // 14 Census-2011-vintage shards keyed by ASCII-lowercase district
  // NAME slug (e.g. `district=anantnag`, `district=ladakh_leh`)
  // because that vintage predates the LGD codes for the modern
  // bifurcated districts. The slug alphabet is `[a-z0-9_]+` per the
  // lift script's `CENSUS2011_DISTRICT_TO_MODERN` mapping; the
  // regex below subsumes both the numeric and slug variants.
  { kind: "villages", pattern: /^villages\/state=[a-z0-9-]+\/district=[a-z0-9_]+\/all\.(?:geojson|topojson)$/ },
  // ULB Wards (LGD lineage; SBM_Wards.geojsonl.7z from ramSeraph, MoHUA
  // Swachh Bharat Mission Urban release, CC0 1.0). Per-(state, ulb)
  // shards under a nested ULB-keyed Hive layout (parent partition is
  // ULB, not district — a ULB can span multiple districts; LGD treats
  // ULB as the primary urban entity with its own LGD code). Shipped
  // via C.3.b (docs/archive/plans/20260529-boundary-rip-and-replace-plan.md); the
  // C.3.a infrastructure adds the Hive pattern + lift orchestrator
  // before the live lift runs. Registry will live in
  // `maplibre/sources.ts:WARD_BOUNDARY_BY_ULB` (C.3.c).
  { kind: "wards", pattern: /^wards\/state=[a-z0-9-]+\/ulb=\d+\/all\.(?:geojson|topojson)$/ },
  // Assembly Constituencies (ECI/HTL lineage). Per-state shards under the
  // same Hive layout as subdistricts. Owned by `maplibre/sources.ts`, not
  // the `boundaries.ts` loader; included here so the orphan detector
  // doesn't flag them as legacy.
  { kind: "ac", pattern: /^ac\/state=[a-z0-9-]+\/all\.(?:geojson|topojson)$/ },
  // Parliamentary Constituencies. Single-file national layout keyed on
  // delimitation_vintage (each delimitation order published by ECI/the
  // Delimitation Commission gets its own partition; the current ingest
  // is the 2024 General Election delimitation). The `delim=YYYY/` Hive
  // segment is mandatory because pre-2008 LS data will need pre-2008
  // boundaries when historical seats are added in a future PR.
  { kind: "pc", pattern: /^pc\/delim=\d{4}\/all\.(?:geojson|topojson)$/ },
  // Postal pincode polygons are orthogonal to the LGD hierarchy. They shard
  // by resolved state when possible, plus a synthetic unkeyed bucket for
  // pincodes whose state could not be resolved from the directory table.
  { kind: "postal", pattern: /^postal\/(state=[a-z0-9-]+|scope=unkeyed)\/all\.(?:geojson|topojson)$/ },
];

function isWellFormedHivePath(relPath: string): boolean {
  return HIVE_SHAPES.some(s => s.pattern.test(relPath));
}

const HIVE_PATH_CANARIES = [
  // Root singleton: country silhouette, no join key.
  "country/all.geojson",
  // National administrative layers.
  "states/all.geojson",
  "districts/all.topojson",
  // State-partitioned LGD lineage.
  "subdistricts/state=tamil-nadu/all.geojson",
  "blocks/state=tamil-nadu/all.geojson",
  // Nested district/ULB partitions.
  "panchayats/state=tamil-nadu/district=568/all.topojson",
  "villages/state=tamil-nadu/district=577/all.geojson",
  "wards/state=andaman-and-nicobar/ulb=804041/all.topojson",
  // Orthogonal postal layer.
  "postal/state=tamil-nadu/all.topojson",
] as const;

describe("boundaries-conform - bounded Hive path canaries", () => {
  it.each(HIVE_PATH_CANARIES)("%s matches a known Hive shape and exists", (relPath) => {
    expect(isWellFormedHivePath(relPath), relPath).toBe(true);
    expect(existsSync(resolve(boundariesRoot, relPath)), relPath).toBe(true);
  });

  it("rejects an unknown shape canary", () => {
    expect(isWellFormedHivePath("mystery/state=tamil-nadu/all.geojson")).toBe(false);
  });
});

describe("boundaries-conform — legacy sidecars are gone (T.0d)", () => {
  const SIDECAR_CANARIES = [
    // Provenance sidecar.
    "in/states/all.geojson.sources.json",
    // Simplification metadata sidecar.
    "in/districts/all.geojson.metadata.json",
    // Dropped-feature denominator sidecar.
    "in/subdistricts/state=tamil-nadu/all.geojson.unkeyed.json",
    // Retired per-state village index manifest family.
    "in/villages/state=tamil-nadu/S22-villages-index.json",
  ] as const;

  it.each(SIDECAR_CANARIES)("%s stays absent", (relPath) => {
    expect(existsSync(resolve(boundaryFamilyRoot, relPath)), relPath).toBe(false);
  });
});

describe("boundaries-conform — csv ledger is on disk", () => {
  // The single source of truth for shard inventory. Per-row schema is
  // enforced by backend pytest; we only assert the file is present so
  // future DuckDB-WASM consumers (or any reader that wants to query the
  // inventory) can register the view via the canonical CSV reader seam.
  it("datasets/data/entities/boundary_layer.csv exists", () => {
    const path = resolve(repoRoot, "datasets", "data", "entities", "boundary_layer.csv");
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

const TOPOJSON_DECODE_CANARIES = [
  // Root object name + singleton-ish shape.
  "states/all.topojson",
  // Large national administrative object.
  "districts/all.topojson",
  // State partition path.
  "subdistricts/state=tamil-nadu/all.topojson",
  // Nested district partition path.
  "panchayats/state=tamil-nadu/district=568/all.topojson",
  // Orthogonal postal layer.
  "postal/state=tamil-nadu/all.topojson",
] as const;

describe("boundaries-conform - bounded TopoJSON decode canaries", () => {
  it.each(TOPOJSON_DECODE_CANARIES)("%s decodes to sibling GeoJSON feature count", (topoRel) => {
    const geoRel = topoRel.replace(/\.topojson$/, ".geojson");
    const topoAbs = resolve(boundariesRoot, topoRel);
    const geoAbs = resolve(boundariesRoot, geoRel);
    expect(existsSync(topoAbs), topoRel).toBe(true);
    expect(existsSync(geoAbs), geoRel).toBe(true);
    const topo = JSON.parse(readFileSync(topoAbs, "utf8")) as Topology;
    const geo = JSON.parse(readFileSync(geoAbs, "utf8")) as { features: unknown[] };
    const objectNames = Object.keys(topo.objects ?? {});
    expect(objectNames.length).toBeGreaterThan(0);
    const decoded = topojsonFeature(
      topo,
      topo.objects[objectNames[0]] as GeometryCollection,
    );
    const decodedFeatures =
      decoded.type === "FeatureCollection" ? decoded.features : [decoded];
    expect(decodedFeatures.length).toBe(geo.features.length);
  });
});

