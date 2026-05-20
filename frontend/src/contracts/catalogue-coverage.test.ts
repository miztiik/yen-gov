/**
 * Contract test (Phase 0 of TODO/VIZ-LAYER-GAPS-PLAN.md):
 * THE CATALOGUE DRIFT DETECTOR.
 *
 * Job: enforce that every indicator artifact on disk under
 * `datasets/indicators/in/**` is EITHER referenced from
 * `datasets/taxonomy/topics.json` OR justified in
 * `catalogue-coverage.allowlist.json`. Anything else fails the build.
 *
 * Why: as of the 2026-05-15 audit, 41 of 80 indicator artifacts were on
 * disk but unreachable from the IA — silently invisible to citizens.
 * Without a ratchet, every new ingest widens the gap. With this test,
 * the count can only go down: the way to land a new artifact is
 * (a) wire it in topics.json, OR (b) add it to the allowlist
 * with a written reason. Either way the choice becomes visible in code
 * review instead of getting buried in `notes/`.
 *
 * The test does THREE things:
 *   1. Every on-disk indicator id is wired OR allowlisted.
 *   2. Every allowlisted id actually exists on disk (no stale entries).
 *   3. No id is both wired AND allowlisted (one or the other).
 *
 * Companion to the existing schema-conformance test in
 * `datasets-conform.test.ts`. That test enforces that data IS valid;
 * this test enforces that valid data is also REACHABLE.
 *
 * Path moved in T.0b from `datasets/reference/in/topic-catalogue.json`
 * (TODO/20260517-canonical-long-format-pivot.md §0e Phase 0 closeout).
 *
 * See: docs/architecture/frontend/catalogue-drift-detector.md
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { globSync } from "glob";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const indicatorsDir = resolve(repoRoot, "datasets", "indicators", "in");
const cataloguePath = resolve(repoRoot, "datasets", "taxonomy", "topics.json");
const allowlistPath = resolve(__dirname, "catalogue-coverage.allowlist.json");

interface CatalogueArtifact {
  kind?: string;
  id?: string;
}
interface CatalogueTopic {
  artifacts?: CatalogueArtifact[];
}
interface Catalogue {
  topics?: CatalogueTopic[];
}

interface AllowlistEntry {
  id: string;
  reason: string;
}
interface AllowlistFile {
  allowlist: AllowlistEntry[];
}

/** Indicator ids referenced by the IA spine. */
function loadWiredIds(): Set<string> {
  const cat = JSON.parse(readFileSync(cataloguePath, "utf-8")) as Catalogue;
  const out = new Set<string>();
  for (const topic of cat.topics ?? []) {
    for (const art of topic.artifacts ?? []) {
      if (art.kind === "indicator" && typeof art.id === "string" && art.id.length > 0) {
        out.add(art.id);
      }
    }
  }
  return out;
}

/** Indicator ids physically present in datasets/indicators/in/.
 *
 * Excludes `*.notes.json` sidecars — those are editorial overlays for an
 * indicator artifact (schema: indicator-notes.schema.json), not indicator
 * artifacts themselves. They live next to the main `<id>.json` and are
 * keyed off the same id; surfacing them here would generate spurious
 * "<id>.notes" orphans that would have to be either wired (meaningless)
 * or allowlisted (mass churn for no signal).
 */
function loadOnDiskIds(): Set<string> {
  const files = globSync("**/*.json", { cwd: indicatorsDir, absolute: false, posix: true });
  const out = new Set<string>();
  for (const rel of files) {
    if (rel.endsWith(".notes.json")) continue;
    out.add(rel.replace(/\.json$/, ""));
  }
  return out;
}

/** Indicator ids explicitly excused from being wired. */
function loadAllowlist(): AllowlistEntry[] {
  const raw = JSON.parse(readFileSync(allowlistPath, "utf-8")) as AllowlistFile;
  return raw.allowlist;
}

const WIRED = loadWiredIds();
const ON_DISK = loadOnDiskIds();
const ALLOWLIST = loadAllowlist();
const ALLOWED_IDS = new Set(ALLOWLIST.map(e => e.id));

describe("contract — catalogue drift detector", () => {
  it("workspace contains the catalogue and at least one indicator artifact", () => {
    expect(WIRED.size, "topics.json wired set is empty — wrong path?").toBeGreaterThan(0);
    expect(ON_DISK.size, "no indicator artifacts found on disk — wrong path?").toBeGreaterThan(0);
  });

  it("every on-disk indicator is either wired or explicitly allowlisted", () => {
    const orphans = [...ON_DISK].filter(id => !WIRED.has(id) && !ALLOWED_IDS.has(id)).sort();
    if (orphans.length > 0) {
      const msg = [
        `${orphans.length} indicator artifact(s) are on disk but neither wired in topics.json nor allowlisted:`,
        ...orphans.map(id => `  - ${id}`),
        "",
        "Fix one of:",
        "  (a) Wire the artifact: add it to datasets/taxonomy/topics.json under the right topic.",
        "  (b) Justify it: add it to frontend/src/contracts/catalogue-coverage.allowlist.json with a one-line reason.",
        "",
        "Either choice is recorded; silently shipping unreachable data is not (Phase 0 ratchet, see TODO/VIZ-LAYER-GAPS-PLAN.md).",
      ].join("\n");
      throw new Error(msg);
    }
  });

  it("every allowlist entry references an artifact that actually exists on disk", () => {
    const stale = ALLOWLIST.filter(e => !ON_DISK.has(e.id)).map(e => e.id).sort();
    if (stale.length > 0) {
      const msg = [
        `${stale.length} allowlist entry(s) reference indicators that no longer exist on disk:`,
        ...stale.map(id => `  - ${id}`),
        "",
        "Remove these from frontend/src/contracts/catalogue-coverage.allowlist.json — the artifact has been deleted or renamed.",
      ].join("\n");
      throw new Error(msg);
    }
  });

  it("no id is both wired AND allowlisted", () => {
    const both = ALLOWLIST.filter(e => WIRED.has(e.id)).map(e => e.id).sort();
    if (both.length > 0) {
      const msg = [
        `${both.length} indicator(s) are both wired in topics.json AND listed in the allowlist:`,
        ...both.map(id => `  - ${id}`),
        "",
        "Once an indicator is wired the allowlist entry is redundant — remove it from the allowlist.",
      ].join("\n");
      throw new Error(msg);
    }
  });

  it("every allowlist entry carries a non-empty reason", () => {
    const empty = ALLOWLIST.filter(e => !e.reason || e.reason.trim().length === 0).map(e => e.id);
    expect(empty, `allowlist entries without a reason: ${empty.join(", ")}`).toEqual([]);
  });
});
