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
 *  the card incrementally as their view-models gain columns. */
export interface TooltipCardModel {
  /** Constituency heading, e.g. "12. Tindivanam" (AC) or
   *  "Bhiwani-Mahendragarh" (PC). Plain text; escaped on render. */
  title: string;
  /** Seat reservation category. Only "SC"/"ST" render a tag; "GEN",
   *  null, or undefined render nothing. */
  reservation?: string | null;
  /** Winning candidate's full name, when the view-model carries it. */
  candidateName?: string | null;
  /** Winning party's short label, e.g. "DMK". */
  partyShort: string;
  /** Winning party's brand/anchor colour as a hex string ("#rrggbb").
   *  Tints the party pill; invalid values are ignored (neutral pill). */
  partyColorHex?: string | null;
  /** Public asset path for the party election symbol, relative to the
   *  site root, e.g. "party-symbols/rising-sun.svg". Validated; anything
   *  with a scheme/protocol or unexpected characters is dropped. */
  symbolAsset?: string | null;
  /** Victory margin in percentage points. null/undefined hides the line. */
  marginPct?: number | null;
}

const NEUTRAL_PILL_BG = "#e2e8f0"; // slate-200
const NEUTRAL_PILL_FG = "#0f172a"; // slate-900

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

/** Pick a readable foreground (near-black or white) for a given pill
 *  background using perceived luminance. */
function readableText(bgHex: string): string {
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

function reservationTag(reservation: string | null | undefined): string {
  if (!reservation) return "";
  const r = reservation.trim().toUpperCase();
  if (r !== "SC" && r !== "ST") return "";
  return (
    ` <span class="ml-1 rounded bg-rose-100 px-1 text-[10px] font-semibold uppercase tracking-wide text-rose-700 align-middle">${r}</span>`
  );
}

function symbolMedallion(
  symbolAsset: string | null | undefined,
  fallback: "silent" | "placeholder" | "unverified" = "silent",
): string {
  // Two-stage dispatch so the security-degrade (a non-empty MALICIOUS
  // path) cannot be laundered into a placeholder medallion:
  //   1. Non-empty input -> sanitise. If safeAssetPath rejects, src stays
  //      null and we silently emit nothing (no <img>).
  //   2. Empty / null / undefined input -> fallback applies; emit a
  //      placeholder / unverified medallion when caller opted in.
  let src: string | null = null;
  if (symbolAsset != null && symbolAsset.trim().length > 0) {
    src = safeAssetPath(symbolAsset);
  } else if (fallback === "placeholder") {
    src = "party-symbols/placeholder.svg";
  } else if (fallback === "unverified") {
    src = "party-symbols/unverified.svg";
  }
  if (!src) return "";
  return `<img src="${escapeHtml(src)}" alt="" width="16" height="16" class="h-4 w-4 shrink-0 object-contain" />`;
}

function partyPill(partyShort: string, partyColorHex: string | null | undefined): string {
  const bg = safeHexColor(partyColorHex) ?? NEUTRAL_PILL_BG;
  const fg = bg === NEUTRAL_PILL_BG ? NEUTRAL_PILL_FG : readableText(bg);
  return (
    `<span class="rounded px-1.5 py-0.5 text-[11px] font-semibold" ` +
    `style="background:${bg};color:${fg}">${escapeHtml(partyShort)}</span>`
  );
}

/** Render the tooltip card to an HTML string. Pure; all inputs sanitised. */
export function renderTooltipCard(model: TooltipCardModel): string {
  const title = `<div class="font-semibold text-slate-900">${escapeHtml(model.title)}${reservationTag(model.reservation)}</div>`;

  const medallion = symbolMedallion(model.symbolAsset, "placeholder");
  const candidate = model.candidateName
    ? `<span class="text-slate-700">${escapeHtml(model.candidateName)}</span>`
    : "";
  const pill = partyPill(model.partyShort, model.partyColorHex);
  const winner = `<div class="mt-0.5 flex items-center gap-1.5">${medallion}${candidate}${pill}</div>`;

  const margin =
    model.marginPct == null
      ? ""
      : `<div class="mt-0.5 text-slate-500">won by ${model.marginPct.toFixed(1)}%</div>`;

  return `<div class="yen-tip text-[13px] leading-tight">${title}${winner}${margin}</div>`;
}
