// state-blocks-registry-coverage contract test.
//
// Invariant: every Development-Block GeoJSON shard that exists on disk
// under `datasets/boundaries/in/blocks/state=in_<lc>/all.geojson` MUST
// have a matching `BLOCK_BOUNDARY[<CODE>]` entry in
// `frontend/src/lib/maplibre/sources.ts`, and vice versa. The frontend
// boundary registry and the on-disk boundary corpus are two halves of
// the same contract; if a shard exists but no registry entry points at
// it, the block-grain page silently returns "no boundary configured"
// (the citizen sees a blank map). If a registry entry points at a
// missing shard, the network request 404s.
//
// This is the C.1.b contract test
// (TODO/20260529-boundary-rip-and-replace-plan.md) - it locks in the
// 35-shard / 35-entry registry sync that C.1.b ships, and prevents
// future PRs from drifting either direction.
//
// Documented carve-out: S24 (Uttar Pradesh) is intentionally NOT in
// the on-disk corpus or the registry. UP's block shard at the standard
// coord_precision=3 renders to 12.8 MB - 7% over the 12 MB
// SNAPSHOT_BYTE_BUDGET. Per the established precedent
// (lift_villages_national.py + lift_subdistricts_national.py both SKIP
// oversized state shards rather than degrade precision per-state), UP
// is deferred to C.1.c follow-up. This test asserts S24 is absent on
// BOTH sides; a future PR that lands C.1.c will replace these
// assertions with the unconditional "exists on both sides" rules.
//
// Per-entry shape assertions (post-A.3 BoundaryEntry):
//   - id matches "<CODE>-block"
//   - geojson_local_path matches "boundaries/in/blocks/state=in_<lc>/all.geojson"
//   - geojson_url is non-empty https URL
//   - join_property is "block_lgd"
//   - label is non-empty string

import { describe, it, expect } from "vitest";
import { existsSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { BLOCK_BOUNDARY } from "../lib/maplibre/sources";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const blocksDir = resolve(repoRoot, "datasets", "boundaries", "in", "blocks");

// Discover all on-disk block shards under the Hive partition layout.
// Returns ["S01", "S02", ...] - 3-character state/UT codes.
function discoverShards(): string[] {
  if (!existsSync(blocksDir)) return [];
  const codes: string[] = [];
  for (const entry of readdirSync(blocksDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const m = entry.name.match(/^state=in_([su]\d{2})$/);
    if (!m) continue;
    const code = m[1].toUpperCase();
    const shard = resolve(blocksDir, entry.name, "all.geojson");
    if (existsSync(shard)) codes.push(code);
  }
  return codes.sort();
}

const shardCodes = discoverShards();
const registryCodes = Object.keys(BLOCK_BOUNDARY).sort();

describe("BLOCK_BOUNDARY registry covers every on-disk block shard", () => {
  it("discovers at least 35 on-disk block shards", () => {
    // Sanity floor: post-C.1.b the corpus carries 35 block shards
    // (one per state/UT that ramSeraph LGD_Blocks attributes, minus
    // S24 deferred to C.1.c). If this drops below 35, an earlier PR
    // has retired shards without updating the registry contract.
    expect(shardCodes.length).toBeGreaterThanOrEqual(35);
  });

  it("registry entry exists for every on-disk shard", () => {
    const missing = shardCodes.filter((c) => !(c in BLOCK_BOUNDARY));
    expect(missing).toEqual([]);
  });

  it("on-disk shard exists for every registry entry", () => {
    const orphans = registryCodes.filter((c) => !shardCodes.includes(c));
    expect(orphans).toEqual([]);
  });

  it("S24 (Uttar Pradesh) is absent from BOTH disk and registry (C.1.c follow-up)", () => {
    // Documented C.1.b carve-out: UP block shard exceeds the 12 MB
    // SNAPSHOT_BYTE_BUDGET at coord_precision=3 and is skipped by
    // tools/boundaries/lift_blocks_national.py. The registry must
    // NOT carry a stale S24 entry pointing at a missing snapshot.
    // When C.1.c lands (per-state coord_precision override OR
    // Douglas-Peucker simplification), DELETE this assertion and
    // verify S24 appears on both sides.
    expect(shardCodes).not.toContain("S24");
    expect(registryCodes).not.toContain("S24");
  });
});

describe("BLOCK_BOUNDARY entry shape is well-formed", () => {
  it.each(Object.entries(BLOCK_BOUNDARY))(
    "entry %s carries the post-A.3 BoundaryEntry shape",
    (code, entry) => {
      expect(entry.id).toBe(`${code}-block`);
      expect(entry.geojson_local_path).toBe(
        `boundaries/in/blocks/state=in_${code.toLowerCase()}/all.geojson`,
      );
      expect(entry.geojson_url).toMatch(/^https:\/\//);
      expect(entry.join_property).toBe("block_lgd");
      expect(entry.label.length).toBeGreaterThan(3);
      // A.3 removed the attribution field from the interface; this
      // assertion is structural - if a future PR re-adds the field on
      // an entry the TS compiler catches it (Object literal may only
      // specify known properties).
      expect((entry as unknown as Record<string, unknown>).attribution).toBeUndefined();
    },
  );

  it("all entries point at the same ramSeraph LGD_Blocks upstream URL", () => {
    // Block-level boundary source-of-truth is a single national
    // geojsonl bundle on ramSeraph (per C.1 recon verdict,
    // notes/2026-05-29-c1-blocks-source-hunt-verdict.md). Any
    // per-state divergence in the upstream URL should be a
    // deliberate, reviewed decision - this assertion forces that.
    const upstreamUrl =
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z";
    for (const [_code, entry] of Object.entries(BLOCK_BOUNDARY)) {
      expect(entry.geojson_url).toBe(upstreamUrl);
    }
  });
});
