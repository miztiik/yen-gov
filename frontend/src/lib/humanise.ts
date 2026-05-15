// Snake_case / kebab-case facet id → human-readable Title Case label.
//
// Used as the LAST-RESORT fallback in the facet-label resolution chain
// (caller-prop > artifact's indicator.facet_labels > humanise(id)). The
// composer SHOULD populate facet_labels on every facetted indicator
// (schema 1.4); this helper exists so a forgotten label never produces
// "other_thermal" in citizen-facing chart legends.
//
// Rules:
//   - Split on "_" or "-".
//   - Title-case each segment (first char upper, rest lower) — keeps
//     trailing acronyms like "mw" from over-capitalising; explicit
//     facet_labels override is the right answer for "MW", "GST", etc.
//   - Empty / non-string input returns "" so callers can still display
//     something (the chart's null-safety covers further downstream).

export function humanise(id: string | null | undefined): string {
  if (!id) return "";
  return id
    .split(/[_-]+/)
    .filter(Boolean)
    .map((s, i) => (i === 0 ? s[0].toUpperCase() + s.slice(1) : s.toLowerCase()))
    .join(" ");
}
