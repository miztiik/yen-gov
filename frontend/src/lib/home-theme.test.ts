import { afterEach, describe, expect, it, vi } from "vitest";
import {
  dayOfYear,
  defaultHomeTheme,
  homeThemeOptions,
  parseHomeTheme,
  sameTheme,
  serializeHomeTheme,
  themeCaption,
  type HomeTheme,
} from "./home-theme";
import type { TopicCatalogue } from "./catalogue";

const catalogue: TopicCatalogue = {
  $schema: "https://example.test/topic-catalogue.schema.json",
  $schema_version: "1.1",
  sources: [],
  topics: [
    {
      id: "fiscal",
      title: "Money & debt",
      list: "concurrent",
      summary: "",
      artifacts: [
        {
          kind: "indicator",
          id: "fiscal/outstanding_debt_pct_gsdp",
          display: "Outstanding liabilities (% of GSDP)",
          scope: "national",
        },
        {
          // State-scope artifacts must NOT show up as theme options.
          kind: "indicator",
          id: "fiscal/state_only_thing",
          scope: "state",
        },
      ],
    },
    {
      id: "energy",
      title: "Power & energy",
      list: "concurrent",
      summary: "",
      artifacts: [
        {
          kind: "indicator",
          id: "energy/installed_capacity_renewable_mw",
          display: "Installed renewable capacity (MW)",
          // scope omitted ⇒ defaults to national
        },
        {
          // Election artifacts must NOT show up either.
          kind: "election",
          id: "AcGenMay2026",
          display: "Tamil Nadu Assembly · May 2026",
        },
      ],
    },
  ],
};

describe("parseHomeTheme", () => {
  it("returns null when ?theme is absent", () => {
    expect(parseHomeTheme("", catalogue)).toBeNull();
    expect(parseHomeTheme("?other=1", catalogue)).toBeNull();
  });

  it("returns null for empty / whitespace ?theme", () => {
    expect(parseHomeTheme("?theme=", catalogue)).toBeNull();
    expect(parseHomeTheme("?theme=%20%20", catalogue)).toBeNull();
  });

  it("parses ?theme=election", () => {
    expect(parseHomeTheme("?theme=election", catalogue)).toEqual({ kind: "election" });
  });

  it("parses ?theme=indicator/<id> when the catalogue knows the id", () => {
    expect(
      parseHomeTheme("?theme=indicator/fiscal/outstanding_debt_pct_gsdp", catalogue),
    ).toEqual({ kind: "indicator", id: "fiscal/outstanding_debt_pct_gsdp" });
  });

  it("rejects unknown indicator ids (returns null so caller falls back to default)", () => {
    expect(parseHomeTheme("?theme=indicator/fiscal/bogus", catalogue)).toBeNull();
  });

  it("rejects state-scope indicator ids (theme is national-scope only)", () => {
    expect(parseHomeTheme("?theme=indicator/fiscal/state_only_thing", catalogue)).toBeNull();
  });

  it("rejects election artifact ids (election theme is the dedicated 'election' value)", () => {
    expect(parseHomeTheme("?theme=indicator/AcGenMay2026", catalogue)).toBeNull();
  });

  it("rejects malformed values", () => {
    expect(parseHomeTheme("?theme=garbage", catalogue)).toBeNull();
    expect(parseHomeTheme("?theme=indicator/", catalogue)).toBeNull();
    expect(parseHomeTheme("?theme=Election", catalogue)).toBeNull(); // case-sensitive
  });

  it("accepts a URLSearchParams instance", () => {
    const p = new URLSearchParams({ theme: "election" });
    expect(parseHomeTheme(p, catalogue)).toEqual({ kind: "election" });
  });

  it("returns null for any indicator when the catalogue is null", () => {
    expect(parseHomeTheme("?theme=indicator/fiscal/outstanding_debt_pct_gsdp", null)).toBeNull();
  });

  it("still parses election even with a null catalogue", () => {
    expect(parseHomeTheme("?theme=election", null)).toEqual({ kind: "election" });
  });
});

