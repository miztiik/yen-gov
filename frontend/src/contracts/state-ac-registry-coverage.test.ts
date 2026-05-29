// state-ac-registry-coverage contract test.
//
// Invariant: every AC GeoJSON shard that exists on disk under
// `datasets/boundaries/in/ac/state=in_<lc>/all.geojson` MUST have a
// matching `STATE_AC[<CODE>]` entry in `frontend/src/lib/maplibre/sources.ts`,
// and vice versa. The frontend boundary registry and the on-disk
// boundary corpus are two halves of the same contract; if a shard
// exists but no registry entry points at it, `/s/<state>/ac/<n>` will
// silently return "no boundary configured" (the citizen sees a blank
// map). If a registry entry points at a missing shard, the network
// request 404s.
//
// This is the A.2 contract test
// (TODO/20260529-boundary-rip-and-replace-plan.md) - it locks in the
// 31-shard / 31-entry registry sync that A.2 ships, and prevents
// future PRs from drifting either direction.
//
// Per-entry shape assertions (post-A.3 BoundaryEntry):
//   - id matches "<CODE>-ac"
//   - geojson_local_path matches "boundaries/in/ac/state=in_<lc>/all.geojson"
//   - geojson_url is non-empty https URL
//   - join_property is non-empty string
//   - label is non-empty string

import { describe, it, expect } from "vitest";
import { existsSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { STATE_AC } from "../lib/maplibre/sources";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const acDir = resolve(repoRoot, "datasets", "boundaries", "in", "ac");

// Discover all on-disk AC shards under the Hive partition layout.
// Returns ["S01", "S02", ...] - 2- or 3-character state/UT codes.
function discoverShards(): string[] {
  if (!existsSync(acDir)) return [];
  const codes: string[] = [];
  for (const entry of readdirSync(acDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const m = entry.name.match(/^state=in_([su]\d{2})$/);
    if (!m) continue;
    const code = m[1].toUpperCase();
    const shard = resolve(acDir, entry.name, "all.geojson");
    if (existsSync(shard)) codes.push(code);
  }
  return codes.sort();
}

const shardCodes = discoverShards();
const registryCodes = Object.keys(STATE_AC).sort();

describe("STATE_AC registry covers every on-disk AC shard", () => {
  it("discovers at least 31 on-disk AC shards", () => {
    // Sanity floor: post-D.7 R1 + A.1.b, the corpus should carry >=31
    // AC shards. If this drops below 31, an earlier PR has retired
    // shards without updating the registry contract.
    expect(shardCodes.length).toBeGreaterThanOrEqual(31);
  });

  it("registry entry exists for every on-disk shard", () => {
    const missing = shardCodes.filter((c) => !(c in STATE_AC));
    expect(missing).toEqual([]);
  });

  it("on-disk shard exists for every registry entry", () => {
    const orphans = registryCodes.filter((c) => !shardCodes.includes(c));
    expect(orphans).toEqual([]);
  });
});

describe("STATE_AC entry shape is well-formed", () => {
  it.each(Object.entries(STATE_AC))(
    "entry %s carries the post-A.3 BoundaryEntry shape",
    (code, entry) => {
      expect(entry.id).toBe(`${code}-ac`);
      expect(entry.geojson_local_path).toBe(
        `boundaries/in/ac/state=in_${code.toLowerCase()}/all.geojson`,
      );
      expect(entry.geojson_url).toMatch(/^https:\/\//);
      expect(entry.join_property).toMatch(/^[a-z_]+$/);
      expect(entry.label.length).toBeGreaterThan(3);
      // A.3 removed the attribution field from the interface; this
      // assertion is structural - if a future PR re-adds the field on
      // an entry the TS compiler catches it (Object literal may only
      // specify known properties).
      expect((entry as unknown as Record<string, unknown>).attribution).toBeUndefined();
    },
  );

  it("U08 uses seat_id join key (post-2022 J&K shijithpk supplement)", () => {
    // Documented exception: shijithpk's J&K post-2022 90-AC supplement
    // uses `seat_id` not `ac_no`. Lock this in so a future "normalise
    // all join keys to ac_no" PR doesn't silently change behaviour.
    expect(STATE_AC.U08.join_property).toBe("seat_id");
  });

  it("all non-U08 entries use ac_no join key", () => {
    for (const [code, entry] of Object.entries(STATE_AC)) {
      if (code === "U08") continue;
      expect(entry.join_property).toBe("ac_no");
    }
  });
});
