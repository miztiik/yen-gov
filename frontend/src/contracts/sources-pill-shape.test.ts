// Contract test for the post-v3.1 sources pill view-model.
//
// This contract is the long-lived, low-churn guard for the new
// 5-col citation ledger + the dedupe-to-pills view-model. It mirrors
// the doctrine in `docs/concepts/data-provenance.md` (inline ADR
// `citation-ledger-5col`, 2026-06-11) and ratifies the on-disk schema
// at `datasets/data/_schema/columns.json::entities/source.csv`.
//
// Replaces a prior contract test that asserted the 11-col v2 ledger
// shape (the v2 render surface + helpers were retired in this PR-1).

import { describe, expect, it } from "vitest";
import {
  dedupeToPills,
  publisherDisplay,
  type PublisherPill,
  type SourceRow,
} from "../lib/sources";

describe("sources-pill contract", () => {
  it("SourceRow has exactly 5 declared fields", () => {
    // Round-trip a literal value to confirm the surface. TypeScript
    // already enforces this at compile time; the runtime check guards
    // against an accidental excess-property creep in the type.
    const row: SourceRow = {
      source_id: "src-deadbeef0001",
      producer: "Reserve Bank of India",
      title: "State Finances: A Study of Budgets",
      vintage: "2025-26",
      url: "https://rbi.org.in",
    };
    expect(Object.keys(row).sort()).toEqual([
      "producer",
      "source_id",
      "title",
      "url",
      "vintage",
    ]);
  });

  it("PublisherPill has exactly 4 declared fields", () => {
    const pill: PublisherPill = {
      label: "RBI",
      vintage_summary: "2025-26",
      url: "https://rbi.org.in",
      count: 1,
    };
    expect(Object.keys(pill).sort()).toEqual([
      "count",
      "label",
      "url",
      "vintage_summary",
    ]);
  });

  it("dedupeToPills returns empty array for empty input", () => {
    expect(dedupeToPills([])).toEqual([]);
  });

  it("dedupeToPills collapses multi-vintage same-(producer x series) input to one pill", () => {
    const pills = dedupeToPills([
      {
        source_id: "src-rbi-2024-25",
        producer: "Reserve Bank of India",
        title: "State Finances: A Study of Budgets",
        vintage: "2024-25",
        url: null,
      },
      {
        source_id: "src-rbi-2025-26",
        producer: "Reserve Bank of India",
        title: "State Finances: A Study of Budgets",
        vintage: "2025-26",
        url: "https://rbi.org.in",
      },
    ]);
    expect(pills).toHaveLength(1);
    expect(pills[0].label).toBe("RBI State Finances");
    expect(pills[0].vintage_summary).toBe("2024-25 to 2025-26");
    expect(pills[0].url).toBe("https://rbi.org.in");
    expect(pills[0].count).toBe(2);
  });

  it("publisherDisplay maps the 8 most common publishers compactly", () => {
    const expected: Record<string, string> = {
      "Reserve Bank of India": "RBI",
      "Election Commission of India": "ECI",
      "Ministry of Statistics and Programme Implementation": "MoSPI",
      "NITI Aayog India Climate & Energy Dashboard": "NITI ICED",
      "Central Electricity Authority": "CEA",
      "NITI Aayog": "NITI Aayog",
      "yen-gov": "yen-gov",
      Wikipedia: "Wikipedia",
    };
    for (const [producer, display] of Object.entries(expected)) {
      const mapped = publisherDisplay(producer);
      expect(mapped, `publisherDisplay(${producer})`).toBe(display);
      expect(mapped.length).toBeGreaterThanOrEqual(2);
      expect(mapped.length).toBeLessThanOrEqual(12);
    }
  });

  it("publisherDisplay falls back to raw producer string when unmapped", () => {
    // Forward-compatibility: a new ingest can add a publisher without
    // touching the display map; the pill renders the raw name as-is.
    const novel = "Election Department of XYZ State";
    expect(publisherDisplay(novel)).toBe(novel);
  });
});
