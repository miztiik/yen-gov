// state-blocks-registry-coverage contract test.
//
// Invariant: every Development-Block GeoJSON shard that exists on disk
// under `datasets/boundaries/in/blocks/state=<lgd-slug>/all.geojson` MUST
// have a matching `BLOCK_BOUNDARY[<CODE>]` entry in
// `frontend/src/lib/maplibre/sources.ts`, and vice versa. The frontend
// boundary registry and the on-disk boundary corpus are two halves of
// the same contract; if a shard exists but no registry entry points at
// it, the block-grain page silently returns "no boundary configured"
// (the citizen sees a blank map). If a registry entry points at a
// missing shard, the network request 404s.
//
// This is the C.1.b + C.1.c contract test
// (docs/archive/plans/20260529-boundary-rip-and-replace-plan.md) - it locks in the
// 36-shard / 36-entry registry sync (full elective-state coverage)
// and prevents future PRs from drifting either direction.
//
// S24 (Uttar Pradesh) was a documented C.1.b carve-out (block shard
// 12.8 MB > 12 MB SNAPSHOT_BYTE_BUDGET at coord_precision=3). C.1.c
// landed the lift script's auto-fallback path: when a bucket exceeds
// the budget at the default precision, the script re-emits at the
// next coarser precision (coord_precision=2, ~1.1 km) before SKIP.
// UP now lands at ~2.2 MB / 822 features with simplification_tolerance_deg=0.01
// (recorded on the boundary_layers.parquet row). The fallback is
// uniform script behaviour, NOT per-state hand-coded config, so
// renderer-side heterogeneity is invisible (join_property is the LGD
// id; vertex count only affects edge precision invisible at
// choropleth zoom 6-10 for typical block size 10-50 km).
//
// Per-entry shape assertions (post-A.3 BoundaryEntry):
//   - id matches "<CODE>-block"
//   - geojson_local_path matches "boundaries/in/blocks/state=<lgd-slug>/all.geojson"
//   - geojson_url is non-empty https URL
//   - join_property is "block_lgd"
//   - label is non-empty string

import { describe, it, expect } from "vitest";
import { existsSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { BLOCK_BOUNDARY, ECI_TO_LGD_SLUG } from "../lib/boundaries/sources";

const SLUG_TO_ECI: Record<string, string> = Object.fromEntries(
  Object.entries(ECI_TO_LGD_SLUG).map(([code, slug]) => [slug, code]),
);

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const blocksDir = resolve(repoRoot, "datasets", "boundaries", "in", "blocks");

// Discover all on-disk block shards under the Hive partition layout.
// Returns ["S01", "S02", ...] - 3-character state/UT codes.
function discoverShards(): string[] {
  if (!existsSync(blocksDir)) return [];
  const codes: string[] = [];
  for (const entry of readdirSync(blocksDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const m = entry.name.match(/^state=(.+)$/);
    if (!m) continue;
    const slug = m[1];
    const code = SLUG_TO_ECI[slug];
    if (!code) continue;
    const shard = resolve(blocksDir, entry.name, "all.geojson");
    if (existsSync(shard)) codes.push(code);
  }
  return codes.sort();
}

const shardCodes = discoverShards();
const registryCodes = Object.keys(BLOCK_BOUNDARY).sort();

describe("BLOCK_BOUNDARY registry covers every on-disk block shard", () => {
  it("discovers at least 36 on-disk block shards", () => {
    // Sanity floor: post-C.1.c the corpus carries 36 block shards
    // (one per state/UT that ramSeraph LGD_Blocks attributes; full
    // elective coverage achieved by the lift script's coord_precision
    // auto-fallback). If this drops below 36, an earlier PR has
    // retired shards without updating the registry contract.
    expect(shardCodes.length).toBeGreaterThanOrEqual(36);
  });

  it("registry entry exists for every on-disk shard", () => {
    const missing = shardCodes.filter((c) => !(c in BLOCK_BOUNDARY));
    expect(missing).toEqual([]);
  });

  it("on-disk shard exists for every registry entry", () => {
    const orphans = registryCodes.filter((c) => !shardCodes.includes(c));
    expect(orphans).toEqual([]);
  });

  it("S24 (Uttar Pradesh) is present on BOTH disk and registry (C.1.c)", () => {
    // C.1.c landed the lift script's auto-fallback: S24's shard is
    // emitted at coord_precision=2 (~1.1 km / 2.2 MB / 822 features)
    // when the default precision exceeds the 12 MB budget. This
    // assertion is the symmetric replacement for the C.1.b
    // "S24 absent from both" carve-out and locks in full elective
    // coverage. Any future budget regression that re-trips SKIP
    // would FAIL this test.
    expect(shardCodes).toContain("S24");
    expect(registryCodes).toContain("S24");
  });
});

describe("BLOCK_BOUNDARY entry shape is well-formed", () => {
  it.each(Object.entries(BLOCK_BOUNDARY))(
    "entry %s carries the post-A.3 BoundaryEntry shape",
    (code, entry) => {
      expect(entry.id).toBe(`${code}-block`);
      expect(entry.geojson_local_path).toBe(
        `boundaries/in/blocks/state=${ECI_TO_LGD_SLUG[code]}/all.geojson`,
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
    // docs/archive/notes/2026-05-29-c1-blocks-source-hunt-verdict.md). Any
    // per-state divergence in the upstream URL should be a
    // deliberate, reviewed decision - this assertion forces that.
    const upstreamUrl =
      "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/blocks/LGD_Blocks.geojsonl.7z";
    for (const [_code, entry] of Object.entries(BLOCK_BOUNDARY)) {
      expect(entry.geojson_url).toBe(upstreamUrl);
    }
  });
});
