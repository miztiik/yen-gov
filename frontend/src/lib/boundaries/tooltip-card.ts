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

import { marginShade } from "../elections/election-map-coloring";

/** Every field beyond the winner identity is optional so callers can adopt
 *  the card incrementally as their view-models gain columns. The fixed
 *  224x150 card renders the same for every surface (PC / AC map, hex
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
   *  Carries party identity: the pill fill and the share-bar's winner
   *  segment. (The left accent bar is shaded by margin, not this hue.)
   *  Invalid values fall back to the neutral grey (never injected raw). */
  partyColorHex?: string | null;
  /** Public asset path for the party election symbol, relative to the
   *  site root, e.g. "party-symbols/rising-sun.svg". Validated; anything
   *  with a scheme/protocol or unexpected characters degrades to a
   *  neutral disc (never a broken <img>). */
  symbolAsset?: string | null;
  /** Victory margin in percentage points. null/undefined hides the
   *  margin value. Rendered in neutral slate; the margin-as-colour signal
   *  lives on the left accent bar via marginShade (the map's single source
   *  of truth), not a second ramp here. */
  marginPct?: number | null;
  /** Winner's share of all votes cast, in percent (0-100). When present
   *  (and not pending), renders the 2-segment FPTP bar: winner segment in
   *  the party hue, the remainder in one fixed neutral. null hides the bar. */
  winnerSharePct?: number | null;
  /** When true the result is not yet declared: neutral bar + disc, no
   *  margin value, blank candidate; the parent / grain / name / affordance
   *  still render. */
  pending?: boolean;
}

const NEUTRAL_HEX = "#cbd5e1"; // slate-300 (--party-neutral): pending / no-winner
const BORDER_HEX = "#e2e8f0"; // slate-200: card border

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

/** Fixed card chrome: 224x150, white surface, slate-200 hairline, shadow,
 *  12px radius clipping the left accent bar, pointer-events off so the
 *  cursor still reaches the map underneath. */
const CARD_STYLE = [
  "box-sizing:border-box",
  "position:relative",
  "width:224px",
  "height:150px",
  "border-radius:12px",
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
    `<span style="flex-shrink:0;font-size:9px;font-weight:700;` +
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
    `<span style="flex-shrink:0;font-size:9px;font-weight:600;` +
    `text-transform:uppercase;letter-spacing:0.04em;color:#be123c;` +
    `background:#ffe4e6;border-radius:4px;padding:1px 4px">${r}</span>`
  );
}

/** 20px party symbol. A real, safe asset renders an <img>; an empty,
 *  garbage, or MALICIOUS path (or a pending result) degrades to a NEUTRAL
 *  disc - never a broken <img>, never the placeholder asset. The disc is
 *  neutral (not party-hued) because the party PILL beside it already
 *  carries the party colour, so the disc never repeats the hue. */
function symbolToken(
  symbolAsset: string | null | undefined,
  pending: boolean,
): string {
  if (!pending && symbolAsset != null && symbolAsset.trim().length > 0) {
    const src = safeAssetPath(symbolAsset);
    if (src) {
      return `<img src="${escapeHtml(src)}" alt="" width="20" height="20" style="display:block;width:20px;height:20px;flex-shrink:0;object-fit:contain" />`;
    }
    // Rejected path -> fall through to the disc (never emit an <img>).
  }
  return (
    `<span style="display:inline-block;width:20px;height:20px;flex-shrink:0;` +
    `border-radius:9999px;background:#f1f5f9;box-shadow:inset 0 0 0 1px #cbd5e1"></span>`
  );
}

/** Margin value text in NEUTRAL slate. The margin-as-colour signal lives
 *  on the left accent bar (marginShade - the map's single source of truth),
 *  so this is not a second/competing ramp. Leading "+" sign (a sign, not an
 *  arrow); tabular-nums so digits never reflow. */
function marginValue(marginPct: number | null | undefined): string {
  if (marginPct == null) return "";
  const abs = Math.abs(marginPct);
  return (
    `<span style="flex-shrink:0;font-size:12px;font-weight:600;` +
    `color:#475569;font-variant-numeric:tabular-nums">+${abs.toFixed(1)}%</span>`
  );
}

/** Winning party short in a PILL filled with the party hue (fg via the
 *  luma helper so it reads on any brand colour). The pill is the card's
 *  party-IDENTITY carrier; pending -> neutral. */
function partyPill(
  partyShort: string,
  accentHex: string,
  pending: boolean,
): string {
  const bg = pending ? NEUTRAL_HEX : accentHex;
  const fg = readableText(bg);
  return (
    `<span style="flex-shrink:0;font-size:11px;font-weight:700;` +
    `padding:1px 7px;border-radius:9999px;background:${bg};color:${fg};` +
    `white-space:nowrap">${escapeHtml(partyShort)}</span>`
  );
}

