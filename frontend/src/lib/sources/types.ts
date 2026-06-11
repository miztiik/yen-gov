// SourceRow: the canonical 5-col citation-ledger row shape, post v3.1.
//
// Mirrors the on-disk columns at `datasets/data/entities/source.csv` (and
// the schema declaration at `datasets/data/_schema/columns.json`):
//
//   source_id (PK), producer, title, vintage, url
//
// The 6 v2.0 fields (license, confidence_tier, is_issuing_authority,
// verification_method, citation_full, notes) are retired per the new
// inline ADR `citation-ledger-5col` in docs/concepts/data-provenance.md
// (2026-06-11). No enum types ship here.
//
// MIGRATING (PR-1 of TODO/20260611-sources-simplification-plan.md): the
// on-disk CSV header is still `owner`; the DuckDB seam in
// frontend/src/lib/duckdb.ts aliases `owner AS producer` until PR-1
// renames the header + drops the alias. The TypeScript type uses the
// canonical name (`producer`) from day one.
export interface SourceRow {
  /** Deterministic 12-char PK: src-<sha256(producer|title|vintage)[:12]>. */
  source_id: string;
  /** Publisher organisation, verbatim from the source. OWID origin.producer. */
  producer: string;
  /** Citizen-readable report name, verbatim. OWID origin.title. */
  title: string;
  /** Strongest period anchor available (publisher edition OR operator
   *  snapshot window). Non-empty per ADR-0042 v3.0. OWID origin.vintage. */
  vintage: string;
  /** Landing/publisher page URL. Empty when hand-imported / transcribed /
   *  editorial. yen-gov ships one URL field (no url_download distinction),
   *  hence `url` not OWID's `url_main`. */
  url: string | null;
}

// PublisherPill: the deduped view-model output one chart card footer
// renders. One pill per (producer x series_family) where series_family
// is derived from the leading clause of `title`. Multiple SourceRow
// instances with the same (producer, series_family) collapse to one
// pill; the vintage_summary names the range or set of vintages
// contributing.
//
// View-model produces PublisherPill[] via `dedupeToPills(rows)`. The
// SourceList Svelte component renders the array; it does NOT consume
// raw SourceRow[].
export interface PublisherPill {
  /** Display label rendered as the pill's text. Examples:
   *  "RBI State Finances", "ECI", "Wikipedia", "yen-gov".
   *  Length: 2-40 chars typically; soft cap at ~30 before the vintage
   *  suffix is appended in the renderer. */
  label: string;
  /** Vintage summary string. Examples:
   *  "2025-26"            (single vintage)
   *  "2022-23 to 2025-26" (contiguous FY range, detected by string sort)
   *  "various"            (mixed non-range vintages)
   *  ""                   (no vintage on any contributing row)
   *  Rendered as " (<vintage_summary>)" suffix on the pill when non-empty. */
  vintage_summary: string;
  /** Click target. First non-null `url` among contributing rows; null if
   *  every contributing row has no url (pill renders as plain text, not link). */
  url: string | null;
  /** Number of SourceRow entries that collapsed into this pill. >=1.
   *  Used by the renderer for "+N more" overflow when total pills > 3. */
  count: number;
}
