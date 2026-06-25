import { describe, it, expect } from "vitest";
import {
  renderTooltipCard,
  MARGIN_CLOSE_PP,
  MARGIN_DECISIVE_PP,
} from "./tooltip-card";

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

  it("fills the accent bar with a valid hex and ignores an invalid colour", () => {
    const ok = renderTooltipCard({ title: "t", partyShort: "p", partyColorHex: "#ff0000" });
    expect(ok).toContain("background:#ff0000");

    const bad = renderTooltipCard({
      title: "t",
      partyShort: "p",
      partyColorHex: "red;content:url(x)",
    });
    // Injection rejected; the bar falls back to the neutral grey.
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

  it("colours the margin value by abs(margin) on the 3-band scale", () => {
    // < MARGIN_CLOSE_PP -> amber-700.
    const close = renderTooltipCard({ title: "t", partyShort: "p", marginPct: 3.2 });
    expect(close).toMatch(/<span[^>]*color:#b45309[^>]*>\+3\.2%<\/span>/);

    // MARGIN_CLOSE_PP .. < MARGIN_DECISIVE_PP -> slate-500.
    const mid = renderTooltipCard({ title: "t", partyShort: "p", marginPct: 8 });
    expect(mid).toMatch(/<span[^>]*color:#64748b[^>]*>\+8\.0%<\/span>/);

    // >= MARGIN_DECISIVE_PP -> slate-900.
    const decisive = renderTooltipCard({ title: "t", partyShort: "p", marginPct: 22 });
    expect(decisive).toMatch(/<span[^>]*color:#0f172a[^>]*>\+22\.0%<\/span>/);
  });

  it("treats the band thresholds as closed-open intervals", () => {
    // Exactly MARGIN_CLOSE_PP (5) is NOT close -> mid band.
    const atClose = renderTooltipCard({
      title: "t",
      partyShort: "p",
      marginPct: MARGIN_CLOSE_PP,
    });
    expect(atClose).toMatch(/color:#64748b[^>]*>\+5\.0%/);

    // Exactly MARGIN_DECISIVE_PP (15) IS decisive.
    const atDecisive = renderTooltipCard({
      title: "t",
      partyShort: "p",
      marginPct: MARGIN_DECISIVE_PP,
    });
    expect(atDecisive).toMatch(/color:#0f172a[^>]*>\+15\.0%/);
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

  it("degrades to a party-hued disc (no <img>, no placeholder asset) for empty and malicious assets", () => {
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
      // The party-hued disc carries identity instead of a broken image.
      expect(html).toContain("background:#123456");
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
