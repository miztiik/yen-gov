/**
 * Schema-level contract test for the `formation` column on
 * party_alliances.csv added by R6 of the state-event-page redesign
 * plan (2026-06-15).
 *
 * Reads the on-disk CSV header + every row and asserts:
 *
 *  1. The header carries exactly the 6 columns
 *     `[party_id, event_id, state, alliance, source_id, formation]`
 *     in that order (the additive minor bump on the file-class).
 *  2. Every row's `formation` value is one of
 *     `{ pre_poll, post_poll, hybrid, "" }` (empty = back-compat
 *     default = semantically pre_poll per the schema-of-schemas note).
 *  3. No row has fewer columns than the header (i.e. no row pre-dates
 *     the v2.5 bump and was forgotten in the migration).
 *
 * Doctrine: per Max + Hans verdict, the formation column is the
 * machine-readable axis for the AllianceTotals honesty caption.
 * Curator backfill of explicit pre_poll/post_poll/hybrid values is a
 * follow-up; empty here is the legal back-compat default.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const CSV_PATH = resolve(
  __dirname,
  "../../../../datasets/data/entities/party_alliances.csv",
);

const EXPECTED_HEADER = [
  "party_id",
  "event_id",
  "state",
  "alliance",
  "source_id",
  "formation",
];

const ALLOWED_FORMATION_VALUES = new Set([
  "pre_poll",
  "post_poll",
  "hybrid",
  "", // empty = back-compat default = semantically pre_poll
]);

function parseRows(): string[][] {
  const text = readFileSync(CSV_PATH, "utf8");
  return text
    .split(/\r?\n/)
    .filter((l) => l.length > 0)
    .map((l) => l.split(","));
}

describe("party_alliances.csv: formation column contract (R6)", () => {
  it("carries the 6-column header in the canonical order", () => {
    const rows = parseRows();
    expect(rows.length).toBeGreaterThan(0);
    expect(rows[0]).toEqual(EXPECTED_HEADER);
  });

  it("every data row matches the header column count (no orphans)", () => {
    const rows = parseRows();
    const offenders: number[] = [];
    for (let i = 1; i < rows.length; i++) {
      if (rows[i].length !== EXPECTED_HEADER.length) {
        offenders.push(i + 1);
      }
    }
    expect(
      offenders,
      `Rows with mismatched column count (line numbers): ${offenders.join(", ")}. ` +
        "R6 (TODO/20260615-state-election-event-page-redesign-plan.md) " +
        "added the trailing `formation` column; every existing row must " +
        "carry an empty 6th field (an additive minor schema bump).",
    ).toEqual([]);
  });

  it("every formation value is one of {pre_poll, post_poll, hybrid, empty}", () => {
    const rows = parseRows();
    const formationIdx = EXPECTED_HEADER.indexOf("formation");
    const offenders: { line: number; value: string }[] = [];
    for (let i = 1; i < rows.length; i++) {
      const value = (rows[i][formationIdx] ?? "").trim();
      if (!ALLOWED_FORMATION_VALUES.has(value)) {
        offenders.push({ line: i + 1, value });
      }
    }
    expect(
      offenders,
      `Rows with illegal formation values: ${JSON.stringify(offenders)}. ` +
        "Allowed: pre_poll / post_poll / hybrid / empty (back-compat).",
    ).toEqual([]);
  });
});
