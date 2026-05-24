// Boundary-corpus conformance contract. Runs in `frontend-vitest` alongside
// the other `frontend/src/contracts/*-conform.test.ts` consumers of the
// committed dataset corpus.
//
// Two invariants enforced here that schemas can't:
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
//
// Per-row schema validation (column types, layer_id grammar, source_id
// pattern, denominator invariant) is owned by the backend Tier-A pytest
// suite via `backend/tests/test_boundary_layers_seed.py`. We rely on the
// fused-atomic-commit discipline (CLAUDE.md §15) to keep the parquet and
// the on-disk shards in lockstep — this conform test is the consumer-side
// drift detector.

import { describe, it, expect } from "vitest";
import { existsSync } from "node:fs";
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
