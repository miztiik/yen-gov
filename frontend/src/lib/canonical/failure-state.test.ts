// Failure-state copy contract tests.
//
// Per canonical-store.md §16 + CLAUDE.md §15: the citizen MUST NEVER see
// raw error messages (which carry URLs, schema versions, internal paths).
// Every ManifestErrorKind MUST have plain-language copy. This test is the
// guardrail — if a new ManifestErrorKind is added to types.ts without a
// COPY_BY_KIND mapping, this test fails loud.

import { describe, expect, it } from "vitest";

import { allFailureCopyKeys, copyForError } from "./failure-state";
import type { ManifestError, ManifestErrorKind } from "./types";

const ALL_KINDS: ManifestErrorKind[] = [
  "not_found",
  "network",
  "malformed",
  "schema_version_unsupported",
  "table_not_found",
];

function makeError(kind: ManifestErrorKind): ManifestError {
  return {
    kind,
    message: `https://internal.example/path?schema_version=9.9 — stack trace at line 42`,
    table_id: "elections.election_results",
  };
}

describe("allFailureCopyKeys", () => {
  it("covers every ManifestErrorKind exactly once", () => {
    const keys = allFailureCopyKeys().slice().sort();
    expect(keys).toEqual(ALL_KINDS.slice().sort());
  });
});

describe("copyForError", () => {
  it.each(ALL_KINDS)("returns non-empty headline for %s", (kind) => {
    const copy = copyForError(makeError(kind));
    expect(copy.headline.length).toBeGreaterThan(0);
  });

  it.each(ALL_KINDS)("never leaks raw message for %s", (kind) => {
    const copy = copyForError(makeError(kind));
    // The raw message carries URLs, schema versions, and stack-shaped
    // strings. None of those should appear in citizen-facing copy.
    const combined = `${copy.headline}\n${copy.body}`;
    expect(combined).not.toContain("https://");
    expect(combined).not.toContain("9.9");
    expect(combined).not.toContain("stack");
    expect(combined).not.toContain("line 42");
    expect(combined).not.toContain("elections.election_results");
  });

  it("offers retry for transient kinds (network, schema_version_unsupported)", () => {
    expect(copyForError(makeError("network")).showRetry).toBe(true);
    // schema_version_unsupported retries because the typical fix is a
    // hard refresh (the user's bundle is stale relative to manifest).
    expect(copyForError(makeError("schema_version_unsupported")).showRetry).toBe(true);
  });

  it("does NOT offer retry for terminal kinds (not_found, malformed, table_not_found)", () => {
    expect(copyForError(makeError("not_found")).showRetry).toBe(false);
    expect(copyForError(makeError("malformed")).showRetry).toBe(false);
    expect(copyForError(makeError("table_not_found")).showRetry).toBe(false);
  });

  it("returns plain-English headlines (no jargon, no symbols)", () => {
    for (const kind of ALL_KINDS) {
      const { headline } = copyForError(makeError(kind));
      // Reject obvious developer-speak.
      expect(headline.toLowerCase()).not.toContain("error");
      expect(headline.toLowerCase()).not.toContain("exception");
      expect(headline.toLowerCase()).not.toContain("undefined");
      expect(headline.toLowerCase()).not.toContain("null");
      expect(headline).not.toMatch(/\{|\}|<|>/);
    }
  });
});
