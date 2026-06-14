// PR-2 contract test for `datasets/taxonomy/methodology_breaks.json`.
//
// Asserts every row's `note` field is free of operator-narrative
// leaks (`PR-N of TODO/...md`, `lspc-delim-N`,
// `methodology_version=...`, "PR-N will render ...") AND that
// `cleanNote` is idempotent on each on-disk note (so the view-model
// fetch boundary in `party-detail.ts::pickLsMethodologyBreaks` is a
// safety net, not a string mutator).
//
// This is a Tier-A contract test: it runs on every commit and gates
// the citizen-facing tooltip from regressing into operator grammar.

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanNote } from "../lib/methodology/clean-note";

const repoRoot = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
  "..",
);
const methodologyBreaksPath = resolve(
  repoRoot,
  "datasets",
  "taxonomy",
  "methodology_breaks.json",
);

interface MethodologyBreakRow {
  methodology_version: string;
  note: string;
}
interface Catalogue {
  methodology_breaks: MethodologyBreakRow[];
}

function loadRows(): MethodologyBreakRow[] {
  const raw = readFileSync(methodologyBreaksPath, "utf-8");
  const cat = JSON.parse(raw) as Catalogue;
  return cat.methodology_breaks ?? [];
}

const LEAK_PATTERNS: { name: string; pattern: RegExp }[] = [
  { name: "PR-N reference", pattern: /\bPR-\d+\b/ },
  { name: "TODO/foo.md path", pattern: /\bTODO\/[\w./-]+\.md\b/ },
  { name: "lspc-delim-N identifier", pattern: /\blspc-delim-\d+\b/ },
  { name: "methodology_version=X token", pattern: /\bmethodology_version[:=]/ },
  { name: "'PR-N will render' sentence", pattern: /\bPR-\d+\s+will\s+/ },
  { name: "'PR-N of TODO/' sentence", pattern: /\bPR-\d+\s+of\s+TODO\// },
];

describe("methodology-tooltip-no-leaks contract", () => {
  const rows = loadRows();

  it("loads at least one methodology-break row from disk", () => {
    expect(rows.length).toBeGreaterThan(0);
  });

  describe.each(rows)(
    "row $methodology_version",
    ({ methodology_version, note }) => {
      it("has a non-empty note field", () => {
        expect(typeof note).toBe("string");
        expect(note.length).toBeGreaterThan(0);
      });

      it.each(LEAK_PATTERNS)(
        `note carries no operator-narrative leak: $name`,
        ({ pattern }) => {
          const match = note.match(pattern);
          expect(
            match,
            `methodology_version=${methodology_version} note matched ${pattern}: ${match?.[0] ?? ""}`,
          ).toBeNull();
        },
      );

      it("cleanNote is idempotent on this row (no mutation of on-disk text)", () => {
        const cleaned = cleanNote(note);
        expect(cleaned).toBe(note);
      });
    },
  );
});
