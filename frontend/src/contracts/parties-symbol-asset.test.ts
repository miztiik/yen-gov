/**
 * parties.csv `symbol_asset` paths must resolve in the static bundle.
 *
 * This is a deployability contract, not a coverage claim: any populated
 * `symbol_asset` value is a URL the citizen site can request, so it must
 * point at a real file under `frontend/public/`.
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

describe("parties.csv symbol_asset paths are deployable", () => {
  const rows = loadPartiesRows();
  const populated = rows.filter((r) => r.symbol_asset.length > 0);

  it("every non-empty symbol_asset resolves under frontend/public/", () => {
    const broken = populated
      .filter((r) => !existsSync(resolve(publicDir, r.symbol_asset)))
      .map((r) => ({ party_id: r.party_id, symbol_asset: r.symbol_asset }));
    expect(broken).toEqual([]);
  });
});

describe("fallback party-symbol assets are deployable", () => {
  it("placeholder.svg exists at frontend/public/party-symbols/placeholder.svg", () => {
    const path = resolve(publicDir, "party-symbols", "placeholder.svg");
    expect(existsSync(path)).toBe(true);
  });

  it("unverified.svg exists at frontend/public/party-symbols/unverified.svg", () => {
    const path = resolve(publicDir, "party-symbols", "unverified.svg");
    expect(existsSync(path)).toBe(true);
  });
});
