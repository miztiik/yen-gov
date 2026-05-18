// LoaderResult discriminated union + failure-state copy contract.
//
// Per canonical-store.md §16: every loader returns one of four states;
// renderers MUST handle all four. The `failed` state renders plain-
// language copy (no stack traces) with a retry button.
//
// This module is the SINGLE source for failure-state copy. New error
// kinds get a copy mapping here, not invented inline at the renderer.

import type { ManifestError, ManifestErrorKind } from "./types";

export type LoaderResult<T> =
  | { status: "ok"; data: T }
  | { status: "loading" }
  | { status: "partial"; data: T; reason: string }
  | { status: "failed"; reason: string };

export interface FailureCopy {
  /** One-line heading the citizen sees. Imperative voice, plain English. */
  headline: string;
  /** Optional one-line body explaining what (if anything) the citizen can
   *  do. Empty string when the headline is sufficient on its own. */
  body: string;
  /** Whether a Retry button should be offered. False for "not found" and
   *  for malformed data — retrying won't help; the operator needs to fix
   *  the upstream artifact. */
  showRetry: boolean;
}

/** Map a typed ManifestError onto plain-language copy. Never leaks the
 *  raw `message` field (which often contains URLs, schema versions, or
 *  internal-looking strings the citizen shouldn't see). */
export function copyForError(error: ManifestError): FailureCopy {
  return COPY_BY_KIND[error.kind];
}

const COPY_BY_KIND: Record<ManifestErrorKind, FailureCopy> = {
  not_found: {
    headline: "This data isn't available yet.",
    body: "Check back later — we haven't published this dataset for the current selection.",
    showRetry: false,
  },
  network: {
    headline: "Could not load this data right now.",
    body: "Your connection may be slow. Try again in a moment.",
    showRetry: true,
  },
  malformed: {
    headline: "We received this data, but couldn't read it.",
    body: "This is being fixed. Please try again later.",
    showRetry: false,
  },
  schema_version_unsupported: {
    headline: "This page is out of date.",
    body: "Refresh the page to load the current version.",
    showRetry: true,
  },
  table_not_found: {
    headline: "This data isn't available yet.",
    body: "Other sections of the page may still work.",
    showRetry: false,
  },
};

/** Return the canonical copy keys. Used by tests + by audit tooling that
 *  needs to enumerate every possible failure-state surface in CI. */
export function allFailureCopyKeys(): ManifestErrorKind[] {
  return Object.keys(COPY_BY_KIND) as ManifestErrorKind[];
}
