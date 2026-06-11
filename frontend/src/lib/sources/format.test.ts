import { describe, expect, it } from "vitest";
import {
  dedupeToPills,
  publisherDisplay,
  seriesFamily,
  summarizeVintages,
} from "./format";
import type { SourceRow } from "./types";

describe("publisherDisplay", () => {
  it("maps known publishers to their compact abbreviation", () => {
    expect(publisherDisplay("Reserve Bank of India")).toBe("RBI");
    expect(publisherDisplay("Election Commission of India")).toBe("ECI");
    expect(publisherDisplay("Ministry of Statistics and Programme Implementation")).toBe(
      "MoSPI",
    );
    expect(publisherDisplay("NITI Aayog India Climate & Energy Dashboard")).toBe(
      "NITI ICED",
    );
    expect(publisherDisplay("Central Electricity Authority")).toBe("CEA");
  });

  it("returns the raw producer string when unmapped", () => {
    expect(publisherDisplay("Some New Publisher")).toBe("Some New Publisher");
    expect(publisherDisplay("TCPD")).toBe("TCPD");
  });

  it("trims leading/trailing whitespace before lookup", () => {
    expect(publisherDisplay("  Reserve Bank of India  ")).toBe("RBI");
  });

  it("Wikipedia and yen-gov are passed through as themselves", () => {
    expect(publisherDisplay("Wikipedia")).toBe("Wikipedia");
    expect(publisherDisplay("yen-gov")).toBe("yen-gov");
  });
});

describe("seriesFamily", () => {
  it("strips everything from the first colon onward", () => {
    expect(seriesFamily("State Finances: A Study of Budgets")).toBe("State Finances");
  });

  it("strips everything from em-dash-with-spaces onward", () => {
    expect(
      seriesFamily(
        "Statistical Report Section 10 (Detailed Results) \u2014 Tamil Nadu AcGenMay2026",
      ),
    ).toBe("Statistical Report Section 10 (Detailed Results)");
  });

  it("strips everything from hyphen-with-spaces onward", () => {
    expect(
      seriesFamily("General Election to Lok Sabha 2009 - Constituency-wise candidate results"),
    ).toBe("General Election to Lok Sabha 2009");
  });

  it("returns the whole title when no separator is present", () => {
    expect(seriesFamily("Handbook of Statistics on the Indian Economy 2024-25")).toBe(
      "Handbook of Statistics on the Indian Economy 2024-25",
    );
    expect(seriesFamily("List of Chief Ministers of Tripura")).toBe(
      "List of Chief Ministers of Tripura",
    );
  });

  it("trims whitespace and handles edge cases", () => {
    expect(seriesFamily("  State Finances: stuff  ")).toBe("State Finances");
    expect(seriesFamily("")).toBe("");
  });

  it("prefers earliest separator when multiple are present", () => {
    expect(seriesFamily("Foo: Bar \u2014 Baz")).toBe("Foo");
    expect(seriesFamily("Foo - Bar: Baz")).toBe("Foo");
  });
});

describe("summarizeVintages", () => {
  it("returns empty string when input is empty", () => {
    expect(summarizeVintages([])).toBe("");
  });

  it("returns empty string when all entries are empty/whitespace", () => {
    expect(summarizeVintages(["", "  ", ""])).toBe("");
  });

  it("returns the single vintage when only one distinct non-empty entry", () => {
    expect(summarizeVintages(["2025-26"])).toBe("2025-26");
    expect(summarizeVintages(["2025-26", "2025-26", "2025-26"])).toBe("2025-26");
    expect(summarizeVintages(["2025-26", "", "2025-26"])).toBe("2025-26");
  });

  it("names the span when exactly two distinct vintages", () => {
    expect(summarizeVintages(["2024-25", "2025-26"])).toBe("2024-25 to 2025-26");
    expect(summarizeVintages(["2025-26", "2024-25"])).toBe("2024-25 to 2025-26");
  });

  it("returns 'various' when 3+ distinct vintages", () => {
    expect(summarizeVintages(["2022-23", "2024-25", "2025-26"])).toBe("various");
  });

  it("trims whitespace inside vintage strings", () => {
    expect(summarizeVintages(["  2025-26  ", "2025-26"])).toBe("2025-26");
  });
});

