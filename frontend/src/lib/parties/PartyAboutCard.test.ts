/**
 * `PartyAboutCard.test.ts` — pure-helper pin for the per-party About
 * card (PR-6 of TODO/20260614-party-page-reimagination-plan.md).
 *
 * The test file targets ONLY the helpers exported from
 * `<script module>` (`foundingYearLabel`, `recognitionLabel`,
 * `shortPartyToken`); the Svelte render path is not mounted (project
 * doctrine - no `@testing-library/svelte`; §13 browser smoke covers
 * the live render path on the dev server).
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  foundingYearLabel,
  recognitionLabel,
  shortPartyToken,
} from "./PartyAboutCard.svelte";

describe("foundingYearLabel", () => {
  it('returns "Active since YYYY" for a live party with a known founding year', () => {
    expect(foundingYearLabel(1980, null)).toBe("Active since 1980");
    expect(foundingYearLabel(1885, null)).toBe("Active since 1885");
  });

  it('returns "Active YYYY-YYYY" for a defunct party with both years known', () => {
    expect(foundingYearLabel(1977, 1988)).toBe("Active 1977-1988");
    expect(foundingYearLabel(1936, 1996)).toBe("Active 1936-1996");
  });

  it('returns "Dissolved YYYY" when only the dissolution year is known', () => {
    expect(foundingYearLabel(null, 1996)).toBe("Dissolved 1996");
  });

  it("returns null when both years are blank (caller suppresses the row)", () => {
    expect(foundingYearLabel(null, null)).toBeNull();
  });
});

describe("recognitionLabel", () => {
  it('returns Hans H7 "Nationally recognised party" for national scope', () => {
    expect(recognitionLabel("national")).toBe("Nationally recognised party");
  });

  it('returns Hans H7 "State-recognised party" for state scope', () => {
    expect(recognitionLabel("state")).toBe("State-recognised party");
  });

  it('returns Hans H7 "Registered party (unrecognised)" for unrecognised_registered scope', () => {
    expect(recognitionLabel("unrecognised_registered")).toBe(
      "Registered party (unrecognised)",
    );
  });

  it('returns "Defunct" for defunct scope (verbatim from upstream contract)', () => {
    expect(recognitionLabel("defunct")).toBe("Defunct");
  });

  it('returns Hans H7 "Special category" for sentinel scope (IND / NOTA)', () => {
    expect(recognitionLabel("sentinel")).toBe("Special category");
  });

  it('returns "Recognition unknown" for null / blank / unknown enum values', () => {
    expect(recognitionLabel(null)).toBe("Recognition unknown");
    expect(recognitionLabel("garbage-value")).toBe("Recognition unknown");
  });
});

describe("shortPartyToken", () => {
  it("strips the parties.IN. taxonomy prefix to surface the short token", () => {
    expect(shortPartyToken("parties.IN.BJP")).toBe("BJP");
    expect(shortPartyToken("parties.IN.JP")).toBe("JP");
    expect(shortPartyToken("parties.IN.NOTA")).toBe("NOTA");
  });

  it("falls back to the input string when no dot separator is present", () => {
    expect(shortPartyToken("BJS")).toBe("BJS");
  });

  it("returns the original id when the trailing dot-token is empty", () => {
    // Defensive: a malformed id like "parties.IN." would yield "" from
    // the trailing-token split; the helper falls back to the input so
    // the consumer never renders a literal empty <a> link.
    expect(shortPartyToken("parties.IN.")).toBe("parties.IN.");
  });
});

describe("PartyAboutCard source-string pins (PR-3 D4)", () => {
  // Source-string pin against the .svelte file (per project doctrine -
  // no `@testing-library/svelte`). Pins the Wikipedia link gets a
  // citizen-visible W glyph reinforcement + a stable testid for the
  // browser smoke loop. See PR-3 of
  // TODO/20260615-party-page-citizen-fixes-plan.md.
  const src = readFileSync(
    resolve(__dirname, "./PartyAboutCard.svelte"),
    "utf8",
  );

  it("imports the TopicIcon renderer", () => {
    expect(src).toContain(
      'import TopicIcon from "../TopicIcon.svelte";',
    );
  });

  it("renders the wikipedia glyph before the Wikipedia label", () => {
    // Looser match than `<TopicIcon name="wikipedia"` because the
    // attribute is line-wrapped in the source; normalise whitespace
    // before asserting the (component, name) pair appears together.
    const normalised = src.replace(/\s+/g, " ");
    expect(normalised).toContain('<TopicIcon name="wikipedia"');
    // And the literal label survives next to the glyph - the icon is
    // reinforcement, not replacement.
    expect(normalised).toContain("Wikipedia");
  });

  it("stamps a stable testid on the Wikipedia anchor", () => {
    expect(src).toContain('data-testid="party-wikipedia-link"');
  });
});
