import { describe, it, expect } from "vitest";
import { renderTooltipCard } from "./tooltip-card";
import { marginShade } from "../elections/election-map-coloring";

describe("renderTooltipCard", () => {
  it("renders the name and a margin value with a leading +", () => {
    const html = renderTooltipCard({
      title: "12. Tindivanam",
      partyShort: "DMK",
      marginPct: 14.23,
    });
    expect(html).toContain("12. Tindivanam");
    expect(html).toContain("DMK");
    expect(html).toContain("+14.2%");
    // Legacy "won by X%" phrasing is gone (R-C: value-only).
    expect(html).not.toContain("won by");
  });

  it("omits the margin value when marginPct is null or undefined", () => {
    const a = renderTooltipCard({ title: "A", partyShort: "X", marginPct: null });
    const b = renderTooltipCard({ title: "B", partyShort: "Y" });
    expect(a).not.toMatch(/\+\d/);
    expect(b).not.toMatch(/\+\d/);
  });

  // --- Security suite (preserved verbatim in intent) ---

  it("escapes HTML in title, party label, and candidate name", () => {
    const html = renderTooltipCard({
      title: '<img src=x onerror="alert(1)">',
      partyShort: "<b>BJP</b>",
      candidateName: "A & B <script>",
      marginPct: 5,
    });
    expect(html).not.toContain("<img src=x");
    expect(html).not.toContain("<b>BJP</b>");
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;img");
    expect(html).toContain("&amp; B &lt;script&gt;");
  });

  it("carries the party hue on the pill and ignores an invalid colour", () => {
    // The party hue lives on the pill (and the share-bar segment), not the
    // left accent bar (which is shaded by margin).
    const ok = renderTooltipCard({ title: "t", partyShort: "p", partyColorHex: "#ff0000" });
    expect(ok).toContain("background:#ff0000");

    const bad = renderTooltipCard({
      title: "t",
      partyShort: "p",
      partyColorHex: "red;content:url(x)",
    });
    // Injection rejected; identity falls back to the neutral grey.
    expect(bad).not.toContain("red;content");
    expect(bad).toContain("background:#cbd5e1");
  });

  it("renders the symbol image only for a safe relative asset path", () => {
    const ok = renderTooltipCard({
      title: "t",
      partyShort: "p",
      symbolAsset: "party-symbols/rising-sun.svg",
    });
    expect(ok).toContain('src="party-symbols/rising-sun.svg"');

    for (const bad of [
      "javascript:alert(1)",
      "http://evil/x.svg",
      "//evil/x.svg",
      "..\\..\\secret",
      'x" onload="alert(1)',
    ]) {
      const html = renderTooltipCard({ title: "t", partyShort: "p", symbolAsset: bad });
      expect(html).not.toContain("<img");
    }
  });

  // --- Fixed-card content suite (R-A .. R-H) ---

  it("renders a reservation tag only for SC/ST", () => {
    expect(renderTooltipCard({ title: "t", partyShort: "p", reservation: "SC" })).toContain(
      ">SC<",
    );
    expect(renderTooltipCard({ title: "t", partyShort: "p", reservation: "st" })).toContain(
      ">ST<",
    );
    expect(
      renderTooltipCard({ title: "t", partyShort: "p", reservation: "GEN" }),
    ).not.toContain(">GEN<");
    const none = renderTooltipCard({ title: "t", partyShort: "p", reservation: null });
    expect(none).not.toContain(">SC<");
    expect(none).not.toContain(">ST<");
  });

  it("renders the grain chip for PC and AC and omits it when grain is absent", () => {
    expect(renderTooltipCard({ title: "t", partyShort: "p", grain: "PC" })).toContain(">PC<");
    expect(renderTooltipCard({ title: "t", partyShort: "p", grain: "AC" })).toContain(">AC<");
    const none = renderTooltipCard({ title: "t", partyShort: "p" });
    expect(none).not.toContain(">PC<");
    expect(none).not.toContain(">AC<");
  });

  it("renders the parent-state line", () => {
    const html = renderTooltipCard({
      title: "Tindivanam",
      partyShort: "DMK",
      parentLabel: "Tamil Nadu",
    });
    expect(html).toContain("Tamil Nadu");
  });

  it("renders the margin value in neutral slate regardless of magnitude", () => {
    // No party-independent band ramp any more: the margin-as-colour signal
    // moved to the left accent bar (marginShade). The text is always slate.
    for (const m of [3.2, 8, 22]) {
      const html = renderTooltipCard({ title: "t", partyShort: "p", marginPct: m });
      expect(html).toMatch(
        new RegExp(`<span[^>]*color:#475569[^>]*>\\+${m.toFixed(1)}%<\\/span>`),
      );
    }
    // The retired band colours never appear.
    const any = renderTooltipCard({ title: "t", partyShort: "p", marginPct: 3.2 });
    expect(any).not.toContain("#b45309"); // amber-700 (old "close")
  });

  it("shades the left accent bar by margin via marginShade", () => {
    const hex = "#2563eb";
    const html = renderTooltipCard({
      title: "t",
      partyShort: "p",
      partyColorHex: hex,
      marginPct: 18,
    });
    // The 4px left bar is filled with the choropleth's own margin shade.
    expect(html).toContain(`background:${marginShade(hex, 18)}`);
    // With no margin the bar is neutral, not the raw hue.
    const noMargin = renderTooltipCard({ title: "t", partyShort: "p", partyColorHex: hex });
    expect(noMargin).toMatch(/position:absolute;left:0;[^"]*background:#cbd5e1/);
  });

  it("renders the FPTP vote-share bar from winnerSharePct and omits it when absent", () => {
    const hex = "#2563eb";
    const withBar = renderTooltipCard({
      title: "t",
      partyShort: "p",
      partyColorHex: hex,
      winnerSharePct: 34.6,
    });
    // Track is the fixed neutral rest; the winner segment is the party hue
    // sized to the share (no number).
    expect(withBar).toContain("background:#94a3b8");
    expect(withBar).toContain(`width:34.6%;background:${hex}`);

    const noBar = renderTooltipCard({ title: "t", partyShort: "p", partyColorHex: hex });
    expect(noBar).not.toContain("background:#94a3b8");
  });

  it("renders the winning party short inside a hued pill", () => {
    const html = renderTooltipCard({ title: "t", partyShort: "BJP", partyColorHex: "#ff9933" });
    expect(html).toMatch(/border-radius:9999px;background:#ff9933;color:#[0-9a-f]{6}[^>]*>BJP</);
  });

  it("renders the candidate name when provided", () => {
    const html = renderTooltipCard({
      title: "t",
      partyShort: "INC",
      candidateName: "Shashi Tharoor",
      marginPct: 12.3,
    });
    expect(html).toContain("Shashi Tharoor");
  });

  it("degrades to a neutral disc (no <img>, no placeholder asset) for empty and malicious assets", () => {
    const assets: (string | null | undefined)[] = [
      "",
      "   ",
      null,
      undefined,
      'x" onload="alert(1)',
      "javascript:alert(1)",
      "..\\..\\secret",
      "//evil/x.svg",
    ];
    for (const asset of assets) {
      const html = renderTooltipCard({
        title: "t",
        partyShort: "p",
        symbolAsset: asset,
        partyColorHex: "#123456",
      });
      expect(html).not.toContain("<img");
      expect(html).not.toContain("party-symbols/");
      // The disc is neutral (the pill carries party identity, so the disc
      // never repeats the hue); a broken image is never emitted.
      expect(html).toContain("background:#f1f5f9");
    }
  });

  it("renders the pending branch: neutral bar, no margin, blank candidate, full context", () => {
    const html = renderTooltipCard({
      title: "Tindivanam",
      partyShort: "Pending",
      grain: "AC",
      parentLabel: "Tamil Nadu",
      candidateName: "Should Not Show",
      marginPct: 42,
      partyColorHex: "#ff0000",
      pending: true,
    });
    expect(html).toContain("background:#cbd5e1"); // neutral bar + disc
    expect(html).not.toContain("background:#ff0000"); // party colour suppressed
    expect(html).not.toContain("+42.0%"); // no margin value
    expect(html).not.toContain("Should Not Show"); // candidate blanked
    expect(html).toContain("Tamil Nadu"); // parent still shown
    expect(html).toContain(">AC<"); // grain chip still shown
    expect(html).toContain("Tindivanam"); // name still shown
    expect(html).toContain("Click to view"); // affordance still shown
  });

  it("shows a text-only 'Click to view' affordance with no arrow", () => {
    const html = renderTooltipCard({ title: "t", partyShort: "p" });
    expect(html).toContain("Click to view");
    expect(html).not.toContain("->");
    expect(html).not.toContain("\u2192"); // right arrow glyph
  });
});