describe("serializeHomeTheme", () => {
  it("returns '' for the default election theme (clean URL)", () => {
    expect(serializeHomeTheme({ kind: "election" })).toBe("");
  });

  it("returns indicator/<id> for indicator themes", () => {
    expect(
      serializeHomeTheme({ kind: "indicator", id: "fiscal/outstanding_debt_pct_gsdp" }),
    ).toBe("indicator/fiscal/outstanding_debt_pct_gsdp");
  });

  it("round-trips against parseHomeTheme for every option", () => {
    const opts = homeThemeOptions(catalogue);
    for (const o of opts) {
      const v = serializeHomeTheme(o.theme);
      const parsed = v === ""
        ? parseHomeTheme("", catalogue) ?? defaultHomeTheme(catalogue)
        : parseHomeTheme(`?theme=${v}`, catalogue);
      expect(parsed).toEqual(o.theme);
    }
  });
});

describe("defaultHomeTheme", () => {
  // PR-2 (2026-06-11): the default theme is no longer "always election".
  // It rotates by day-of-year across CURATED_DEFAULT_THEMES (5 indicators,
  // one per topic family) when at least 3 of them resolve to a national-scope
  // indicator in the live catalogue. Falls back to election otherwise.
  // Plan-doc: TODO/20260611-home-page-citizen-experience-plan.md row PR-2.
  //
  // Catalogue fixture with all 5 curated indicator ids present (national-scope).
  // Used by the "returns a curated indicator" test below and the
  // deterministic-rotation describe block.
  const fullCatalogue: TopicCatalogue = {
    $schema: "https://example.test/topic-catalogue.schema.json",
    $schema_version: "1.1",
    sources: [],
    topics: [
      {
        id: "fiscal",
        title: "Money & debt",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "fiscal/outstanding_debt_pct_gsdp",
            display: "Outstanding liabilities (% of GSDP)",
            scope: "national",
          },
        ],
      },
      {
        id: "economy",
        title: "Economy",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "economy/gdp_inr_crore",
            display: "GDP (INR crore)",
            scope: "national",
          },
        ],
      },
      {
        id: "prices",
        title: "Prices & inflation",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "prices/cpi_inflation_pct",
            display: "CPI inflation (%)",
            scope: "national",
          },
        ],
      },
      {
        id: "environment",
        title: "Environment",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "environment/india_ghg_emissions_mtco2e_by_sector",
            display: "India GHG emissions by sector",
            scope: "national",
          },
        ],
      },
      {
        id: "agriculture",
        title: "Farming & livestock",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "agriculture/pashu_aadhaar_count_cattle",
            display: "Pashu Aadhaar cattle count",
            scope: "national",
          },
        ],
      },
    ],
  };

  it("falls back to election when catalogue is null", () => {
    expect(defaultHomeTheme(null)).toEqual({ kind: "election" });
  });

  it("falls back to election when the curated pool collapses below 3 available indicators", () => {
    // Top-level `catalogue` fixture has only 1 of the 5 curated ids
    // (fiscal/outstanding_debt_pct_gsdp); the others are not curated or
    // are state-scope/election artifacts. Pool size 1 < 3 -> election.
    expect(defaultHomeTheme(catalogue)).toEqual({ kind: "election" });
  });

  it("returns a curated indicator when the catalogue has >= 3 curated ids", () => {
    const result = defaultHomeTheme(fullCatalogue);
    expect(result.kind).toBe("indicator");
    if (result.kind === "indicator") {
      expect([
        "fiscal/outstanding_debt_pct_gsdp",
        "economy/gdp_inr_crore",
        "prices/cpi_inflation_pct",
        "environment/india_ghg_emissions_mtco2e_by_sector",
        "agriculture/pashu_aadhaar_count_cattle",
      ]).toContain(result.id);
    }
  });
});

