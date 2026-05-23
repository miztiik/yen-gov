// StackedTrendV2 — standalone SVG export (Phase 2.7).
//
// Per TODO/20260518-frontend-charting-modernisation-plan.md Phase 2.7.
// Produces a single self-contained SVG string that a citizen can save,
// share, or paste into a document. No external font, no external CSS,
// no `<image>` reference — everything needed to render is inline so
// the file works offline and on any viewer that speaks SVG 1.1.
//
// Design choices:
//
//  - **One pure helper, no DOM**. Renders the bars from `model.bars`
//    using the same geometry the on-screen chart uses (via the existing
//    helpers `barTotal`, `segmentVisualHeightPct`, `visibleCategoryIds`),
//    so the export matches what the citizen saw. Importantly, we do
//    NOT serialise the live `<svg>` node from the DOM — that node uses
//    `viewBox="0 0 100 100"` + `preserveAspectRatio="none"` to fluidly
//    fill its container, which would produce stretched text if exported
//    directly. The export rebuilds geometry on a pixel-accurate
//    `viewBox` with crisp HTML `<text>` so labels read cleanly at any
//    zoom level.
//
//  - **SVG only, no PNG**. The plan says "Prefer SVG export for
//    SVG-authored charts; add PNG export only when needed." A citizen
//    pasting into Google Docs or Slack gets SVG support out of the
//    box; rasterising via `<canvas>` would force a font-fallback
//    decision, a DPI question, and a much larger bundle. If a future
//    user actually requests PNG we add a separate helper that
//    rasterises this SVG — the contract is one-way.
//
//  - **No external font reference**. Inline `font-family="system-ui,
//    -apple-system, ..."` so the SVG renders with the viewer's default
//    sans-serif. Avoids the standalone-SVG "missing font" trap where
//    a CSS `@font-face` URL points at our dev server.
//
//  - **Provenance always present**. The footer line cites the
//    highest-confidence source (`gold` > `silver` > `bronze`) via the
//    same `producer | title (vintage)` template the on-screen
//    SourceListV2 uses. Holy Law #9 — no anonymous data ships, including
//    on a downloaded image.
//
// CLAUDE.md §0 (a11y descoped): no `<title>` / `<desc>` / `role` on the
// root SVG. The export is a visual artifact; the citizen who downloads
// it has already seen the live readout panel for the same data.

import {
  barTotal,
  maxBarTotal,
  segmentVisualHeightPct,
  visibleCategoryIds,
} from "./helpers";
import {
  OTHER_CATEGORY_FILL_V2,
  OTHER_CATEGORY_ID_V2,
  type StackedTrendV2Model,
  type StackedTrendV2Source,
} from "./types";

// ---- layout constants (px on the export's pixel-accurate viewBox) ----
//
// Pixel-accurate `viewBox` so text stays crisp at any zoom. 640 wide
// matches a common social-card width; 460 tall fits title + chart +
// labels + legend + footer without dead space.

export const EXPORT_WIDTH_PX = 640;
export const EXPORT_HEIGHT_PX = 460;

const PAD_X = 24;
const TITLE_Y = 28;
const SUBTITLE_Y = 48;
const CHART_TOP = 80;
const CHART_HEIGHT = 240;
const PERIOD_LABEL_Y = CHART_TOP + CHART_HEIGHT + 18;
const LEGEND_Y = PERIOD_LABEL_Y + 28;
const FOOTER_Y = EXPORT_HEIGHT_PX - 18;

const CHART_INNER_WIDTH = EXPORT_WIDTH_PX - PAD_X * 2;
const BAR_GAP_RATIO = 0.15;

// ---- font stack ------------------------------------------------------
//
// Inline so the SVG never requests an external CSS or font file. Order
// matches what Tailwind ships at `font-sans` so the export mirrors the
// on-screen typography on most viewers.

const FONT_FAMILY =
  "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif";

// ---- pure helpers ----------------------------------------------------

/**
 * Escape the five XML / SVG-significant characters so user-controlled
 * strings (titles, category labels, source citations) never break the
 * standalone document. NOT a generic HTML sanitiser — the export only
 * emits text content, never attribute values that accept URLs.
 */
