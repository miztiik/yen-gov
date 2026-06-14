// state-panchayats-registry-coverage contract test.
//
// High-cardinality registry truth is generated from the boundary encoding
// receipt. This test proves freshness and a few representative consumer
// canaries; it deliberately does not recursively read
// datasets/boundaries/in/panchayats.

import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it, expect } from "vitest";
import {
  PANCHAYAT_BOUNDARY_BY_DISTRICT,
  PANCHAYAT_DISTRICTS_BY_STATE,
  PANCHAYAT_STATE_NAMES,
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

const generatedKeyCount = Object.values(PANCHAYAT_DISTRICTS_BY_STATE).reduce(
  (sum, districts) => sum + districts.length,
  0,
);

describe("PANCHAYAT_BOUNDARY_BY_DISTRICT generated registry", () => {
  it("is fresh against boundary_encoding.csv and hand-authored state labels", () => {
    expect(runGeneratorCheck()).toContain("generated-sources.ts is fresh");
  });

  it("has one generated BoundaryEntry per generated district key", () => {
    expect(Object.keys(PANCHAYAT_BOUNDARY_BY_DISTRICT).length).toBe(generatedKeyCount);
  });

  it("keeps bounded sentinel entries well-formed", () => {
    const sentinels = [
      ["S13-490", "maharashtra", "Maharashtra"],
      ["S24-118", "uttar-pradesh", "Uttar Pradesh"],
      ["U01-602", "andaman-and-nicobar", "Andaman & Nicobar Islands"],
    ] as const;

    for (const [key, slug, label] of sentinels) {
      const entry = PANCHAYAT_BOUNDARY_BY_DISTRICT[key];
      const districtLgd = key.split("-")[1];
      expect(entry, `${key} should exist`).toBeDefined();
      expect(entry.id).toBe(`${key}-panchayat`);
      expect(entry.geojson_local_path).toBe(
        `boundaries/in/panchayats/state=${slug}/district=${districtLgd}/all.geojson`,
      );
      expect(entry.geojson_url).toBe(
        "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/panchayats/LGD_Panchayats.geojsonl.7z",
      );
      expect(entry.join_property).toBe("gp_code");
      expect(entry.label).toContain(label);
      expect((entry as unknown as Record<string, unknown>).attribution).toBeUndefined();
    }
  });

  it("uses the hand-authored panchayat state labels for every generated state", () => {
    expect(Object.keys(PANCHAYAT_STATE_NAMES).sort()).toEqual(
      Object.keys(PANCHAYAT_DISTRICTS_BY_STATE).sort(),
    );
  });
});
