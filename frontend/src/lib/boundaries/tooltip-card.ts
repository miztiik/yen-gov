// Shared constituency map tooltip card.
//
// One typed model + one pure renderer feed every AC/PC map hover popup
// (StateAcMap, NationalElectionsAtlas, and anything that delegates to them
// through MapChoropleth). Before this module each surface hand-rolled its
// own HTML-string builder and its own `escape_html`, which drifted; the
// "schema is the design system" rule wants ONE card, not per-surface
// bespoke markup.
//
// The renderer is a pure `model -> string` function so it is trivially
// unit-testable and carries no Svelte/DOM dependency. All caller-supplied
// text is HTML-escaped here; colour + asset inputs are validated against a
// strict allowlist before they reach a `style`/`src` attribute, so a
// malicious party label or boundary property can never inject markup.

/** Every field beyond the winner identity is optional so callers can adopt
 *  the card incrementally as their view-models gain columns. The fixed
 *  256x140 card renders the same for every surface (PC / AC map, hex
 *  cartogram); only the text / bar colour / symbol / margin change. */
export interface TooltipCardModel {
  /** Constituency name, e.g. "Tindivanam" (AC) or
   *  "Bhiwani-Mahendragarh" (PC). Plain text; escaped on render. The
   *  leading ECI number is dropped by the caller (no "12. " prefix). */
  title: string;
  /** Seat grain. Renders the leading [PC] / [AC] chip on the name row.
   *  Optional: an absent grain omits the chip so un-migrated callers
   *  still render valid markup. */
  grain?: "PC" | "AC";
  /** Parent state name shown on the first row, e.g. "Tamil Nadu".
   *  null/undefined leaves the row blank. */
  parentLabel?: string | null;
  /** Seat reservation category. Only "SC"/"ST" render a tag; "GEN",
   *  null, or undefined render nothing. */
  reservation?: string | null;
  /** Winning candidate's full name, when the view-model carries it. */
  candidateName?: string | null;
  /** Winning party's short label, e.g. "DMK". */
  partyShort: string;
  /** Winning party's brand/anchor colour as a hex string ("#rrggbb").
   *  Fills the left accent bar and the symbol disc; invalid values fall
   *  back to the neutral grey (never injected raw). */
  partyColorHex?: string | null;
  /** Public asset path for the party election symbol, relative to the
   *  site root, e.g. "party-symbols/rising-sun.svg". Validated; anything
   *  with a scheme/protocol or unexpected characters degrades to the
   *  party-hued disc (never a broken <img>). */
  symbolAsset?: string | null;
  /** Victory margin in percentage points. null/undefined hides the
   *  margin value. Coloured by abs(margin) on a party-independent scale. */
  marginPct?: number | null;
  /** When true the result is not yet declared: neutral bar + disc, no
   *  margin value, blank candidate; the parent / grain / name / affordance
   *  still render. */
  pending?: boolean;
}

/** Margin band thresholds (percentage points). Named so the bands carry
 *  no magic numbers and no prediction language. Party-INDEPENDENT: the
 *  colour flags only how close THIS seat's result was, never a ranking. */
export const MARGIN_CLOSE_PP = 5;
export const MARGIN_DECISIVE_PP = 15;

const NEUTRAL_HEX = "#cbd5e1"; // slate-300 (--party-neutral): pending / no-winner
const BORDER_HEX = "#e2e8f0"; // slate-200: card border, divider, disc ring

export function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    c === "&"
      ? "&amp;"
      : c === "<"
        ? "&lt;"
        : c === ">"
          ? "&gt;"
          : c === '"'
            ? "&quot;"
            : "&#39;",
  );
}

/** Accept only `#rgb`, `#rrggbb`, `#rrggbbaa`; reject everything else so the
 *  value can be inlined into a `style` attribute without escaping concerns. */
function safeHexColor(hex: string | null | undefined): string | null {
  if (!hex) return null;
  return /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$/.test(hex)
    ? hex
    : null;
}

/** Accept only a relative path made of safe path characters; reject any
 *  scheme (`http:`, `data:`, `javascript:`), protocol-relative `//`, or
 *  backslashes so the value is safe inside an `src` attribute. */
function safeAssetPath(path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^[a-z][a-z0-9+.-]*:/i.test(path)) return null; // has a scheme
  if (path.startsWith("//") || path.includes("\\")) return null;
  if (!/^[A-Za-z0-9._\-/]+$/.test(path)) return null;
  return path;
}

/** Pick a readable foreground (near-black or white) for a given
 *  background using perceived luminance. Exported for the hex cartogram
 *  label colouring (see plan R-I). */
export function readableText(bgHex: string): string {
  let h = bgHex.slice(1);
  if (h.length === 3)
    h = h
      .split("")
      .map((c) => c + c)
      .join("");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  // Rec. 601 luma.
  const luma = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luma > 0.6 ? "#0f172a" : "#ffffff";
}

/** Fixed card chrome: 256x140, white surface, slate-200 hairline, shadow,
 *  14px radius clipping the left accent bar, pointer-events off so the
 *  cursor still reaches the map underneath. */
const CARD_STYLE = [
  "box-sizing:border-box",
  "position:relative",
  "width:256px",
  "height:140px",
  "border-radius:14px",
  "overflow:hidden",
  "background:#ffffff",
  `border:1px solid ${BORDER_HEX}`,
  "box-shadow:0 4px 14px rgba(15,23,42,0.12)",
  "pointer-events:none",
  "font-family:inherit",
  "text-align:left",
  "color:#0f172a",
].join(";");