describe("dayOfYear", () => {
  // UTC dates so the test is TZ-independent (the function is UTC-based for
  // shareable rotation - see its doc comment).
  it("returns 1 for Jan 1 UTC", () => {
    expect(dayOfYear(new Date(Date.UTC(2026, 0, 1)))).toBe(1);
  });

  it("returns 182 for Jul 1 UTC in a non-leap year (31+28+31+30+31+30+1)", () => {
    expect(dayOfYear(new Date(Date.UTC(2026, 6, 1)))).toBe(182);
  });

  it("returns 365 for Dec 31 UTC in a non-leap year", () => {
    expect(dayOfYear(new Date(Date.UTC(2026, 11, 31)))).toBe(365);
  });

  it("returns 366 for Dec 31 UTC in a leap year (2024)", () => {
    expect(dayOfYear(new Date(Date.UTC(2024, 11, 31)))).toBe(366);
  });
});

describe("defaultHomeTheme deterministic rotation", () => {
  // The load-bearing oracle for PR-2: same calendar day -> identical id
  // (shareable + refresh-stable); different days within a year -> at
  // least 3 distinct curated ids appear (the rotation actually rotates).
  //
  // Catalogue fixture with all 5 curated indicator ids present so the
  // available pool === full CURATED_DEFAULT_THEMES and the modulo math
  // is exercised against the full set.
  const fullCatalogue: TopicCatalogue = {
    $schema: "https://example.test/topic-catalogue.schema.json",
    $schema_version: "1.1",
    sources: [],
    topics: [
      {
        id: "fiscal",
        title: "Money & debt",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "fiscal/outstanding_debt_pct_gsdp",
            scope: "national",
          },
        ],
      },
      {
        id: "economy",
        title: "Economy",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "economy/gdp_inr_crore",
            scope: "national",
          },
        ],
      },
      {
        id: "prices",
        title: "Prices & inflation",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "prices/cpi_inflation_pct",
            scope: "national",
          },
        ],
      },
      {
        id: "environment",
        title: "Environment",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "environment/india_ghg_emissions_mtco2e_by_sector",
            scope: "national",
          },
        ],
      },
      {
        id: "agriculture",
        title: "Farming & livestock",
        list: "concurrent",
        summary: "",
        artifacts: [
          {
            kind: "indicator",
            id: "agriculture/pashu_aadhaar_count_cattle",
            scope: "national",
          },
        ],
      },
    ],
  };

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns IDENTICAL output on repeated calls on the same frozen day (shareable + refresh-stable)", () => {
    vi.useFakeTimers();
    // 2026-03-15 UTC = Indian fiscal year-end-ish; meaningful baseline.
    vi.setSystemTime(new Date(Date.UTC(2026, 2, 15)));
    const a = defaultHomeTheme(fullCatalogue);
    const b = defaultHomeTheme(fullCatalogue);
    expect(a).toEqual(b);
    expect(a.kind).toBe("indicator");
  });

  it("returns a different curated indicator across day-deltas coprime with the curated pool size", () => {
    // Curated pool size is 5; pick deltas with idx mod 5 in {1, 2, 4} so
    // the three samples must hit three distinct ids no matter where the
    // base day lands in the rotation cycle. Day 100 % 5 == 0 (baseline);
    // day 101 % 5 == 1; day 102 % 5 == 2; day 104 % 5 == 4.
    vi.useFakeTimers();
    vi.setSystemTime(new Date(Date.UTC(2026, 0, 100)));
    const day_100 = defaultHomeTheme(fullCatalogue);
    vi.setSystemTime(new Date(Date.UTC(2026, 0, 101)));
    const day_101 = defaultHomeTheme(fullCatalogue);
    vi.setSystemTime(new Date(Date.UTC(2026, 0, 102)));
    const day_102 = defaultHomeTheme(fullCatalogue);
    expect(day_100.kind).toBe("indicator");
    expect(day_101.kind).toBe("indicator");
    expect(day_102.kind).toBe("indicator");
    if (
      day_100.kind === "indicator"
      && day_101.kind === "indicator"
      && day_102.kind === "indicator"
    ) {
      expect(day_101.id).not.toBe(day_100.id);
      expect(day_102.id).not.toBe(day_100.id);
      expect(day_102.id).not.toBe(day_101.id);
    }
  });

  it("sweeps all 5 distinct curated ids across 5 consecutive days (pool of size 5; one rotation cycle)", () => {
    // Consecutive day offsets guarantee idx 0..4 hit in order, so the set
    // of sampled ids has size == pool length.
    vi.useFakeTimers();
    const sampled_ids: string[] = [];
    for (const day_offset of [0, 1, 2, 3, 4]) {
      vi.setSystemTime(new Date(Date.UTC(2026, 5, 10 + day_offset)));
      const t = defaultHomeTheme(fullCatalogue);
      if (t.kind === "indicator") sampled_ids.push(t.id);
    }
    expect(sampled_ids.length).toBe(5);
    expect(new Set(sampled_ids).size).toBe(5);
  });

  it("falls back to election when the catalogue is null even under frozen time", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(Date.UTC(2026, 2, 15)));
    expect(defaultHomeTheme(null)).toEqual({ kind: "election" });
  });
});