export function escapeSvgText(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

/**
 * Render-time category fill lookup that mirrors `fillFor` in the
 * component but pure (no closure over `model`). Falls back to slate-500
 * when the category has no `fill` AND is not `__OTHER__` — the citizen
 * sees a visible bar rather than a transparent gap if an adapter ships
 * an incomplete category.
 */
export function exportFillFor(
  category_id: string,
  model: StackedTrendV2Model,
): string {
  if (category_id === OTHER_CATEGORY_ID_V2) return OTHER_CATEGORY_FILL_V2;
  const cat = model.categories.find((c) => c.id === category_id);
  return cat?.fill ?? "#64748b";
}

/**
 * Mirror of `labelFor` from the component, pure version. `__OTHER__`
 * collapses to `"Other"`; missing categories fall back to the raw id
 * so the export never silently swallows a data row.
 */
export function exportLabelFor(
  category_id: string,
  model: StackedTrendV2Model,
): string {
  if (category_id === OTHER_CATEGORY_ID_V2) return "Other";
  return (
    model.categories.find((c) => c.id === category_id)?.label ?? category_id
  );
}

/**
 * Format a numeric value for the export legend / readout, mirroring the
 * on-screen `fmtValue` rule. Pure; the unit metadata lives on the
 * model.
 */
export function exportFmtValue(v: number, model: StackedTrendV2Model): string {
  if (model.unit.value_kind === "share") return `${(v * 100).toFixed(1)}%`;
  if (Math.abs(v) >= 1000)
    return `${(v / 1000).toFixed(1)}k ${model.unit.label}`;
  return `${v.toFixed(0)} ${model.unit.label}`;
}

/**
 * Pick the highest-confidence source for the footer citation. Order:
 * gold → silver → bronze; within a tier, the FIRST source in the model
 * wins so adapters keep deterministic control over which row gets the
 * footer slot. Returns `null` when `model.sources` is empty — the
 * caller renders a fallback line.
 */
export function pickPrimarySource(
  model: StackedTrendV2Model,
): StackedTrendV2Source | null {
  const rank: Record<StackedTrendV2Source["confidence_tier"], number> = {
    gold: 0,
    silver: 1,
    bronze: 2,
  };
  let best: StackedTrendV2Source | null = null;
  let bestRank = Infinity;
  for (const s of model.sources) {
    const r = rank[s.confidence_tier];
    if (r < bestRank) {
      best = s;
      bestRank = r;
    }
  }
  return best;
}

/**
 * Compose the citation line for the export footer. Uses
 * `source.citation_full` verbatim when the adapter set it (override),
 * otherwise composes `"producer, title (vintage)"` — same template the
 * on-screen SourceListV2 uses. Holy Law #9: provenance is mandatory,
 * even on an exported image.
 */
export function composeCitation(source: StackedTrendV2Source): string {
  if (source.citation_full) return source.citation_full;
  const trail = source.vintage ? ` (${source.vintage})` : "";
  return `${source.producer}, ${source.title}${trail}`;
}

/**
 * Compose the export filename for the SVG download. Shape:
 *
 *     <headline-or-dimension>_<mode>_<first>-<last>.svg
 *
 * Slugifies the headline (or `model.dimension` when no headline) to
 * lowercase alphanumerics-and-hyphens so the citizen can save the
 * file on any OS. Period IDs (typically already ASCII like "FY2024-25"
 * or "2024") are sanitised the same way so a colon or slash from an
 * adapter never breaks Windows.
 */
export function buildExportFilename(
  model: StackedTrendV2Model,
  mode: "percent" | "absolute",
): string {
  const base = model.headline?.text ?? model.dimension;
  const slug = slugify(base) || "chart";
  const firstPeriod = slugify(model.bars[0]?.period_id ?? "");
  const lastPeriod = slugify(model.bars[model.bars.length - 1]?.period_id ?? "");
  const window =
    firstPeriod && lastPeriod
      ? firstPeriod === lastPeriod
        ? firstPeriod
        : `${firstPeriod}-${lastPeriod}`
      : "";
  const parts = [slug, mode, window].filter((p) => p.length > 0);
  return `${parts.join("_")}.svg`;
}

function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

// ---- the export builder ---------------------------------------------

export interface BuildExportSvgOptions {
  /**
   * The current rendering mode at export time. Drives the subtitle
   * label ("Share" / "Total") and the bar geometry (percent stacks fill
   * the full bar; absolute stacks scale by `maxBarTotal`).
   */
  mode: "percent" | "absolute";
}

/**
 * Build a standalone SVG document string for the given model + mode.
 *
 * Output is a complete `<?xml version=...?>` + `<svg>` document with
 * `xmlns` declared, so saving to disk and opening in a browser tab
 * works without any wrapping HTML. Bar geometry mirrors the on-screen
 * chart (same helpers) so the export reproduces the citizen's view.
 *
 * Out of scope for v1:
 *
 *  - **Pinned readout state**. Export captures the chart as the citizen
 *    sees it without overlays; the readout panel is interactive UI,
 *    not citizen-takeaway content. If a future user requests "export
 *    with my pinned period highlighted" we add a `pinnedPeriod` option.
 *  - **Inline labels**. The on-screen labels overlay HTML at percent
 *    coordinates which doesn't translate to the pixel-accurate export
 *    canvas without re-doing the layout. Legend at the bottom serves
 *    the same role for the export.
 *  - **Hatched stripes**. SVG `<pattern>` round-trips, but most
 *    standalone-SVG viewers (including Preview.app on macOS pre-13)
 *    silently drop pattern fills. Export uses a flat grey for missing
 *    so the citizen still sees the gap; the on-screen view keeps the
 *    pattern for clarity.
 */
export function buildExportSvg(
  model: StackedTrendV2Model,
  opts: BuildExportSvgOptions,
): string {
  const { mode } = opts;
  const title = model.headline?.text ?? `${model.dimension} over time`;
  const firstLabel = model.bars[0]?.period_label ?? "";
  const lastLabel =
    model.bars[model.bars.length - 1]?.period_label ?? "";
  const periodWindow =
    firstLabel === lastLabel
      ? firstLabel
      : `${firstLabel} – ${lastLabel}`;
  const modeLabel = mode === "percent" ? "Share" : "Total";
  const subtitle = `${modeLabel} · ${periodWindow}`;

  const visibleIds = visibleCategoryIds(model);
  const maxTotal = maxBarTotal(model.bars);

  const pitch = CHART_INNER_WIDTH / Math.max(1, model.bars.length);
  const barWidth = pitch * (1 - BAR_GAP_RATIO);

  // ---- bars + period labels ---------------------------------------
  const barEls: string[] = [];
  const periodLabelEls: string[] = [];

  model.bars.forEach((bar, i) => {
    const slotX = PAD_X + i * pitch;
    const x = slotX + (pitch - barWidth) / 2;
    const total = barTotal(bar);
    let cursorY = CHART_TOP + CHART_HEIGHT; // SVG y grows downward
    for (const seg of bar.segments) {
      if (seg.availability !== "present") continue;
      if (seg.value == null) continue;
      const heightPct = segmentVisualHeightPct(seg, total, maxTotal, mode);
      if (heightPct <= 0) continue;
      const heightPx = (heightPct / 100) * CHART_HEIGHT;
      cursorY -= heightPx;
      barEls.push(
        `<rect x="${x.toFixed(2)}" y="${cursorY.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${heightPx.toFixed(2)}" fill="${exportFillFor(seg.category_id, model)}" />`,
      );
    }
    // Missing-segment cap: flat grey rect above the present stack so
    // the citizen still sees there's missing data. No pattern fill —
    // see the docstring's "Hatched stripes" out-of-scope note.
    const hasMissing = bar.segments.some(
      (s) => s.availability !== "present",
    );
    if (hasMissing) {
      const capHeight = 6;
      const capY = cursorY - capHeight;
      barEls.push(
        `<rect x="${x.toFixed(2)}" y="${capY.toFixed(2)}" width="${barWidth.toFixed(2)}" height="${capHeight.toFixed(2)}" fill="#cbd5e1" />`,
      );
    }
    periodLabelEls.push(
      `<text x="${(slotX + pitch / 2).toFixed(2)}" y="${PERIOD_LABEL_Y}" text-anchor="middle" font-size="10" fill="#475569">${escapeSvgText(bar.period_label)}</text>`,
    );
  });

  // Baseline (zero line) so a sparse / mostly-missing series still
  // anchors to the x-axis.
  const baseline = `<line x1="${PAD_X}" y1="${CHART_TOP + CHART_HEIGHT}" x2="${EXPORT_WIDTH_PX - PAD_X}" y2="${CHART_TOP + CHART_HEIGHT}" stroke="#cbd5e1" stroke-width="0.5" />`;

  // ---- legend ------------------------------------------------------
  // Wraps to a second row if more than 4 categories at the desktop
  // width — keeps the footer line readable.
  const LEGEND_GAP_X = 90;
  const legendEls: string[] = [];
  visibleIds.forEach((id, idx) => {
    const col = idx % 6;
    const row = Math.floor(idx / 6);
    const lx = PAD_X + col * LEGEND_GAP_X;
    const ly = LEGEND_Y + row * 16;
    legendEls.push(
      `<rect x="${lx}" y="${ly - 8}" width="10" height="10" fill="${exportFillFor(id, model)}" />`,
    );
    legendEls.push(
      `<text x="${lx + 14}" y="${ly}" font-size="10" fill="#334155">${escapeSvgText(exportLabelFor(id, model))}</text>`,
    );
  });

  // ---- footer (provenance) ----------------------------------------
  const primary = pickPrimarySource(model);
  const footerText = primary
    ? `Source · ${composeCitation(primary)}`
    : "Source · (not specified)";

  return (
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<svg xmlns="http://www.w3.org/2000/svg" ` +
    `viewBox="0 0 ${EXPORT_WIDTH_PX} ${EXPORT_HEIGHT_PX}" ` +
    `width="${EXPORT_WIDTH_PX}" height="${EXPORT_HEIGHT_PX}" ` +
    `font-family="${FONT_FAMILY}">\n` +
    `  <rect x="0" y="0" width="${EXPORT_WIDTH_PX}" height="${EXPORT_HEIGHT_PX}" fill="#ffffff" />\n` +
    `  <text x="${PAD_X}" y="${TITLE_Y}" font-size="16" font-weight="600" fill="#0f172a">${escapeSvgText(title)}</text>\n` +
    `  <text x="${PAD_X}" y="${SUBTITLE_Y}" font-size="11" fill="#64748b">${escapeSvgText(subtitle)}</text>\n` +
    `  ${baseline}\n` +
    `  ${barEls.join("\n  ")}\n` +
    `  ${periodLabelEls.join("\n  ")}\n` +
    `  ${legendEls.join("\n  ")}\n` +
    `  <text x="${PAD_X}" y="${FOOTER_Y}" font-size="10" fill="#64748b">${escapeSvgText(footerText)}</text>\n` +
    `</svg>\n`
  );
}