/** Leading [PC] / [AC] chip on the name row. Absent grain -> no chip. */
function grainChip(grain: "PC" | "AC" | undefined): string {
  if (grain !== "PC" && grain !== "AC") return "";
  return (
    `<span style="flex-shrink:0;font-size:10px;font-weight:700;` +
    `text-transform:uppercase;letter-spacing:0.04em;color:#475569;` +
    `background:#f1f5f9;border-radius:4px;padding:1px 4px">${grain}</span>`
  );
}

/** Right-aligned SC/ST badge on the name row. Nothing for GEN/null. */
function reservationTag(reservation: string | null | undefined): string {
  if (!reservation) return "";
  const r = reservation.trim().toUpperCase();
  if (r !== "SC" && r !== "ST") return "";
  return (
    `<span style="flex-shrink:0;font-size:10px;font-weight:600;` +
    `text-transform:uppercase;letter-spacing:0.04em;color:#be123c;` +
    `background:#ffe4e6;border-radius:4px;padding:1px 4px">${r}</span>`
  );
}

/** 18px party symbol. A real, safe asset renders an <img>; an empty,
 *  garbage, or MALICIOUS path (or a pending result) degrades to a
 *  party-hued disc - never a broken <img>, never the placeholder asset
 *  (plan R-H). The disc colour reuses the same `safeHexColor` allowlist
 *  as the bar (no second colour allowlist). */
function symbolToken(
  symbolAsset: string | null | undefined,
  accentHex: string,
  pending: boolean,
): string {
  if (!pending && symbolAsset != null && symbolAsset.trim().length > 0) {
    const src = safeAssetPath(symbolAsset);
    if (src) {
      return `<img src="${escapeHtml(src)}" alt="" width="18" height="18" style="display:block;width:18px;height:18px;flex-shrink:0;object-fit:contain" />`;
    }
    // Rejected path -> fall through to the disc (never emit an <img>).
  }
  const disc = pending ? NEUTRAL_HEX : accentHex;
  return (
    `<span style="display:inline-block;width:18px;height:18px;flex-shrink:0;` +
    `border-radius:9999px;background:${disc};box-shadow:inset 0 0 0 1px ${BORDER_HEX}"></span>`
  );
}

/** Margin value text, coloured on a party-INDEPENDENT 3-band scale by
 *  abs(margin). Always a leading "+" sign (a sign, not an arrow); no
 *  "safe"/"marginal" word label. tabular-nums so digits never reflow. */
function marginValue(marginPct: number | null | undefined): string {
  if (marginPct == null) return "";
  const abs = Math.abs(marginPct);
  let color: string;
  let weight: number;
  if (abs < MARGIN_CLOSE_PP) {
    color = "#b45309"; // amber-700: this seat was close
    weight = 600;
  } else if (abs < MARGIN_DECISIVE_PP) {
    color = "#64748b"; // slate-500
    weight = 600;
  } else {
    color = "#0f172a"; // slate-900: decisive
    weight = 700;
  }
  return (
    `<span style="flex-shrink:0;font-size:13px;font-weight:${weight};` +
    `color:${color};font-variant-numeric:tabular-nums">+${abs.toFixed(1)}%</span>`
  );
}

/** Render the fixed tooltip card to an HTML string. Pure; all caller text
 *  is HTML-escaped and every colour / asset input is allowlist-validated
 *  before it reaches a style/src attribute. */
export function renderTooltipCard(model: TooltipCardModel): string {
  const pending = model.pending === true;
  const accent = pending ? NEUTRAL_HEX : (safeHexColor(model.partyColorHex) ?? NEUTRAL_HEX);

  // Left party-colour accent bar (R-B); the card radius + overflow:hidden
  // clip it to the rounded corner.
  const bar = `<span style="position:absolute;left:0;top:0;bottom:0;width:4px;background:${accent}"></span>`;

  // Row 1: parent state.
  const parent = model.parentLabel ? escapeHtml(model.parentLabel) : "";
  const row1 = `<div style="display:flex;align-items:center;min-width:0;font-size:11px;font-weight:500;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${parent}</div>`;

  // Row 2: grain chip + constituency name + reservation badge.
  const name = `<span style="flex:1 1 auto;min-width:0;font-size:14px;font-weight:600;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(model.title)}</span>`;
  const row2 = `<div style="display:flex;align-items:center;gap:6px;min-width:0">${grainChip(model.grain)}${name}${reservationTag(model.reservation)}</div>`;

  // Row 3: divider.
  const row3 = `<div style="display:flex;align-items:center"><span style="display:block;width:100%;height:1px;background:${BORDER_HEX}"></span></div>`;

  // Row 4: party symbol + party short + 3-band margin value.
  const party = `<span style="flex:1 1 auto;min-width:0;font-size:13px;font-weight:600;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(model.partyShort)}</span>`;
  const margin = pending ? "" : marginValue(model.marginPct);
  const row4 = `<div style="display:flex;align-items:center;gap:8px;min-width:0">${symbolToken(model.symbolAsset, accent, pending)}${party}${margin}</div>`;

  // Row 5: winning candidate (the one extra field, R-F).
  const candidate = pending || !model.candidateName ? "" : escapeHtml(model.candidateName);
  const row5 = `<div style="display:flex;align-items:center;min-width:0;font-size:12px;font-weight:400;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${candidate}</div>`;

  // Row 6: affordance (R-G: text only, no arrow / chevron).
  const row6 = `<div style="display:flex;align-items:flex-end;font-size:11px;font-weight:500;color:#94a3b8">Click to view</div>`;

  const content = `<div style="position:relative;height:100%;box-sizing:border-box;padding:14px 14px 14px 18px;display:grid;grid-template-rows:14px 20px 9px 20px 16px 1fr">${row1}${row2}${row3}${row4}${row5}${row6}</div>`;

  return `<div class="yen-tip" style="${CARD_STYLE}">${bar}${content}</div>`;
}
