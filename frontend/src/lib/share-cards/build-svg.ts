/**
 * Pure share-card SVG builder for R7 of
 * TODO/20260615-state-election-event-page-redesign-plan.md (J-elevated-14).
 *
 * Produces a 1200x630 SVG string that gets rasterised to PNG by the
 * build step in `frontend/scripts/build-share-cards.ts`. The PNG is
 * what WhatsApp / Twitter / LinkedIn / Signal show as the unfurl
 * preview when a citizen shares `/<state>/elections/<event>` or
 * `/t/elections/<event>`.
 *
 * Design decisions (Jony + Citizen, plan-doc Section 7.5):
 *  - 1200x630 = OG card standard (Facebook + Twitter + LinkedIn agree).
 *  - Typography-first: the citizen's friend on WhatsApp gets a
 *    legible thumbnail at 200x100 in the preview - tiny visuals are
 *    noise; big numbers are signal.
 *  - Winner-party color band (full width, ~70px) at the top sets the
 *    visual identity at a glance ("BJP won" reads from the saffron
 *    even before the eye lands on the text).
 *  - Headline = "{Winner} {seats} of {total}" in big bold.
 *  - Subtitle = "{State or India} - {body} {year}".
 *  - Footer = small "yen-gov.org" wordmark + source attribution line.
 *  - Hand-rolled SVG (no @vercel/og / satori) - resvg-js takes raw
 *    SVG bytes. Keeps the dep tree minimal (Holy Law #8).
 *
 * Pure: no I/O, no file reads, no network. The build script does the
 * fetching + parsing + rasterisation; this module just turns a struct
 * into an SVG string. Test seam: vitest unit asserts SVG width/height
 * and the headline + subtitle text appear verbatim.
 */

export interface ShareCardInput {
  /** Citizen-visible big number, e.g. "230 of 288". */
  seats_summary: string;
  /** Winning party short name, e.g. "BJP" or "Mahayuti". Optional;
   *  when null the headline simplifies to just "{seats} of {total}
   *  seats". */
  winner_label: string | null;
  /** Winner brand colour hex (e.g. "#FF9933"). Falls back to a
   *  slate-700 if the resolver returned no colour. */
  winner_colour_hex: string | null;
  /** State display name OR "India" for national events. */
  scope_label: string;
  /** "Assembly" / "Parliament" - the body chip. */
  body_label: string;
  /** Event year, e.g. "2024". */
  year_label: string;
  /** Citation footer line, e.g. "Source: Election Commission of India". */
  source_line: string;
}

/** Card dimensions. The OG standard is 1200x630; never parametrise. */
export const SHARE_CARD_WIDTH = 1200;
export const SHARE_CARD_HEIGHT = 630;

/** Default neutral colour when the winner colour is missing. */
const DEFAULT_BAND_COLOUR = "#334155"; // slate-700

/**
 * Escape special XML characters in a string. The card builder writes
 * SVG bytes directly so any unescaped `&` / `<` / `>` would corrupt
 * the document. Quotes are also escaped because they appear inside
 * attribute values (e.g. font-family) - although the card never
 * emits user-supplied attributes, doing it once at the boundary
 * keeps the helper safe to compose with.
 */
export function escapeXml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * Compose the SVG bytes for one share card. Pure function; no I/O.
 *
 * Layout (top to bottom):
 *  - 0..70   px: winner-party-colour band
 *  - 70..110 px: padding
 *  - 110..280 px: subtitle "{scope} - {body} {year}"
 *  - 280..460 px: headline "{winner} {seats}"
 *  - 460..540 px: padding
 *  - 540..610 px: source footer line
 *  - 610..620 px: yen-gov wordmark
 */
export function buildShareCardSvg(input: ShareCardInput): string {
  const band_hex = input.winner_colour_hex ?? DEFAULT_BAND_COLOUR;
  const subtitle = `${input.scope_label} - ${input.body_label} ${input.year_label}`;
  // Headline: "Winner 230 of 288 seats" when winner exists;
  // "230 of 288 seats" when it does not.
  const headline = input.winner_label
    ? `${input.winner_label} won ${input.seats_summary}`
    : `${input.seats_summary} seats`;

  const subtitle_esc = escapeXml(subtitle);
  const headline_esc = escapeXml(headline);
  const source_esc = escapeXml(input.source_line);

  // Inter is the closest free font to the citizen-facing yen-gov
  // chrome; if the renderer can't find it the system stack catches.
  const FONT_STACK =
    "'Inter','Helvetica Neue',Arial,sans-serif";

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${SHARE_CARD_WIDTH}" height="${SHARE_CARD_HEIGHT}" viewBox="0 0 ${SHARE_CARD_WIDTH} ${SHARE_CARD_HEIGHT}">
  <rect x="0" y="0" width="${SHARE_CARD_WIDTH}" height="${SHARE_CARD_HEIGHT}" fill="#ffffff"/>
  <rect x="0" y="0" width="${SHARE_CARD_WIDTH}" height="70" fill="${band_hex}"/>
  <text x="80" y="200" font-family="${FONT_STACK}" font-size="34" font-weight="500" fill="#64748b" letter-spacing="2">${subtitle_esc.toUpperCase()}</text>
  <text x="80" y="340" font-family="${FONT_STACK}" font-size="72" font-weight="700" fill="#0f172a">${headline_esc}</text>
  <text x="80" y="560" font-family="${FONT_STACK}" font-size="22" font-weight="400" fill="#64748b">${source_esc}</text>
  <text x="80" y="600" font-family="${FONT_STACK}" font-size="20" font-weight="600" fill="#0f172a" letter-spacing="1">YEN-GOV.ORG</text>
  <line x1="80" y1="520" x2="${SHARE_CARD_WIDTH - 80}" y2="520" stroke="#e2e8f0" stroke-width="1"/>
</svg>
`;
}
