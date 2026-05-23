// SourceList v2 — citizen-facing chart footer contract.
//
// These types describe the **read-only consumer shape** of a single row from
// `taxonomy.sources` (the manifest-registered v2.0 citation ledger per
// ADR-0032). This file is the boundary between the canonical store and
// the chart-shell / footer chrome (Phase 1.4 of
// TODO/20260518-frontend-charting-modernisation-plan.md).
//
// R-24 — citizen-facing footer chrome reads ONLY the v2.0 ledger fields.
// Fetch telemetry (`first_fetched_at`, `last_seen_at`, `date_accessed`,
// `content_hash`) was retired from the canonical contract per ADR-0032
// P.0e and MUST NOT appear in any footer surface. Those fields live in
// `.runtime/<adapter>/<source_id>.json` sidecars for cache invalidation
// only — they describe *fetch telemetry*, not *citation identity*.
//
// R-28 — the consumer (SourceList v2) resolves the parquet location via
// `datasets/manifest.json` → `table_id: "taxonomy.sources"`. NEVER
// hardcode `/data/taxonomy/sources.parquet` at any call site.
//
// Structural-only PR (Phase 1.4 step 1): this file ships the types + the
// pure formatting helpers. The existing `frontend/src/lib/SourceList.svelte`
// (which uses the retired `SourceRef.fetched_at`) is NOT touched in this
// PR — the v2 migration of the render surface lands in a follow-up once
// the contract is stable.

/**
 * License enum, locked to ADR-0032 § Sources ledger. Mirrored from
 * `datasets/schemas/source.schema.json` (v2.0).
 */
export type SourceLicense =
  | "OGL-IN-1.0"
  | "CC-BY-4.0"
  | "CC0-1.0"
  | "public-domain"
  | "unknown-public"
  | "internal";

/**
 * Confidence tier — curation discipline for Indian mixed-quality data shelves.
 *
 * - `gold`   issuing authority publishing its own primary data (ECI, MoSPI, RBI)
 * - `silver` reputable secondary republisher / research aggregator (PRS, CMIE, OWID-import)
 * - `bronze` single-paper / unverified mirror — surface with citizen-visible caveat
 */
export type ConfidenceTier = "gold" | "silver" | "bronze";

/**
 * Verification method — how yen-gov knows the citation reflects what the
 * producer actually published. Trust ordering live-fetch > archived-snapshot
 * > transcribed > editorial (see
 * `backend/yen_gov/canonical/citation.verification_method_rank`).
 */
export type VerificationMethod =
  | "live-fetch"
  | "archived-snapshot"
  | "transcribed"
  | "editorial";

/**
 * A single row from `taxonomy.sources` (v2.0 schema). The 11-column
 * citation ledger per ADR-0032.
 *
 * Natural identity = `(producer, title, vintage)`. `source_id` is a
 * deterministic 12-char hex prefix of `sha256(f"{producer}|{title}|{vintage}")`
 * (NOT random, NOT autoincrement).
 */
export interface SourceV2Row {
  /** PK. Deterministic `src-` + 12 hex chars from sha256 of the citation triple. */
  readonly source_id: string;
  /** Publisher organisation. Part of the citation identity triple. */
  readonly producer: string;
  /** The thing being cited. Part of the citation identity triple. */
  readonly title: string;
  /** Source's own period/revision label, preserved as-published. May be empty. */
  readonly vintage: string;
  /** Locked enum — see SourceLicense. */
  readonly license: SourceLicense;
  readonly confidence_tier: ConfidenceTier;
  /** True iff producer is the official issuing authority for this data. */
  readonly is_issuing_authority: boolean;
  readonly verification_method: VerificationMethod;
  /** Landing/about URL. Null when archived-snapshot/transcribed/editorial. */
  readonly url_main: string | null;
  /** Full bibliographic citation when adapter has overridden the default render. */
  readonly citation_full: string | null;
  /** Operator-visible free-text note; NOT citizen-facing. */
  readonly notes: string | null;
}

/**
 * The **forbidden** field names that the v2.0 pivot retired from the
 * canonical sources contract. Exported as a compile-time constant so
 * contract tests can assert any of these reappearing under
 * `datasets/schemas/source.schema.json` fails loud.
 *
 * Per ADR-0032 P.0e + R-24 + CLAUDE.md §12.
 */
export const FORBIDDEN_SOURCE_FIELDS: readonly string[] = Object.freeze([
  "url",
  "content_hash",
  "url_download",
  "date_accessed",
  "first_fetched_at",
  "last_seen_at",
  "fetched_at",
]);

/**
 * The collapsed, citizen-facing summary line for a single citation —
 * what the chart footer shows by default before the disclosure triangle
 * is opened.
 *
 * Example: `"Election Commission of India · official series · AcGenApr2021"`
 *
 * Composed from:
 * - producer (always)
 * - "official series" if `is_issuing_authority`, else "republished"
 * - vintage when non-empty
 */
export interface CollapsedSummary {
  readonly producer: string;
  readonly authority_label: "official series" | "republished";
  readonly vintage: string | null;
  /** Composed display string `"producer · authority · vintage"`. */
  readonly display: string;
}

/**
 * The expanded disclosure shape. Each field maps one-to-one onto a v2
 * ledger column; this interface exists so the renderer cannot silently
 * grow new fetch-telemetry surfaces (R-24 enforcement at the type level).
 */
export interface ExpandedDisclosure {
  readonly source_id: string;
  readonly citation: string;
  readonly license: SourceLicense;
  readonly confidence_tier: ConfidenceTier;
  readonly is_issuing_authority: boolean;
  readonly verification_method: VerificationMethod;
  readonly url_main: string | null;
  readonly notes: string | null;
}
