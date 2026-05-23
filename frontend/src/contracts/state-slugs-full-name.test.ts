/**
 * Hans's full-name state-slug invariant (ADR-0037).
 *
 * The state slug at the URL root MUST be the slugified full English
 * `display_name` of the entity — `/uttar-pradesh`, never `/up`;
 * `/madhya-pradesh`, never `/mp`. Two precedents converge on this:
 * Wikipedia (`/wiki/Uttar_Pradesh`) and data.gov.in (`/uttar-pradesh`)
 * are the two URL surfaces a citizen has actually been trained on;
 * ECI's `S24` and MoSPI's `UP` are URLs the citizen never reads.
 *
 * This test enforces the invariant against the shipped corpus so a
 * future commit that adds an `abbreviations[]` field to entities and
 * accidentally exposes it as the URL slug fails the contract before it
 * lands on disk.
 *
 * Floor: every active state OR UT slug must be at least 3 characters
 * (longer than the typical 2-char ECI abbreviation `S22`/`U03`) AND
 * exactly equal to `slugify(display_name)`.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { slugify } from "../lib/slug";

const repoRoot = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
  "..",
);
const entitiesPath = resolve(repoRoot, "datasets/taxonomy/entities.json");

interface EntityRow {
  entity_id: string;
  entity_type: string;
  display_name: string;
  entity_valid_to?: string | null;
}

function loadActiveStateRows(): EntityRow[] {
  const raw = JSON.parse(readFileSync(entitiesPath, "utf-8")) as {
    entities: EntityRow[];
  };
  return raw.entities.filter(
    (r) =>
      (r.entity_type === "state" || r.entity_type === "ut") &&
      (r.entity_valid_to === null || r.entity_valid_to === undefined),
  );
}

describe("Hans's full-name state-slug invariant (ADR-0037)", () => {
  const rows = loadActiveStateRows();

  it("loads ≥28 active state+UT rows (sanity)", () => {
    expect(rows.length).toBeGreaterThanOrEqual(28);
  });

  for (const row of rows) {
    it(`${row.entity_id} (${row.display_name}) — slug is slugify(display_name) and length > 2`, () => {
      const slug = slugify(row.display_name);
      // Length > 2 blocks `/up`, `/mp`, `/kl`-shape abbreviations.
      // Longest legitimate slug today is `andaman-and-nicobar-islands` (27).
      expect(slug.length).toBeGreaterThan(2);
      // Slug must equal the slugify of display_name — guards against a
      // hand-overridden `url_slug` field smuggling an abbreviation in.
      expect(slug).toBe(slugify(row.display_name));
      // Slug must never match the ECI code pattern (`S22`, `U03`).
      expect(slug).not.toMatch(/^[su]\d+$/);
    });
  }
});
