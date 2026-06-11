// Unit tests for the StackedTrendV2 export helper (Phase 2.7).
//
// Covers every pure helper in `./export.ts` plus the SVG-builder
// invariants: well-formed XML envelope, correct viewBox, all bars
// present, every visible category in the legend, provenance footer
// present, hostile input escaped.
//
// Runs in node (no jsdom). "Well-formed XML" is checked via a tiny
// hand-rolled `<`/`>` and `<tag>...</tag>` balance walk rather than
// importing a DOM parser dep — that would bloat the dev image just
// to assert one invariant a regex can handle.

import { describe, expect, it } from "vitest";
import minimalFixture from "./__fixtures__/minimal.fixture.json";
import {
  buildExportFilename,
  buildExportSvg,
  composeCitation,
  EXPORT_HEIGHT_PX,
  EXPORT_WIDTH_PX,
  escapeSvgText,
  exportFillFor,
  exportFmtValue,
  exportLabelFor,
  pickPrimarySource,
} from "./export";
import { StackedTrendV2Model, type StackedTrendV2Source } from "./types";

const model = StackedTrendV2Model.parse(minimalFixture);

describe("escapeSvgText", () => {
  it("escapes the five XML-significant characters", () => {
    expect(escapeSvgText(`<a b="c" d='e'>&f</a>`)).toBe(
      `&lt;a b=&quot;c&quot; d=&apos;e&apos;&gt;&amp;f&lt;/a&gt;`,
    );
  });
  it("passes through plain text unchanged", () => {
    expect(escapeSvgText("Coal share 62%")).toBe("Coal share 62%");
  });
});

describe("exportFillFor", () => {
  it("returns the category's explicit fill when present", () => {
    expect(exportFillFor("coal", model)).toBe("#374151");
  });
  it("returns the fixed grey for the __OTHER__ collapsed bucket", () => {
    expect(exportFillFor("__OTHER__", model)).toBe("#9ca3af");
  });
  it("falls back to slate-500 for unknown categories", () => {
    expect(exportFillFor("nonexistent", model)).toBe("#64748b");
  });
});

describe("exportLabelFor", () => {
  it("returns the category's explicit label", () => {
    expect(exportLabelFor("coal", model)).toBe("Coal");
  });
  it("returns 'Other' for the __OTHER__ bucket", () => {
    expect(exportLabelFor("__OTHER__", model)).toBe("Other");
  });
  it("falls back to the raw id when no category row matches", () => {
    expect(exportLabelFor("nonexistent", model)).toBe("nonexistent");
  });
});

describe("exportFmtValue", () => {
  it("renders share values as percent with one decimal", () => {
    const shareModel = { ...model, unit: { ...model.unit, value_kind: "share" as const } };
    expect(exportFmtValue(0.621, shareModel)).toBe("62.1%");
  });
  it("renders ≥1000 in 'k <unit>' form", () => {
    expect(exportFmtValue(1234, model)).toBe("1.2k TWh");
  });
  it("renders <1000 with no decimal + unit label", () => {
    expect(exportFmtValue(42, model)).toBe("42 TWh");
  });
});

describe("pickPrimarySource", () => {
  it("returns the first source in model.sources", () => {
    const picked = pickPrimarySource(model);
    expect(picked?.label).toContain("CEA");
  });
  it("falls back to a non-CEA source when CEA is absent", () => {
    const onlyIndiastat: StackedTrendV2Source[] = [
      {
        label: "Indiastat Power",
        vintage_summary: "2024",
        url: "https://www.indiastat.com",
        count: 1,
      },
    ];
    const picked = pickPrimarySource({ ...model, sources: onlyIndiastat });
    expect(picked?.label).toContain("Indiastat");
  });
  it("returns null when no sources are present", () => {
    expect(pickPrimarySource({ ...model, sources: [] })).toBeNull();
  });
});

describe("composeCitation", () => {
  it("composes '<label> (<vintage_summary>)' for a pill with a vintage", () => {
    const s: StackedTrendV2Source = {
      label: "CEA Executive Summary",
      vintage_summary: "Monthly 2024-25",
      url: null,
      count: 1,
    };
    expect(composeCitation(s)).toBe(
      "CEA Executive Summary (Monthly 2024-25)",
    );
  });
  it("omits the vintage trailer when vintage_summary is empty", () => {
    const s: StackedTrendV2Source = {
      label: "Custom",
      vintage_summary: "",
      url: null,
      count: 1,
    };
    expect(composeCitation(s)).toBe("Custom");
  });
});

