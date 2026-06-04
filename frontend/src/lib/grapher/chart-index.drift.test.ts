/**
 * Drift gate for the chart-index contract (plan section 20.9 + 21.9).
 *
 * The contract surface is THREE artifacts that MUST stay 1:1:
 *   (A) the `ChartType` union at frontend/src/lib/grapher/catalogue.ts
 *   (B) the renderer rows in section 1 of docs/reference/chart-index.md
 *   (C) the matrix rows in section 2 of docs/reference/chart-index.md,
 *       encoded as the pure function `feasibleAt()` (lands in chunk U4).
 *
 * This file is the sibling to catalogue.test.ts the plan calls for in
 * section 22.6 (gate name: `chart-drift-test`). At the D-DOC2 chunk
 * (this doc-only PR) the cross-checks against the `ChartType` union and
 * against `feasibleAt()` are TODO stubs: the union is still the legacy
 * 3-value form `"stacked-trend" | "ranked" | "choropleth"`, and
 * `feasibleAt()` does not exist yet. Both land together in chunk U4.
 *
 * Live today (one assertion): the chart-index doc is present, contains
 * the section-1 renderer table, the section-2 matrix table, and lists
 * `CategoryBar{ranked}` in EVERY matrix row (the guaranteed fallback
 * per plan section 23.5). That single assertion is enough to catch a
 * deletion or a structural rewrite of the contract before U4 lands.
 *
 * Per `/memories/lessons.md` ("vitest does NOT resolve the $lib
 * SvelteKit alias by default"), this file uses relative imports only.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

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

describe("chart-index drift gate (D-DOC2 LIVE assertions)", () => {
  const docSrc = readFileSync(chartIndexPath, "utf-8");

  it("declares the section-1 renderer table", () => {
    // The H2 anchor + the table header columns the doc commits to.
    expect(docSrc).toMatch(/^##\s+1\.\s+The base set/m);
    expect(docSrc).toMatch(
      /\|\s*#\s*\|\s*Renderer \(mode\)\s*\|\s*Thumb\s*\|.*long-format CSV shape needed.*Use when.*Feasibility rule\s*\|/,
    );
  });

  it("declares the section-2 data-shape -> encoding matrix", () => {
    expect(docSrc).toMatch(/^##\s+2\.\s+Data-shape\s+->\s+encoding matrix/m);
    expect(docSrc).toMatch(
      /\|\s*Data shape \(after the query\)\s*\|\s*`time` cardinality\s*\|\s*Allowed encodings/,
    );
  });

  it("guarantees `CategoryBar{ranked}` fallback in every matrix row", () => {
    // Slice the doc to section 2 only so we do not accidentally count
    // the renderer table (which already names `CategoryBar{ranked}`
    // on row 4) or the prose that follows.
    const sec2Start = docSrc.search(
      /^##\s+2\.\s+Data-shape\s+->\s+encoding matrix/m,
    );
    const sec3Start = docSrc.search(/^##\s+3\.\s+Forbidden encodings/m);
    expect(sec2Start).toBeGreaterThan(-1);
    expect(sec3Start).toBeGreaterThan(sec2Start);
    const sec2 = docSrc.slice(sec2Start, sec3Start);

    // Data rows of the matrix: lines that look like
    // `| <shape> | <time> | <encodings> |`. Skip the header (the row
    // whose 2nd cell is literally "`time` cardinality") and the
    // separator (the row of dashes).
    const dataRows = sec2
      .split("\n")
      .filter((line) => /^\|.+\|.+\|.+\|/.test(line))
      .filter((line) => !/`time` cardinality/.test(line))
      .filter((line) => !/^\|\s*-+\s*\|/.test(line));

    expect(dataRows.length).toBeGreaterThanOrEqual(8);
    for (const row of dataRows) {
      expect(
        row,
        `matrix row missing the guaranteed CategoryBar{ranked} fallback: ${row}`,
      ).toMatch(/CategoryBar\{ranked\}/);
    }
  });

  it("declares the drift gate's three contract artifacts in section 4", () => {
    expect(docSrc).toMatch(/^##\s+4\.\s+Drift gate/m);
    expect(docSrc).toMatch(/`ChartType` union/);
    expect(docSrc).toMatch(/feasibleAt\(\)/);
  });
});

describe("chart-index drift gate (D-DOC2 TODO stubs - land with U4)", () => {
  // These three assertions are the post-U4 contract surface. They
  // depend on (a) the widened `ChartType` union and (b) the
  // `feasibleAt()` pure function, both of which land in chunk U4.
  // Keeping them as `it.todo` makes the intent visible to any agent
  // reading this file without producing false-green pass output.

  it.todo(
    "every `ChartType` union member has exactly one section-1 renderer row",
  );

  it.todo(
    "every section-1 renderer row appears as a `ChartType` union member",
  );

  it.todo(
    "every encoding listed in a section-2 matrix row resolves to a renderer row in section 1 and a `feasibleAt()` branch",
  );
});
