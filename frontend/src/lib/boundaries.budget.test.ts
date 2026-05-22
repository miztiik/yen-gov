// Bundle-budget contract (Fowler v3 nit). Two ratchets:
//
//   1. Per-shard byte budget — the whole point of partitioning villages by
//      district was that a single click pulls a small shard. If a future
//      snapshot regression ships a 50 MB shard, this test catches it
//      before a citizen sits through the download.
//   2. Total chunk count ceiling — one shard per TN district, one national
//      silhouette, one states layer, one districts layer, one subdistricts
//      shard per state. The current count should sit comfortably under 80;
//      if it ever exceeds 80 we want a conscious decision (split policy
//      change, new state coverage), not drift.
//
// Post-T.0d (ADR-0031 Amendment 2026-05-22): files live under the Hive
// tree `datasets/boundaries/in/<kind>/state=in_<lc>/district=<lgd>/all.geojson`.
// File-classification is by parent-path component, not basename. The
// shard-vs-index-count cross-check is gone (no index file post-migration;
// the parquet ledger at `datasets/boundaries/boundary_layers.parquet`
// is the single source of truth, validated by `boundaries-conform`).
//
// Budgets here are a deliberate ceiling — well above today's largest file
// — so the test fails on a *snapshot regression*, not on routine growth.
import { describe, it, expect } from "vitest";
import { statSync } from "node:fs";
import { resolve, sep, posix } from "node:path";
import { fileURLToPath } from "node:url";
import { globSync } from "glob";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const boundariesRoot = resolve(repoRoot, "datasets", "boundaries", "in");

// Per-shard ceiling: today's largest village shard is ~2.8 MB. 4 MB is the
// "this is genuinely large for one click but still tolerable" line. Bigger
// than that almost certainly means a coord_precision or filtering regression.
const VILLAGE_SHARD_MAX_BYTES = 4 * 1024 * 1024;

// Subdistrict per-state file: today's TN file is ~5 MB. 8 MB ceiling.
const SUBDISTRICT_MAX_BYTES = 8 * 1024 * 1024;

// National silhouettes (country, states, districts) are large by nature
// — single national outlines at acceptable detail. 16 MB ceiling.
const NATIONAL_MAX_BYTES = 16 * 1024 * 1024;

// Total chunk-count ratchet — the loader's path table is finite; runaway
// growth means a split-policy regression.
const MAX_TOTAL_CHUNKS = 80;

// Glob the Hive tree. `glob` returns POSIX-separated relative paths even on
// Windows; normalize to POSIX for the kind-classification regexes.
const ALL_SHARDS = globSync("**/all.geojson", { cwd: boundariesRoot, absolute: false })
  .map(p => p.split(sep).join(posix.sep))
  .sort();

function kindOf(relPath: string): "village" | "subdistrict" | "national" | null {
  if (relPath.startsWith("villages/")) return "village";
  if (relPath.startsWith("subdistricts/")) return "subdistrict";
  if (
    relPath.startsWith("country/") ||
    relPath.startsWith("states/") ||
    relPath.startsWith("districts/")
  )
    return "national";
  return null;
}

describe("budget — per-shard byte ceilings", () => {
  it("at least one shard is present (sanity)", () => {
    expect(ALL_SHARDS.length).toBeGreaterThan(0);
  });

  for (const relPath of ALL_SHARDS) {
    const size = statSync(resolve(boundariesRoot, relPath)).size;
    const kind = kindOf(relPath);
    if (kind === "village") {
      it(`${relPath} ≤ ${VILLAGE_SHARD_MAX_BYTES} bytes (got ${size})`, () => {
        expect(size).toBeLessThanOrEqual(VILLAGE_SHARD_MAX_BYTES);
      });
    } else if (kind === "subdistrict") {
      it(`${relPath} ≤ ${SUBDISTRICT_MAX_BYTES} bytes (got ${size})`, () => {
        expect(size).toBeLessThanOrEqual(SUBDISTRICT_MAX_BYTES);
      });
    } else if (kind === "national") {
      it(`${relPath} ≤ ${NATIONAL_MAX_BYTES} bytes (got ${size})`, () => {
        expect(size).toBeLessThanOrEqual(NATIONAL_MAX_BYTES);
      });
    }
    // Anything else (postal/, future kinds) is out of scope for this budget.
  }
});

describe("budget — total chunk count ratchet", () => {
  it(`≤ ${MAX_TOTAL_CHUNKS} all.geojson shards under boundaries/in/ (got ${ALL_SHARDS.length})`, () => {
    expect(ALL_SHARDS.length).toBeLessThanOrEqual(MAX_TOTAL_CHUNKS);
  });
});
