// Vitest unit for `IndicatorDoc.svelte`'s pure module-scope helpers
// (`cadenceLabel` + `projectToFourFieldSource`). Mirrors the U5a /
// U2a pattern: the helpers are exported from a `<script lang="ts"
// module>` block so vitest can cover them without a DOM mount.
//
// Imports come directly from the .svelte file's module-block exports;
// vite-plugin-svelte resolves the module block as a normal TS module.
// No jsdom, no Svelte runtime - this is leaf-helper testing.

import { describe, it, expect } from "vitest";
import {
  cadenceLabel,
  projectToFourFieldSource,
} from "./IndicatorDoc.svelte";
import type {
  IndicatorMeta,
  IndicatorMethodology,
  IndicatorSource,
} from "../lib/indicators";

describe("cadenceLabel", () => {
  it.each([
    ["annual", "Annual"],
    ["annual_fy", "Annual (financial year)"],
    ["annual_cy", "Annual (calendar year)"],
    ["quarterly", "Quarterly"],
    ["quarterly_fy", "Quarterly (financial year)"],
    ["quarterly_cy", "Quarterly (calendar year)"],
    ["monthly", "Monthly"],
    ["weekly", "Weekly"],
    ["daily", "Daily"],
    ["decennial", "Decennial (every 10 years)"],
    ["ad_hoc", "Ad hoc (no regular schedule)"],
  ])("maps controlled-vocab '%s' to citizen-readable '%s'", (input, label) => {
    expect(cadenceLabel(input)).toBe(label);
  });

  it("returns 'Not declared' when cadence is null", () => {
    expect(cadenceLabel(null)).toBe("Not declared");
  });

  it("returns 'Not declared' when cadence is undefined", () => {
    expect(cadenceLabel(undefined)).toBe("Not declared");
  });

  it("returns 'Not declared' when cadence is empty string", () => {
    expect(cadenceLabel("")).toBe("Not declared");
  });

  it("falls through unknown vocabulary terms as-is (forward-compat)", () => {
    // A future ingest may introduce a cadence string the frontend
    // doesn't yet recognise; we surface it verbatim rather than
    // silently dropping it (Holy Law: never lose publisher signal).
    expect(cadenceLabel("biennial")).toBe("biennial");
    expect(cadenceLabel("sub_annual_unscheduled")).toBe("sub_annual_unscheduled");
  });
});

describe("projectToFourFieldSource", () => {
  // Minimal helpers to build the shapes the function consumes. We don't
  // need every field on IndicatorMeta / IndicatorMethodology - only the
  // fields the projection reads.
  function source(overrides: Partial<IndicatorSource> = {}): IndicatorSource {
    return {
      url: "https://example.gov.in/dataset",
      fetched_at: "2026-05-11T15:18:58Z",
      ...overrides,
    };
  }

  function methodology(
    overrides: Partial<IndicatorMethodology> = {},
  ): IndicatorMethodology {
    return {
      definition: "stub",
      publisher: "RBI",
      documentation_status: "authored",
      methodology_breaks: [],
      known_caveats: [],
      notes: [],
      ...overrides,
    };
  }

  function meta(overrides: Partial<IndicatorMeta> = {}): IndicatorMeta {
    return {
      id: "fiscal/outstanding_debt_pct_gsdp",
      title: "Outstanding liabilities (% of GSDP)",
      entity_kind: "state",
      time_grain: "fiscal_year",
      value_kind: "share",
      direction: "lower_is_better",
      unit: "%",
      ...overrides,
    };
  }

  it("owner falls back to methodology.publisher when present", () => {
    const out = projectToFourFieldSource(source(), methodology(), meta());
    expect(out.owner).toBe("RBI");
  });

  it("owner falls back to source.authority when methodology.publisher absent", () => {
    const out = projectToFourFieldSource(
      source({ authority: "Ministry of Statistics" }),
      null,
      meta(),
    );
    expect(out.owner).toBe("Ministry of Statistics");
  });

  it("owner is null when neither methodology.publisher nor source.authority is set", () => {
    const out = projectToFourFieldSource(source(), null, meta());
    expect(out.owner).toBeNull();
  });

  it("title prefers source.name when set", () => {
    const out = projectToFourFieldSource(
      source({ name: "State Finances: A Study of Budgets" }),
      methodology(),
      meta(),
    );
    expect(out.title).toBe("State Finances: A Study of Budgets");
  });

  it("title falls back to URL hostname when source.name absent", () => {
    const out = projectToFourFieldSource(
      source({ url: "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/20_ST2301202696AC652FC4CE482EAAD928FC544CD86A.XLSX" }),
      methodology(),
      meta(),
    );
    expect(out.title).toBe("rbidocs.rbi.org.in");
  });

  it("title is null when URL is unparseable and no name is provided", () => {
    const out = projectToFourFieldSource(
      // The IndicatorSource type insists url is a string; pass a
      // malformed value the URL constructor will reject.
      source({ url: "not-a-url" }),
      methodology(),
      meta(),
    );
    expect(out.title).toBeNull();
  });

  it("vintage prefers indicator.methodology_vintage (the publisher edition) when set", () => {
    const out = projectToFourFieldSource(
      source(),
      methodology(),
      meta({ methodology_vintage: "RBI State Finances 2025-26 edition" }),
    );
    expect(out.vintage).toBe("RBI State Finances 2025-26 edition");
  });

  it("vintage falls back to source.fetched_at (operator snapshot window) otherwise", () => {
    const out = projectToFourFieldSource(
      source({ fetched_at: "2026-05-11T15:18:58Z" }),
      methodology(),
      meta(),
    );
    expect(out.vintage).toBe("2026-05-11T15:18:58Z");
  });

  it("vintage is null when neither methodology_vintage nor fetched_at is set", () => {
    const out = projectToFourFieldSource(
      // fetched_at is required by IndicatorSource's TS shape; null
      // here exercises the projection's null-safety path.
      { url: "https://example.gov.in", fetched_at: null as unknown as string },
      methodology(),
      meta(),
    );
    expect(out.vintage).toBeNull();
  });

  it("url passes through source.url verbatim", () => {
    const out = projectToFourFieldSource(
      source({ url: "https://example.gov.in/foo/bar.xlsx" }),
      methodology(),
      meta(),
    );
    expect(out.url).toBe("https://example.gov.in/foo/bar.xlsx");
  });
});
