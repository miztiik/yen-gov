// Boundary-corpus conformance contract. Runs in `frontend-vitest` alongside
// the other `frontend/src/contracts/*-conform.test.ts` consumers of the
// committed dataset corpus.
//
// Three invariants enforced here that schemas can't:
//
//   1. **Hive-tree shape**: every `*.geojson` under `datasets/boundaries/in/`
//      sits at a well-formed Hive path. The contract paths the loader uses
//      are the only paths that should appear; anything else is dead weight
//      or a legacy artifact the T.0d migration missed.
//   2. **No legacy sidecars**: pre-T.0d sidecar shapes
//      (`*.sources.json`, `*.unkeyed.json`, `*.metadata.json`,
//      `*-index.json`) are now forbidden under `datasets/boundaries/`.
//      Provenance + unkeyed counts + simplification metadata all live in
//      `boundary_layers.parquet`. The Tier-B validator carries the same
//      gate; this file is the front-end-side mirror so the contract is
//      enforced in the same suite as the boundary loader.
//   3. **Per-layer gzipped-size ceiling** (Phase 0.4 of the boundary-
//      coverage expansion plan, 2026-05-24): every shipped GeoJSON shard
//      gzips below the per-layer budget asserted in `LAYER_GZIP_CEILING_KB`.
//      The publish pipeline serves these shards as gzipped HTTP responses
//      from GitHub Pages — the citizen pays this byte cost on every map
//      load. The ceiling is the regression gate against an ingest re-emit
//      that silently re-inflates a geometry (e.g. mapshaper not run, a
//      higher-resolution upstream landed without a `simplify.py` re-run).
//
// Per-row schema validation (column types, layer_id grammar, source_id
// pattern, denominator invariant) is owned by the backend Tier-A pytest
// suite via `backend/tests/test_boundary_layers_seed.py`. We rely on the
// fused-atomic-commit discipline (CLAUDE.md §15) to keep the parquet and
// the on-disk shards in lockstep — this conform test is the consumer-side
// drift detector.

import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { resolve, sep, posix } from "node:path";
import { fileURLToPath } from "node:url";
import { globSync } from "glob";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
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
  // Postal Chennai: pre-Hive single-file layout; promote when a second state lands.
  { kind: "postal", pattern: /^postal\/IN-pincodes-[a-z0-9-]+\.geojson$/ },
];

function isWellFormedHivePath(relPath: string): boolean {
  return HIVE_SHAPES.some(s => s.pattern.test(relPath));
}

// Per-layer gzipped-size ceiling in KB. MUST stay in lockstep with
// `tools/boundaries/simplify.py:LAYER_TUNING` — the simplifier produces
// these sizes; this contract enforces them on every CI run. A future PR
// that bumps the simplifier ceiling without bumping this constant (or
// vice-versa) is the drift class this pair is designed to catch.
//
// Keys are the Hive top-level segment (matches the `kind` field above).
// A new layer added without an entry here is flagged by the
// "every kind has a ceiling entry" sanity check below.
const LAYER_GZIP_CEILING_KB: Record<string, number> = {
  country: 100,
  states: 200,
  districts: 500,
  subdistricts: 300,
  villages: 500,
  ac: 500,
  pc: 500,
  postal: 500,
};

function hiveKindOf(relPath: string): string | null {
  // Strip everything past the top-level segment and look up.
  const top = relPath.split("/")[0];
  if (top in LAYER_GZIP_CEILING_KB) return top;
  return null;
}

function gzipKB(absPath: string): number {
  const raw = readFileSync(absPath);
  return gzipSync(raw, { level: 6 }).byteLength / 1024;
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

describe("boundaries-conform — per-layer gzipped-size ceiling (Phase 0.4)", () => {
  // The seven Hive shapes above all classify their files to one of
  // LAYER_GZIP_CEILING_KB's eight keys (postal currently has no on-disk
  // shard). A future kind added to HIVE_SHAPES without a ceiling entry
  // would let an arbitrarily fat geometry land unchecked.
  it("every Hive kind has a gzip-size ceiling entry", () => {
    const kindsInPaths = new Set(HIVE_SHAPES.map(s => s.kind));
    const kindsWithCeiling = new Set(Object.keys(LAYER_GZIP_CEILING_KB));
    const missing = [...kindsInPaths].filter(k => !kindsWithCeiling.has(k));
    expect(
      missing,
      `Hive kinds without a LAYER_GZIP_CEILING_KB entry: ${missing.join(", ")} — add the kind to LAYER_GZIP_CEILING_KB and bump tools/boundaries/simplify.py LAYER_TUNING in lockstep`,
    ).toEqual([]);
  });

  // The actual ceiling assertion. One test per file so the failure
  // surface is precise — vitest will list every breaching shard by
  // name with its actual gzipped size.
  for (const rel of ALL_GEOJSON) {
    const kind = hiveKindOf(rel);
    if (kind === null) continue; // orphan detector above handles this
    const ceilingKB = LAYER_GZIP_CEILING_KB[kind];
    it(`${rel} gzips to <= ${ceilingKB} KB`, () => {
      const abs = resolve(boundariesRoot, rel);
      const actualKB = gzipKB(abs);
      expect(
        actualKB,
        `${rel} is ${actualKB.toFixed(1)} KB gzipped (ceiling ${ceilingKB} KB). Re-run tools/boundaries/simplify.py to thin the geometry, or bump LAYER_TUNING + LAYER_GZIP_CEILING_KB together if the citizen-byte budget is being deliberately raised.`,
      ).toBeLessThanOrEqual(ceilingKB);
    });
  }
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
      const survivors = globSync(pattern, { cwd: boundariesRoot, absolute: false });
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