describe("dedupeToPills", () => {
  function row(producer: string, title: string, vintage: string, url: string | null = null): SourceRow {
    return { source_id: `src-${producer}-${vintage}`, producer, title, vintage, url };
  }

  it("returns empty array for empty input", () => {
    expect(dedupeToPills([])).toEqual([]);
  });

  it("renders single row as one pill with publisher + series + vintage", () => {
    const pills = dedupeToPills([
      row("Reserve Bank of India", "State Finances: A Study of Budgets", "2025-26", "https://rbi.org.in"),
    ]);
    expect(pills).toEqual([
      {
        label: "RBI State Finances",
        vintage_summary: "2025-26",
        url: "https://rbi.org.in",
        count: 1,
      },
    ]);
  });

  it("collapses multiple rows of same (producer x series_family) to one pill", () => {
    const pills = dedupeToPills([
      row(
        "Election Commission of India",
        "Statistical Report Section 10 (Detailed Results) \u2014 Tamil Nadu AcGenMay2026",
        "AcGenMay2026",
      ),
      row(
        "Election Commission of India",
        "Statistical Report Section 10 (Detailed Results) \u2014 Karnataka AcGenMay2023",
        "AcGenMay2023",
      ),
    ]);
    expect(pills).toHaveLength(1);
    expect(pills[0].count).toBe(2);
    // 'ECI Statistical Report Section 10 (Detailed Results)' = 52 chars, over budget,
    // so the label falls back to just 'ECI'.
    expect(pills[0].label).toBe("ECI");
    expect(pills[0].vintage_summary).toBe("AcGenMay2023 to AcGenMay2026");
  });

  it("keeps separate pills for different series under same publisher", () => {
    const pills = dedupeToPills([
      row("Reserve Bank of India", "State Finances: A Study of Budgets", "2025-26"),
      row("Reserve Bank of India", "Handbook of Statistics on Indian States", "2024-25"),
    ]);
    expect(pills).toHaveLength(2);
    expect(pills.map((p) => p.label).sort()).toEqual([
      "RBI",
      "RBI State Finances",
    ]);
  });

  it("falls back to publisher-only when label budget exceeded", () => {
    const pills = dedupeToPills([
      row(
        "Wikipedia",
        "List of Chief Ministers of Tripura",
        "",
        "https://en.wikipedia.org/wiki/List_of_chief_ministers_of_Tripura",
      ),
    ]);
    // 'Wikipedia List of Chief Ministers of Tripura' = 44 chars, over budget.
    expect(pills[0].label).toBe("Wikipedia");
    expect(pills[0].vintage_summary).toBe("");
    expect(pills[0].url).toBe("https://en.wikipedia.org/wiki/List_of_chief_ministers_of_Tripura");
  });

  it("returns null url when all contributing rows have empty url", () => {
    const pills = dedupeToPills([
      row("Election Commission of India", "Statistical Report Section 10", "AcGenMay2026", null),
      row("Election Commission of India", "Statistical Report Section 10", "AcGenMay2023", ""),
    ]);
    expect(pills[0].url).toBeNull();
  });

  it("picks first non-empty url across contributing rows", () => {
    const pills = dedupeToPills([
      row("Reserve Bank of India", "Bulletin Appendix", "2025-26", null),
      row("Reserve Bank of India", "Bulletin Appendix", "2024-25", "https://rbi.org.in/x"),
    ]);
    expect(pills[0].url).toBe("https://rbi.org.in/x");
  });

  it("sorts pills by count desc, then label asc", () => {
    const pills = dedupeToPills([
      row("Reserve Bank of India", "State Finances", "2025-26"),
      row("Election Commission of India", "Statistical Report Section 10 \u2014 X", "v1"),
      row("Election Commission of India", "Statistical Report Section 10 \u2014 Y", "v2"),
      row("Election Commission of India", "Statistical Report Section 10 \u2014 Z", "v3"),
    ]);
    // ECI has 3 contributing rows, RBI has 1. ECI should sort first.
    expect(pills.map((p) => p.label)).toEqual(["ECI", "RBI State Finances"]);
  });

  it("handles title with no separator gracefully", () => {
    const pills = dedupeToPills([
      row("yen-gov", "Editorial framing for derived rollup", "2026-06"),
    ]);
    expect(pills[0].label).toBe("yen-gov");
    expect(pills[0].vintage_summary).toBe("2026-06");
  });

  it("preserves the publisher's raw name for unmapped producers", () => {
    const pills = dedupeToPills([
      row("Some State Department", "Annual Report 2024", "2024", "https://example.gov.in"),
    ]);
    // 'Some State Department Annual Report 2024' = 40 chars, over budget.
    expect(pills[0].label).toBe("Some State Department");
  });

  it("series_family equal to publisher abbreviation collapses to publisher only", () => {
    // Edge case: if some weirdly-shaped row has series_family that matches
    // the publisher's display name, don't duplicate it in the label.
    const pills = dedupeToPills([
      row("Reserve Bank of India", "RBI: Annual Report", "2025-26"),
    ]);
    expect(pills[0].label).toBe("RBI");
  });
});
