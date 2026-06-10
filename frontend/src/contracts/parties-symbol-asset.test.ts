/**
 * G11 contract: parties.csv `symbol_asset` paths resolve to real assets.
 *
 * Plan row 28 (TODO/20260603-data-and-charting-platform-reset-plan.md
 * section 4 EL3): lift curator-verified election_symbol.asset_path from
 * datasets/taxonomy/parties.json into the symbol_asset column of
 * datasets/data/entities/parties.csv so the citizen UI can render the
 * ECI glyph alongside the PartyPill (plan section 25.3).
 *
 * Citizen-bundle invariant: every non-empty `symbol_asset` value must
 * resolve to a file under `frontend/public/`. A broken ref would
 * silently produce a 404 against the static GitHub Pages bundle (Holy
 * Law #1) the first time a citizen renders the party chip.
 *
 * Floor: at least 50 rows populated. Today the corpus carries 54
 * curator-verified entries (G11, 2026-06-09); the floor is two below
 * that so a single retirement does not break the contract.
 */
import { describe, expect, it } from "vitest";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { parseCsvLine } from "../lib/canonical/canonical-entity-translation";

const repoRoot = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
  "..",
);
const partiesCsvPath = resolve(
  repoRoot,
  "datasets/data/entities/parties.csv",
);
const publicDir = resolve(repoRoot, "frontend/public");

function loadPartiesRows(): Array<Record<string, string>> {
  const text = readFileSync(partiesCsvPath, "utf-8");
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  const header = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const cells = parseCsvLine(line);
    const row: Record<string, string> = {};
    for (let i = 0; i < header.length; i++) {
      row[header[i]] = cells[i] ?? "";
    }
    return row;
  });
}

describe("G11 parties.csv symbol_asset citizen-bundle invariant", () => {
  const rows = loadPartiesRows();
  const populated = rows.filter((r) => r.symbol_asset.length > 0);

  it("has at least 50 rows with a populated symbol_asset (floor)", () => {
    expect(populated.length).toBeGreaterThanOrEqual(50);
  });

  it("every populated symbol_asset resolves to a real file under frontend/public/", () => {
    const broken = populated
      .filter((r) => !existsSync(resolve(publicDir, r.symbol_asset)))
      .map((r) => ({ party_id: r.party_id, symbol_asset: r.symbol_asset }));
    expect(broken).toEqual([]);
  });
});

describe("PR-A placeholder + unverified glyph corpus", () => {
  // The renderer (PartySymbolGlyph + maplibre tooltip) opts into one of
  // these two neutral assets when a row carries an empty symbol_asset.
  // Asserting the files exist on disk keeps the citizen bundle honest:
  // a future PR cannot delete either without a contract-test failure.

  it("placeholder.svg exists at frontend/public/party-symbols/placeholder.svg", () => {
    const path = resolve(publicDir, "party-symbols", "placeholder.svg");
    expect(existsSync(path)).toBe(true);
  });

  it("unverified.svg exists at frontend/public/party-symbols/unverified.svg", () => {
    const path = resolve(publicDir, "party-symbols", "unverified.svg");
    expect(existsSync(path)).toBe(true);
  });
});