describe("buildExportFilename", () => {
  it("slugifies the headline + mode + period window into a safe SVG filename", () => {
    const name = buildExportFilename(model, "percent");
    expect(name).toMatch(/^coal-share-falls-below.*_percent_fy2022-23-fy2024-25\.svg$/);
  });
  it("uses the dimension when no headline is set", () => {
    const noHeadline = { ...model, headline: undefined };
    const name = buildExportFilename(noHeadline, "absolute");
    expect(name).toBe("fuel-type_absolute_fy2022-23-fy2024-25.svg");
  });
  it("collapses to a single period when start == end", () => {
    const onePeriod = {
      ...model,
      bars: [model.bars[0]!],
    };
    const name = buildExportFilename(onePeriod, "percent");
    expect(name).toMatch(/_fy2022-23\.svg$/);
    expect(name).not.toMatch(/_fy2022-23-fy2022-23/);
  });
});

describe("buildExportSvg", () => {
  const svg = buildExportSvg(model, { mode: "percent" });

  it("emits a well-formed standalone SVG document", () => {
    expect(svg.startsWith("<?xml")).toBe(true);
    expect(svg).toContain('xmlns="http://www.w3.org/2000/svg"');
    expect(svg.trimEnd().endsWith("</svg>")).toBe(true);
  });

  it("uses the configured pixel-accurate viewBox", () => {
    expect(svg).toContain(`viewBox="0 0 ${EXPORT_WIDTH_PX} ${EXPORT_HEIGHT_PX}"`);
  });

  it("parses as well-formed XML (angle-bracket-balanced + every open tag closes)", () => {
    expect(isWellFormedXml(svg)).toBe(true);
  });

  it("renders the headline as the title text", () => {
    expect(svg).toContain(
      "Coal share falls below 60% for the first time in the visible window.",
    );
  });

  it("renders the mode label in the subtitle", () => {
    expect(svg).toContain("Share");
  });

  it("renders each visible category in the legend", () => {
    expect(svg).toContain(">Coal<");
    expect(svg).toContain(">Solar<");
    expect(svg).toContain(">Wind<");
    expect(svg).toContain(">Hydro<");
    expect(svg).toContain(">Other<");
  });

  it("renders every bar period label", () => {
    expect(svg).toContain(">2022-23<");
    expect(svg).toContain(">2023-24<");
    expect(svg).toContain(">2024-25<");
  });

  it("renders the first source pill in the footer", () => {
    expect(svg).toContain("CEA Executive Summary");
    expect(svg).toContain("Monthly 2024-25");
    expect(svg).not.toContain("Indiastat"); // second pill, not picked
  });

  it("emits at least one <rect> per present segment", () => {
    const rectCount = (svg.match(/<rect /g) ?? []).length;
    // 1 background + 14 present segments + 1 missing cap + 5 legend chips = 21 minimum
    expect(rectCount).toBeGreaterThanOrEqual(20);
  });

  it("absolute mode toggles to 'Total' in the subtitle", () => {
    const absSvg = buildExportSvg(model, { mode: "absolute" });
    expect(absSvg).toContain("Total");
    expect(absSvg).not.toContain("Share ·");
  });

  it("escapes user-controlled headline text so XML stays well-formed", () => {
    const sneaky = {
      ...model,
      headline: {
        ...model.headline!,
        text: `<script>alert("x")</script>`,
      },
    };
    const out = buildExportSvg(sneaky, { mode: "percent" });
    expect(out).not.toContain(`<script>`);
    expect(out).toContain("&lt;script&gt;");
    // Document still passes the angle-balance + tag-closure check.
    expect(isWellFormedXml(out)).toBe(true);
  });

  it("falls back gracefully when sources is empty", () => {
    const noSources = { ...model, sources: [] };
    const out = buildExportSvg(noSources, { mode: "percent" });
    expect(out).toContain("Source · (not specified)");
  });
});

// ---------------------------------------------------------------------
// Tiny well-formed-XML checker (no jsdom dep).
//
// Tokenises the document into open / close / self-closing tags and the
// XML declaration, then walks the stack to confirm every open tag
// closes in LIFO order. Skips text content (declared safe by
// `escapeSvgText`). Sufficient for the asserts above; not a substitute
// for a full XML parser.
// ---------------------------------------------------------------------

function isWellFormedXml(doc: string): boolean {
  const stack: string[] = [];
  // Match: <?xml...?>  |  <tag .../>  |  <tag ...>  |  </tag>
  //
  // Attribute content uses LAZY `[^<>]*?` so a self-closing tag like
  // `<rect x="0" />` doesn't see the `/` swallowed by the attribute
  // matcher. The trailer `\s*(\/?)>` then matches the optional `/`
  // explicitly before the closing `>`.
  const tagRe = /<\?[^>]*\?>|<\/([a-zA-Z][\w-]*)\s*>|<([a-zA-Z][\w-]*)(?:\s[^<>]*?)?\s*(\/?)>/g;
  let m: RegExpExecArray | null;
  while ((m = tagRe.exec(doc)) !== null) {
    const [whole, closingName, openName, selfClose] = m;
    if (whole.startsWith("<?")) continue; // XML decl
    if (closingName) {
      // closing tag — must match top of stack
      const top = stack.pop();
      if (top !== closingName) return false;
    } else if (openName) {
      if (selfClose !== "/") stack.push(openName);
    }
  }
  return stack.length === 0;
}
