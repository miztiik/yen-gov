import { describe, expect, it } from "vitest";
import {
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
          id: "energy/installed_mw_by_state",
          display: "Installed generation capacity (MW)",
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
  it("is election today (no live event window)", () => {
    expect(defaultHomeTheme(catalogue)).toEqual({ kind: "election" });
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
  it("returns 'leading party by state' for election", () => {
    expect(themeCaption({ kind: "election" }, catalogue)).toBe("leading party by state");
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
});

describe("homeThemeOptions", () => {
  it("starts with election, then lists every national indicator in catalogue order", () => {
    const opts = homeThemeOptions(catalogue);
    expect(opts.map(o => o.value)).toEqual([
      "election",
      "indicator/fiscal/outstanding_debt_pct_gsdp",
      "indicator/energy/installed_mw_by_state",
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
});
