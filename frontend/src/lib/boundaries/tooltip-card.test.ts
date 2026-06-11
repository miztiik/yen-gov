import { describe, it, expect } from "vitest";
import { renderTooltipCard } from "./tooltip-card";

describe("renderTooltipCard", () => {
  it("renders the title and the 'won by X%' margin line", () => {
    const html = renderTooltipCard({
      title: "12. Tindivanam",
      partyShort: "DMK",
      marginPct: 14.23,
    });
    expect(html).toContain("12. Tindivanam");
    expect(html).toContain("DMK");
    expect(html).toContain("won by 14.2%");
  });

  it("omits the margin line when marginPct is null or undefined", () => {
    const a = renderTooltipCard({ title: "A", partyShort: "X", marginPct: null });
    const b = renderTooltipCard({ title: "B", partyShort: "Y" });
    expect(a).not.toContain("won by");
    expect(b).not.toContain("won by");
  });

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

  it("renders a reservation tag only for SC/ST", () => {
    expect(renderTooltipCard({ title: "t", partyShort: "p", reservation: "SC" })).toContain(
      ">SC<",
    );
    expect(renderTooltipCard({ title: "t", partyShort: "p", reservation: "st" })).toContain(
      ">ST<",
    );
    expect(
      renderTooltipCard({ title: "t", partyShort: "p", reservation: "GEN" }),
    ).not.toMatch(/>GEN</);
    expect(
      renderTooltipCard({ title: "t", partyShort: "p", reservation: null }),
    ).not.toMatch(/rose-100/);
  });

  it("tints the pill with a valid hex and ignores an invalid colour", () => {
    const ok = renderTooltipCard({ title: "t", partyShort: "p", partyColorHex: "#ff0000" });
    expect(ok).toContain("background:#ff0000");

    const bad = renderTooltipCard({
      title: "t",
      partyShort: "p",
      partyColorHex: "red;content:url(x)",
    });
    expect(bad).not.toContain("red;content");
    expect(bad).toContain("background:#e2e8f0");
  });

  it("renders the symbol medallion only for a safe relative asset path", () => {
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

  it("renders the candidate name when provided", () => {
    const html = renderTooltipCard({
      title: "t",
      partyShort: "INC",
      candidateName: "Shashi Tharoor",
      marginPct: 12.3,
    });
    expect(html).toContain("Shashi Tharoor");
  });
});