describe("sameTheme", () => {
  it("compares by kind and id", () => {
    const a: HomeTheme = { kind: "election" };
    const b: HomeTheme = { kind: "indicator", id: "fiscal/x" };
    const c: HomeTheme = { kind: "indicator", id: "fiscal/x" };
    const d: HomeTheme = { kind: "indicator", id: "fiscal/y" };
    expect(sameTheme(a, a)).toBe(true);
    expect(sameTheme(a, b)).toBe(false);
    expect(sameTheme(b, c)).toBe(true);
    expect(sameTheme(b, d)).toBe(false);
  });
});

describe("themeCaption", () => {
  it("returns 'winning party by state' for election", () => {
    expect(themeCaption({ kind: "election" }, catalogue)).toBe("winning party by state");
  });

  it("returns the artifact display name for known indicators", () => {
    expect(
      themeCaption({ kind: "indicator", id: "fiscal/outstanding_debt_pct_gsdp" }, catalogue),
    ).toBe("Outstanding liabilities (% of GSDP)");
  });

  it("falls back to the bare id when the artifact has no display", () => {
    const cat: TopicCatalogue = {
      ...catalogue,
      topics: [
        {
          id: "x",
          title: "X",
          list: "concurrent",
          summary: "",
          artifacts: [{ kind: "indicator", id: "x/no_display", scope: "national" }],
        },
      ],
    };
    expect(themeCaption({ kind: "indicator", id: "x/no_display" }, cat)).toBe("x/no_display");
  });

  it("falls back to the id when the artifact is unknown to the catalogue", () => {
    expect(themeCaption({ kind: "indicator", id: "unknown/thing" }, catalogue)).toBe(
      "unknown/thing",
    );
  });

  it("prefers titleMap.get(artifact.id) over display when both present", () => {
    const titleMap = new Map([
      ["fiscal/outstanding_debt_pct_gsdp", "Public debt as a share of state output"],
    ]);
    expect(
      themeCaption(
        { kind: "indicator", id: "fiscal/outstanding_debt_pct_gsdp" },
        catalogue,
        titleMap,
      ),
    ).toBe("Public debt as a share of state output");
  });

  it("falls back to artifact.display when titleMap has no entry for the id", () => {
    const titleMap = new Map([["some/other", "Other"]]);
    expect(
      themeCaption(
        { kind: "indicator", id: "fiscal/outstanding_debt_pct_gsdp" },
        catalogue,
        titleMap,
      ),
    ).toBe("Outstanding liabilities (% of GSDP)");
  });

  it("uses titleMap entry even when the artifact is unknown to the catalogue", () => {
    const titleMap = new Map([["unknown/thing", "Some indicator title"]]);
    expect(
      themeCaption({ kind: "indicator", id: "unknown/thing" }, catalogue, titleMap),
    ).toBe("Some indicator title");
  });

  it("ignores titleMap for the election theme (its caption is fixed copy)", () => {
    const titleMap = new Map([["election", "should-not-appear"]]);
    expect(themeCaption({ kind: "election" }, catalogue, titleMap)).toBe(
      "winning party by state",
    );
  });
});

