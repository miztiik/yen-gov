// state-wards-registry-coverage contract test.
//
// High-cardinality registry truth is generated from the boundary encoding
// receipt. This test proves freshness and a few representative consumer
// canaries; it deliberately does not recursively read
// datasets/boundaries/in/wards.

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";
import {
  WARD_BOUNDARY_BY_ULB,
  WARDS_BY_STATE,
  WARD_STATE_NAMES,
} from "../lib/boundaries/sources";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const pythonCandidates = [
  process.env.YEN_GOV_PYTHON,
  process.env.PYTHON,
  resolve(repoRoot, ".venv", "Scripts", "python.exe"),
  resolve(repoRoot, "..", "yen-gov", ".venv", "Scripts", "python.exe"),
  "python",
].filter(Boolean) as string[];

function runGeneratorCheck(): string {
  let lastError: unknown;
  for (const executable of pythonCandidates) {
    if (executable.endsWith("python.exe") && !existsSync(executable)) continue;
    try {
      return execFileSync(executable, ["tools/boundaries/generate_frontend_registry.py", "--check"], {
        cwd: repoRoot,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      });
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

const generatedKeyCount = Object.values(WARDS_BY_STATE).reduce((sum, ulbs) => sum + ulbs.length, 0);

describe("WARD_BOUNDARY_BY_ULB generated registry", () => {
  it("is fresh against boundary_encoding.csv and hand-authored state labels", () => {
    expect(runGeneratorCheck()).toContain("generated-sources.ts is fresh");
  });

  it("has one generated BoundaryEntry per generated ULB key", () => {
    expect(Object.keys(WARD_BOUNDARY_BY_ULB).length).toBe(generatedKeyCount);
  });

  it("keeps bounded sentinel entries well-formed", () => {
    const sentinels = [
      ["S24-800629", "uttar-pradesh", "Uttar Pradesh"],
      ["S13-802640", "maharashtra", "Maharashtra"],
      ["U08-800001", "jammu-and-kashmir", "Jammu & Kashmir"],
    ] as const;

    for (const [key, slug, label] of sentinels) {
      const entry = WARD_BOUNDARY_BY_ULB[key];
      const ulbLgd = key.split("-")[1];
      expect(entry, `${key} should exist`).toBeDefined();
      expect(entry.id).toBe(`${key}-ward`);
      expect(entry.geojson_local_path).toBe(
        `boundaries/in/wards/state=${slug}/ulb=${ulbLgd}/all.geojson`,
      );
      expect(entry.geojson_url).toBe(
        "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/urban/SBM_Wards.geojsonl.7z",
      );
      expect(entry.join_property).toBe("wardcode");
      expect(entry.label).toContain(label);
      expect((entry as unknown as Record<string, unknown>).attribution).toBeUndefined();
    }
  });

  it("uses the hand-authored ward state labels for every generated state", () => {
    expect(Object.keys(WARD_STATE_NAMES).sort()).toEqual(Object.keys(WARDS_BY_STATE).sort());
  });
});
