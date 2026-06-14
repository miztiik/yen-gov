// PR-2 vitest for `cleanNote()`.

import { describe, expect, it } from "vitest";
import { cleanNote } from "./clean-note";

describe("cleanNote", () => {
  it("returns a clean note unchanged (idempotency on already-clean input)", () => {
    const clean =
      "Parliament constituency boundaries shifted from the 1951-Order delimitation (used 1952-1962) to the 1962 Delimitation Commission output (used 1967 and 1971). Per-constituency comparisons across this year are not valid; per-state aggregates are.";
    expect(cleanNote(clean)).toBe(clean);
  });

  it("is idempotent: cleanNote(cleanNote(x)) === cleanNote(x)", () => {
    const raw =
      "Parliament constituency boundaries shifted from the 1951-Order delimitation (used 1952-1962) to the 1962 Delimitation Commission output. PR-4 of TODO/20260613-party-deferred-followups-plan.md (Max Q1.1d). PR-10 will render the marker on DualAxisBarLine.";
    const once = cleanNote(raw);
    const twice = cleanNote(once);
    expect(twice).toBe(once);
  });

  it("strips 'PR-N of TODO/foo.md (parenthetical).' sentences", () => {
    const raw =
      "Real content here. PR-4 of TODO/20260613-party-deferred-followups-plan.md (Max Q1.1d). More real content.";
    const out = cleanNote(raw);
    expect(out).toBe("Real content here. More real content.");
    expect(out).not.toMatch(/PR-\d+/);
    expect(out).not.toMatch(/TODO\//);
  });

  it("strips 'PR-N will render ...' sentences", () => {
    const raw =
      "Real content here. PR-10 will render the marker on DualAxisBarLine.";
    const out = cleanNote(raw);
    expect(out).toBe("Real content here.");
    expect(out).not.toMatch(/PR-\d+/);
  });

  it("strips the em-dash 'added alongside lspc-delim-...' narrative", () => {
    const raw =
      "Real content here. PR-4 of TODO/foo.md (Max Q1.1d) \u2014 added alongside lspc-delim-1967 + lspc-delim-1976 so the chain is represented. PR-10 will render the marker on DualAxisBarLine.";
    const out = cleanNote(raw);
    expect(out).toBe("Real content here.");
  });

  it("strips bare repo-grammar tokens (TODO/x.md, PR-N, lspc-delim-N, methodology_version=X)", () => {
    const raw =
      "Body text mentioning TODO/foo.md and PR-7 and lspc-delim-2008 and methodology_version=foo-bar. End.";
    const out = cleanNote(raw);
    expect(out).not.toMatch(/TODO\//);
    expect(out).not.toMatch(/PR-\d+/);
    expect(out).not.toMatch(/lspc-delim-\d+/);
    expect(out).not.toMatch(/methodology_version/);
    expect(out).toContain("Body text mentioning");
    expect(out).toContain("End.");
  });

  it("throws when the input strips to empty (defensive)", () => {
    expect(() => cleanNote("PR-4 lspc-delim-1967 methodology_version=foo")).toThrow(
      /stripped to empty/i,
    );
  });

  it("collapses double-spaces and leading/trailing whitespace introduced by scrubs", () => {
    const raw = "  A.  PR-9 of TODO/foo.md. B.  ";
    expect(cleanNote(raw)).toBe("A. B.");
  });
});