const VOTE_REST_HEX = "#94a3b8"; // slate-400: "every other party combined"

/** FPTP vote-share bar: a full-width track where the winner's share of all
 *  votes fills the party hue and the remainder is ONE fixed neutral - so a
 *  35%-of-the-vote winner reads as a minority mandate at a glance. No number
 *  (the bar is the signal). Empty string when share is unknown / pending. */
function shareBar(
  winnerSharePct: number | null | undefined,
  accentHex: string,
  pending: boolean,
): string {
  if (pending || winnerSharePct == null || !Number.isFinite(winnerSharePct)) {
    return "";
  }
  const w = Math.max(0, Math.min(100, winnerSharePct));
  return (
    `<div style="height:7px;border-radius:3px;overflow:hidden;background:${VOTE_REST_HEX}">` +
    `<span style="display:block;height:100%;width:${w.toFixed(1)}%;background:${accentHex}"></span>` +
    `</div>`
  );
}

/** Render the fixed tooltip card to an HTML string. Pure; all caller text
 *  is HTML-escaped and every colour / asset input is allowlist-validated
 *  before it reaches a style/src attribute. */
export function renderTooltipCard(model: TooltipCardModel): string {
  const pending = model.pending === true;
  const accent = pending ? NEUTRAL_HEX : (safeHexColor(model.partyColorHex) ?? NEUTRAL_HEX);

  // Left accent bar: REUSES the map's single margin-colour source
  // (marginShade) so its depth = the winning margin, identical to the
  // seat's fill on the map (pale = knife-edge, deep = safe). Pending /
  // no-margin -> neutral. The card radius + overflow:hidden clip it to the
  // rounded corner.
  const barFill =
    pending || model.marginPct == null
      ? NEUTRAL_HEX
      : marginShade(accent, model.marginPct);
  const bar = `<span style="position:absolute;left:0;top:0;bottom:0;width:4px;background:${barFill}"></span>`;

  // Row: parent state.
  const parent = model.parentLabel ? escapeHtml(model.parentLabel) : "";
  const rParent = `<div style="display:flex;align-items:center;min-width:0;font-size:10px;font-weight:500;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${parent}</div>`;

  // Row: grain chip + constituency name + reservation badge.
  const name = `<span style="flex:1 1 auto;min-width:0;font-size:13px;font-weight:700;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeHtml(model.title)}</span>`;
  const rName = `<div style="display:flex;align-items:center;gap:5px;min-width:0">${grainChip(model.grain)}${name}${reservationTag(model.reservation)}</div>`;

  // Row: party symbol + party PILL (identity) + neutral margin (pushed right).
  const margin = pending ? "" : marginValue(model.marginPct);
  const marginR = margin ? `<span style="margin-left:auto">${margin}</span>` : "";
  const rWinner = `<div style="display:flex;align-items:center;gap:7px;min-width:0">${symbolToken(model.symbolAsset, pending)}${partyPill(model.partyShort, accent, pending)}${marginR}</div>`;

  // Row: FPTP vote-share bar (winner hue vs one neutral). Empty when no share.
  const rBar = shareBar(model.winnerSharePct, accent, pending);

  // Row: winning candidate.
  const candidate = pending || !model.candidateName ? "" : escapeHtml(model.candidateName);
  const rCand = `<div style="display:flex;align-items:center;min-width:0;font-size:11px;font-weight:400;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${candidate}</div>`;

  // Row: affordance (text only, no arrow / chevron).
  const rCta = `<div style="display:flex;align-items:flex-end;font-size:10px;font-weight:500;color:#94a3b8">Click to view</div>`;

  // Constant 224x150 box, two grid rhythms: WITH the share bar, and WITHOUT
  // (the bar's track + gap fold into breathing room) so a surface that does
  // not yet thread vote-share never shows an empty gap. Empty <span> cells
  // occupy the gap tracks.
  const sp = "<span></span>";
  const rows = rBar
    ? "12px 4px 18px 10px 24px 8px 14px 6px 14px 4px 1fr"
    : "12px 6px 18px 12px 24px 12px 16px 8px 1fr";
  const cells = rBar
    ? `${rParent}${sp}${rName}${sp}${rWinner}${sp}${rBar}${sp}${rCand}${sp}${rCta}`
    : `${rParent}${sp}${rName}${sp}${rWinner}${sp}${rCand}${sp}${rCta}`;
  const content = `<div style="position:relative;height:100%;box-sizing:border-box;padding:12px 12px 12px 16px;display:grid;grid-template-rows:${rows}">${cells}</div>`;

  return `<div class="yen-tip" style="${CARD_STYLE}">${bar}${content}</div>`;
}
