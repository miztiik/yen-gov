// SourceList v2 — pure formatting helpers (no DOM, no Svelte).
//
// Mirrors the contract of `backend/yen_gov/canonical/citation.render_citation`
// for the citizen-facing collapsed line. Composing a default citation from
// `(producer, title, vintage)` is the renderer's fallback when the upstream
// `citation_full` column is null — see the ADR-0032 v2.0 schema notes
// (`source.schema.json` → properties.citation_full.description).
//
// Per R-24 + CLAUDE.md §12: this file does NOT touch fetch-telemetry
// fields. It does NOT import them. It does NOT degrade gracefully if a
// caller sneaks one in — that path doesn't exist. The type system (see
// `types.ts`) is the only seam.

import type {
  CollapsedSummary,
  ExpandedDisclosure,
  SourceV2Row,
} from "./types";

/**
 * Compose the collapsed, citizen-facing summary line for one citation.
 *
 * Output shape:
 *   `<producer> · <authority-label> · <vintage>`
 *
 * - `authority-label` reads "official series" when `is_issuing_authority`
 *   is true, else "republished". This is the citizen-trust signal.
 * - `vintage` is omitted from `display` when empty (the v2 schema permits
 *   the rare "no vintage published" case as an empty string), but the
 *   structured field on `CollapsedSummary` is still set to `null` so
 *   downstream renderers can detect the absence.
 *
 * @example
 *   formatCollapsedSummary({
 *     producer: "Election Commission of India",
 *     is_issuing_authority: true,
 *     vintage: "AcGenApr2021",
 *     ...
 *   })
 *   //=> { producer: "Election Commission of India",
 *   //     authority_label: "official series",
 *   //     vintage: "AcGenApr2021",
 *   //     display: "Election Commission of India · official series · AcGenApr2021" }
 */
export function formatCollapsedSummary(row: SourceV2Row): CollapsedSummary {
  const authority_label: CollapsedSummary["authority_label"] = row.is_issuing_authority
    ? "official series"
    : "republished";
  const vintage_trim = row.vintage.trim();
  const vintage = vintage_trim.length > 0 ? vintage_trim : null;
  const parts = [row.producer, authority_label];
  if (vintage !== null) parts.push(vintage);
  return {
    producer: row.producer,
    authority_label,
    vintage,
    display: parts.join(" · "),
  };
}

/**
 * Compose the expanded-disclosure shape — every citizen-visible field
 * per R-24 + ADR-0032, with citation text resolved from the upstream
 * `citation_full` column when present and synthesised from
 * `(producer, title, vintage)` otherwise.
 *
 * Default composition mirrors backend `render_citation`:
 *   `<producer>, <title>[ (<vintage>)]`
 *
 * The vintage parenthetical is omitted when vintage is empty.
 */
export function formatExpandedDisclosure(row: SourceV2Row): ExpandedDisclosure {
  return {
    source_id: row.source_id,
    citation: row.citation_full ?? composeDefaultCitation(row),
    license: row.license,
    confidence_tier: row.confidence_tier,
    is_issuing_authority: row.is_issuing_authority,
    verification_method: row.verification_method,
    url_main: row.url_main,
    notes: row.notes,
  };
}

/**
 * Synthesise the default citation string when the upstream
 * `citation_full` column is null. Mirrors
 * `backend/yen_gov/canonical/citation.render_citation` so the frontend
 * and backend agree on the canonical render.
 */
export function composeDefaultCitation(
  row: Pick<SourceV2Row, "producer" | "title" | "vintage">,
): string {
  const vintage_trim = row.vintage.trim();
  const head = `${row.producer}, ${row.title}`;
  return vintage_trim.length > 0 ? `${head} (${vintage_trim})` : head;
}

/**
 * Trust-ordering rank for sorting / surfacing — lower rank is more trusted.
 * Mirrors `backend/yen_gov/canonical/citation.verification_method_rank`.
 *
 * Use case: when a chart cites multiple sources for the same data point
 * (e.g. live ECI + archived snapshot of an older revision), surface the
 * higher-trust one first in the disclosure list.
 */
export function verificationMethodRank(
  method: SourceV2Row["verification_method"],
): number {
  switch (method) {
    case "live-fetch":
      return 0;
    case "archived-snapshot":
      return 1;
    case "transcribed":
      return 2;
    case "editorial":
      return 3;
  }
}