describe("homeThemeOptions", () => {
  it("starts with election, then lists every national indicator in catalogue order", () => {
    const opts = homeThemeOptions(catalogue);
    expect(opts.map(o => o.value)).toEqual([
      "election",
      "indicator/fiscal/outstanding_debt_pct_gsdp",
      "indicator/energy/installed_capacity_renewable_mw",
    ]);
  });

  it("groups by topic title (Elections + each topic's own title)", () => {
    const opts = homeThemeOptions(catalogue);
    const groups = opts.map(o => o.group);
    expect(groups).toEqual(["Elections", "Money & debt", "Power & energy"]);
  });

  it("excludes state-scope indicator artifacts", () => {
    const opts = homeThemeOptions(catalogue);
    expect(opts.some(o => o.value.endsWith("state_only_thing"))).toBe(false);
  });

  it("excludes election-kind artifacts (they're covered by the single 'election' theme)", () => {
    const opts = homeThemeOptions(catalogue);
    expect(opts.some(o => o.value.includes("AcGenMay2026"))).toBe(false);
  });

  it("returns just election when the catalogue is null", () => {
    const opts = homeThemeOptions(null);
    expect(opts).toHaveLength(1);
    expect(opts[0].theme).toEqual({ kind: "election" });
  });

  // IA-reset Step #3b: indicator labels are humanised from the
  // indicator artifact's own `indicator.title`, passed in via an
  // optional title-map. Raw slugs like "fiscal/outstanding_debt_pct_gsdp"
  // should never reach the dropdown when a title is available.
  describe("with titleMap (Step #3b humanised labels)", () => {
    it("prefers titleMap entry over artifact.display and id", () => {
      const titles = new Map<string, string>([
        ["fiscal/outstanding_debt_pct_gsdp", "Outstanding debt"],
        ["energy/installed_capacity_renewable_mw", "Installed capacity"],
      ]);
      const opts = homeThemeOptions(catalogue, titles);
      const fiscal = opts.find(o => o.value === "indicator/fiscal/outstanding_debt_pct_gsdp");
      const energy = opts.find(o => o.value === "indicator/energy/installed_capacity_renewable_mw");
      expect(fiscal?.label).toBe("Outstanding debt");
      expect(fiscal?.caption).toBe("Outstanding debt");
      expect(energy?.label).toBe("Installed capacity");
    });

    it("falls back to artifact.display when titleMap has no entry for that id", () => {
      const titles = new Map<string, string>(); // empty
      const opts = homeThemeOptions(catalogue, titles);
      // catalogue fixture sets display = "Outstanding liabilities (% of GSDP)"
      const fiscal = opts.find(o => o.value === "indicator/fiscal/outstanding_debt_pct_gsdp");
      expect(fiscal?.label).toBe("Outstanding liabilities (% of GSDP)");
    });

    it("falls back to the bare id when neither titleMap nor display is set", () => {
      const cat: TopicCatalogue = {
        ...catalogue,
        topics: [
          {
            id: "x",
            title: "X",
            list: "concurrent",
            summary: "",
            artifacts: [{ kind: "indicator", id: "x/no_display", scope: "national" }],
          },
        ],
      };
      const opts = homeThemeOptions(cat, new Map());
      const x = opts.find(o => o.value === "indicator/x/no_display");
      expect(x?.label).toBe("x/no_display");
    });

    it("does not touch the election entry's label (uses the ELECTION_LABEL constant)", () => {
      const titles = new Map<string, string>([["election", "Should be ignored"]]);
      const opts = homeThemeOptions(catalogue, titles);
      expect(opts[0].value).toBe("election");
      expect(opts[0].label).toBe("Winning party");
    });

    it("handles a null catalogue without crashing (returns just election)", () => {
      const opts = homeThemeOptions(null, new Map([["whatever", "x"]]));
      expect(opts).toHaveLength(1);
      expect(opts[0].label).toBe("Winning party");
    });
  });
});
