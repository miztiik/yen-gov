/**
 * Drift gate for the chart-index contract (plan section 20.9 + 21.9).
 *
 * The contract surface is THREE artifacts that MUST stay 1:1:
 *   (A) the ChartType union at frontend/src/lib/grapher/catalogue.ts
 *   (B) the renderer rows in section 1 of docs/reference/chart-index.md
 *       (one Machine id per row; the Machine id IS the load-bearing handle)
 *   (C) the matrix rows in section 2 of docs/reference/chart-index.md,
 *       encoded as the pure function feasibleAt() at
 *       frontend/src/lib/grapher/feasibleAt.ts
 *
 * U4 (2026-06-05): all D-DOC2-era it.todo stubs are now LIVE. The
 * drift gate is the chart-drift-test named in plan section 22.6.
 *
 * Per /memories/lessons.md ("vitest does NOT resolve the $lib
 * SvelteKit alias by default"), this file uses relative imports only.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { ChartType } from "./catalogue";
import {
  feasibleAt,
  intersectWithCatalogue,
  type DataShape,
  type FeasibleAtInput,
} from "./feasibleAt";

const repoRoot = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
  "..",
  "..",
);
const chartIndexPath = resolve(
  repoRoot,
  "docs",
  "reference",
  "chart-index.md",
);

// The CANONICAL ChartType set the drift gate enforces. Must be
// hand-maintained 1:1 with the ChartType union at catalogue.ts (which
// cannot be reflected at runtime since TS types are erased). Adding a
// member here without a section-1 row + a feasibleAt() branch fails
// the gate. Same on the reverse direction.
const CHART_TYPES: readonly ChartType[] = [
  "choropleth",
  "choropleth-symbol",
  "matrix",
  "ranked",
  "stacked",
  "diverging",
  "line",
  "scatter",
  "dumbbell-dot",
  "dumbbell-arrow",
  "treemap",
  "circle-pack",
];

// The 9 DataShape literals from feasibleAt.ts. Mirrors the matrix row
// count in section 2 of chart-index.md.
const DATA_SHAPES: readonly DataShape[] = [
  "one-measure-over-geo-one-slice",
  "one-measure-over-geo-many-slices",
  "one-measure-named-series-over-time",
  "two-measures-joined-per-entity",
  "one-measure-split-by-facet",
  "part-to-whole-precise-compare",
  "magnitude-clusters-shallow-hierarchy",
  "start-end-pair-per-entity",
  "one-measure-over-geo-glyph-honest",
];

const defaultFeasibleInput = (
  over: Partial<FeasibleAtInput> = {},
): FeasibleAtInput => ({
  dataShape: "one-measure-over-geo-one-slice",
  grain: "state",
  geometryAvailable: true,
  hasFacet: false,
  hasTimeAxis: false,
  ...over,
});

interface Section1Row {
  num: string;
  renderer: string;
  machineId: string;
  thumb: string;
}

// Parse section 1's renderer table. Each row is:
//   | # | Renderer (mode) | Machine id | Thumb | ... |
// The 7-column shape includes long-format CSV shape, Use when, and
// Feasibility rule columns we do not consume here. Strips ALL
// backticks from cell content because section 1 may carry a backtick
// around just the renderer name (e.g. Matrix vs heatmap parenthetical)
// or around the whole renderer-mode form.
function parseSection1Rows(docSrc: string): Section1Row[] {
  const sec1Start = docSrc.search(/^##\s+1\.\s+The base set/m);
  const sec1aStart = docSrc.search(/^###\s+1a\./m);
  const sec1 = docSrc.slice(sec1Start, sec1aStart);
  const rows: Section1Row[] = [];
  for (const line of sec1.split("\n")) {
    const m = line.match(
      /^\|\s*(\d+(?:\s*\(opt\))?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|/,
    );
    if (!m) continue;
    rows.push({
      num: m[1].trim(),
      renderer: m[2].trim().replace(/`/g, ""),
      machineId: m[3].trim().replace(/`/g, ""),
      thumb: m[4].trim().replace(/`/g, ""),
    });
  }
  return rows;
}

// True for the (none yet) Machine id (the optional Radar row).
function isExemptMachineId(id: string): boolean {
  return id.startsWith("(");
}

// Parse section 2's matrix table. Returns each row as the list of
// encoding strings (the section-1 prose form, backticks stripped).
function parseSection2Rows(docSrc: string): string[][] {
  const sec2Start = docSrc.search(
    /^##\s+2\.\s+Data-shape\s+->\s+encoding matrix/m,
  );
  const sec3Start = docSrc.search(/^##\s+3\.\s+Forbidden encodings/m);
  const sec2 = docSrc.slice(sec2Start, sec3Start);
  const rows: string[][] = [];
  for (const line of sec2.split("\n")) {
    if (!/^\|.+\|.+\|.+\|/.test(line)) continue;
    if (/`time` cardinality/.test(line)) continue;
    if (/^\|\s*-+\s*\|/.test(line)) continue;
    const cells = line
      .split("|")
      .slice(1, -1)
      .map((c) => c.trim());
    if (cells.length < 3) continue;
    const encodingsCell = cells[cells.length - 1];
    const encodings = encodingsCell
      .split(",")
      .map((e) => e.trim())
      // Drop conditional parentheticals like (iff geometry).
      .map((e) => e.replace(/\s*\(.*?\)\s*$/, "").trim())
      // Drop trailing compositions like + TimeControl (treated as
      // policy notes, not separate encodings).
      .map((e) => e.replace(/\s*\+.*$/, "").trim())
      // Strip ALL backticks so lookup against the prose -> machine-id
      // map (which strips backticks from section-1 too) is symmetric.
      .map((e) => e.replace(/`/g, ""))
      .filter((e) => e.length > 0);
    rows.push(encodings);
  }
  return rows;
}

// Build the prose -> machine-id map FROM section 1. Section 1
// renderer names may carry a trailing parenthetical OR a
// brace-mode suffix like Matrix-heatmap or CirclePack-pack-bubble
// while section 2 may use a shorter bare form. Register all
// reasonable spellings so section-2 lookups stay tolerant.
function buildProseToMachineId(rows: Section1Row[]): Map<string, string> {
  const m = new Map<string, string>();
  for (const r of rows) {
    if (isExemptMachineId(r.machineId)) continue;
    const full = r.renderer;
    m.set(full, r.machineId);
    const withoutParen = full.replace(/\s*\([^)]*\)\s*$/, "").trim();
    if (withoutParen && withoutParen !== full) {
      m.set(withoutParen, r.machineId);
    }
    const braceMatch = withoutParen.match(/^([A-Za-z]+)\{([^}]+)\}$/);
    if (braceMatch) {
      const head = braceMatch[1];
      for (const mode of braceMatch[2].split(",").map((s) => s.trim())) {
        m.set(head + "{" + mode + "}", r.machineId);
      }
    }
  }
  return m;
}

describe("chart-index drift gate (LIVE doc parse - post-U4)", () => {
  const docSrc = readFileSync(chartIndexPath, "utf-8");

  it("declares the section-1 renderer table with Machine id column", () => {
    expect(docSrc).toMatch(/^##\s+1\.\s+The base set/m);
    expect(docSrc).toMatch(
      /\|\s*#\s*\|\s*Renderer \(mode\)\s*\|\s*Machine id\s*\|\s*Thumb\s*\|.*long-format CSV shape needed.*Use when.*Feasibility rule\s*\|/,
    );
  });

  it("declares the section-2 data-shape -> encoding matrix", () => {
    expect(docSrc).toMatch(/^##\s+2\.\s+Data-shape\s+->\s+encoding matrix/m);
    expect(docSrc).toMatch(
      /\|\s*Data shape \(after the query\)\s*\|\s*`time` cardinality\s*\|\s*Allowed encodings/,
    );
  });

  it("guarantees CategoryBar-ranked fallback in every matrix row", () => {
    const sec2Rows = parseSection2Rows(docSrc);
    expect(sec2Rows.length).toBeGreaterThanOrEqual(8);
    for (const row of sec2Rows) {
      expect(
        row,
        `matrix row missing the guaranteed CategoryBar-ranked fallback: ${row.join(", ")}`,
      ).toContain("CategoryBar{ranked}");
    }
  });

  it("declares the drift gate's three contract artifacts in section 4", () => {
    expect(docSrc).toMatch(/^##\s+4\.\s+Drift gate/m);
    expect(docSrc).toMatch(/`ChartType` union/);
    expect(docSrc).toMatch(/feasibleAt\(\)/);
  });
});

describe("chart-index drift gate (LIVE A x B x C contract - U4)", () => {
  const docSrc = readFileSync(chartIndexPath, "utf-8");
  const sec1Rows = parseSection1Rows(docSrc);
  const sec2Rows = parseSection2Rows(docSrc);
  const proseToMachineId = buildProseToMachineId(sec1Rows);

  it("section-1 lists at least one non-exempt row per ChartType member", () => {
    const docMachineIds = new Set(
      sec1Rows
        .map((r) => r.machineId)
        .filter((id) => !isExemptMachineId(id)),
    );
    for (const t of CHART_TYPES) {
      expect(
        docMachineIds.has(t),
        `ChartType "${t}" has no section-1 row in chart-index.md`,
      ).toBe(true);
    }
  });

  it("section-1 every non-exempt Machine id is a ChartType union member", () => {
    const unionSet = new Set<string>(CHART_TYPES);
    for (const r of sec1Rows) {
      if (isExemptMachineId(r.machineId)) continue;
      expect(
        unionSet.has(r.machineId),
        `section-1 row "${r.renderer}" carries Machine id "${r.machineId}" which is not a ChartType member`,
      ).toBe(true);
    }
  });

  it("section-1 has no duplicate Machine ids (excluding exempt rows)", () => {
    const seen = new Set<string>();
    for (const r of sec1Rows) {
      if (isExemptMachineId(r.machineId)) continue;
      expect(
        seen.has(r.machineId),
        `section-1 has duplicate Machine id "${r.machineId}"`,
      ).toBe(false);
      seen.add(r.machineId);
    }
  });

  it("section-2 every encoding resolves to a section-1 Machine id", () => {
    for (const encodings of sec2Rows) {
      for (const enc of encodings) {
        expect(
          proseToMachineId.has(enc),
          `matrix encoding "${enc}" has no matching section-1 renderer row`,
        ).toBe(true);
      }
    }
  });

  it("feasibleAt covers every DataShape with a non-empty result", () => {
    for (const shape of DATA_SHAPES) {
      const out = feasibleAt(defaultFeasibleInput({ dataShape: shape }));
      expect(
        out.length,
        `feasibleAt(${shape}) returned an empty list`,
      ).toBeGreaterThan(0);
    }
  });

  it("feasibleAt includes ranked in every branch (guaranteed fallback)", () => {
    for (const shape of DATA_SHAPES) {
      const out = feasibleAt(defaultFeasibleInput({ dataShape: shape }));
      expect(
        out,
        `feasibleAt(${shape}) missing the guaranteed ranked fallback`,
      ).toContain("ranked");
    }
  });

  it("feasibleAt only emits members of the ChartType union", () => {
    const unionSet = new Set<string>(CHART_TYPES);
    for (const shape of DATA_SHAPES) {
      const out = feasibleAt(defaultFeasibleInput({ dataShape: shape }));
      for (const t of out) {
        expect(
          unionSet.has(t),
          `feasibleAt(${shape}) emitted "${t}" which is not a ChartType member`,
        ).toBe(true);
      }
    }
  });

  it("intersectWithCatalogue is a pure list-shrinker preserving catalogue order", () => {
    const feasible = feasibleAt(
      defaultFeasibleInput({ dataShape: "one-measure-over-geo-one-slice" }),
    );
    expect(feasible).toEqual(["choropleth", "ranked"]);
    expect(
      intersectWithCatalogue(feasible, ["ranked", "choropleth", "treemap"]),
    ).toEqual(["ranked", "choropleth"]);
    expect(intersectWithCatalogue(feasible, ["treemap"])).toEqual([]);
  });
});
