/**
 * Unit tests for the share-card SVG builder (R7 of
 * TODO/20260615-state-election-event-page-redesign-plan.md, 2026-06-15).
 *
 * Asserts the pure SVG composition: dimensions are the OG-card
 * standard (1200x630), the winner-colour band uses the input hex,
 * headline + subtitle contain the right text, and the source line
 * footer renders. Special-character escaping is exercised so future
 * publishers with `&` in their titles do not corrupt the SVG.
 */

import { describe, expect, it } from "vitest";

import {
  SHARE_CARD_HEIGHT,
  SHARE_CARD_WIDTH,
  buildShareCardSvg,
  escapeXml,
} from "./build-svg";

describe("buildShareCardSvg", () => {
  it("emits a 1200x630 SVG (OG card standard)", () => {
    const svg = buildShareCardSvg({
      seats_summary: "230 of 288",
      winner_label: "Mahayuti",
      winner_colour_hex: "#FF9933",
      scope_label: "Maharashtra",
      body_label: "Assembly",
      year_label: "2024",
      source_line: "Source: Election Commission of India",
    });
    expect(SHARE_CARD_WIDTH).toBe(1200);
    expect(SHARE_CARD_HEIGHT).toBe(630);
    expect(svg).toContain('width="1200"');
    expect(svg).toContain('height="630"');
  });

  it("uses the winner colour for the top band", () => {
    const svg = buildShareCardSvg({
      seats_summary: "230 of 288",
      winner_label: "Mahayuti",
      winner_colour_hex: "#FF9933",
      scope_label: "Maharashtra",
      body_label: "Assembly",
      year_label: "2024",
      source_line: "x",
    });
    expect(svg).toContain('fill="#FF9933"');
  });

  it("falls back to slate-700 when the winner colour is null", () => {
    const svg = buildShareCardSvg({
      seats_summary: "230 of 288",
      winner_label: null,
      winner_colour_hex: null,
      scope_label: "Maharashtra",
      body_label: "Assembly",
      year_label: "2024",
      source_line: "x",
    });
    expect(svg).toContain('fill="#334155"');
  });

  it("composes the headline from winner + seats", () => {
    const svg = buildShareCardSvg({
      seats_summary: "230 of 288",
      winner_label: "Mahayuti",
      winner_colour_hex: "#FF9933",
      scope_label: "Maharashtra",
      body_label: "Assembly",
      year_label: "2024",
      source_line: "x",
    });
    expect(svg).toContain("Mahayuti won 230 of 288");
  });

  it("simplifies the headline when no winner label is supplied", () => {
    const svg = buildShareCardSvg({
      seats_summary: "230 of 288",
      winner_label: null,
      winner_colour_hex: null,
      scope_label: "Maharashtra",
      body_label: "Assembly",
      year_label: "2024",
      source_line: "x",
    });
    expect(svg).toContain("230 of 288 seats");
    expect(svg).not.toContain("won");
  });

  it("renders the subtitle in uppercase with the body + year", () => {
    const svg = buildShareCardSvg({
      seats_summary: "230 of 288",
      winner_label: "Mahayuti",
      winner_colour_hex: "#FF9933",
      scope_label: "Maharashtra",
      body_label: "Assembly",
      year_label: "2024",
      source_line: "x",
    });
    expect(svg).toContain("MAHARASHTRA - ASSEMBLY 2024");
  });

  it("includes the source line footer", () => {
    const svg = buildShareCardSvg({
      seats_summary: "230 of 288",
      winner_label: "Mahayuti",
      winner_colour_hex: "#FF9933",
      scope_label: "Maharashtra",
      body_label: "Assembly",
      year_label: "2024",
      source_line: "Source: Election Commission of India",
    });
    expect(svg).toContain("Source: Election Commission of India");
  });

  it("includes the YEN-GOV.ORG wordmark", () => {
    const svg = buildShareCardSvg({
      seats_summary: "230 of 288",
      winner_label: "Mahayuti",
      winner_colour_hex: "#FF9933",
      scope_label: "Maharashtra",
      body_label: "Assembly",
      year_label: "2024",
      source_line: "x",
    });
    expect(svg).toContain("YEN-GOV.ORG");
  });
});

describe("escapeXml", () => {
  it("escapes the five XML entities", () => {
    expect(escapeXml("Jammu & Kashmir")).toBe("Jammu &amp; Kashmir");
    expect(escapeXml("Greater <than>")).toBe("Greater &lt;than&gt;");
    expect(escapeXml('Quote "test"')).toBe("Quote &quot;test&quot;");
    expect(escapeXml("Apos'trophe")).toBe("Apos&apos;trophe");
  });

  it("leaves safe characters alone", () => {
    expect(escapeXml("Maharashtra Assembly 2024 - 230 of 288")).toBe(
      "Maharashtra Assembly 2024 - 230 of 288",
    );
  });

  it("escapes the band-colour passthrough when used in attribute context", () => {
    // SVG bodies passing `&` through unescaped would break the
    // parser; the build-svg helper relies on escapeXml at every text
    // boundary. This test pins the function's behaviour.
    const messy = "Sant Rajinder Singh's RBI & SBI dataset";
    const out = escapeXml(messy);
    expect(out).not.toContain("&S");
    expect(out).toContain("&amp;");
    expect(out).toContain("&apos;");
  });
});
