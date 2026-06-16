/**
 * Static-source contract test for AllianceTotals.svelte (R6 of the
 * state-event-page redesign plan, 2026-06-15).
 *
 * Doctrine: per Max + Hans verdict in plan-doc Section 0.1, the
 * AllianceTotals panel renders ONLY when the (event_id, state) lookup
 * returns >=1 alliance row. There is no "Alliance data pending" pill;
 * uncurated events are silently absent from the page. Debt tracking
 * lives at datasets/_ops/ + the operator-receipt surface, not on the
 * citizen page.
 *
 * This test reads `AllianceTotals.svelte` off disk and asserts the
 * forbidden phrases / testids never reappear via a future regression
 * (the standard "static-source contract" pattern used by
 * `IndicatorCard.no-cross-family-chrome.test.ts` per user-memory
 * lesson 2026-06-15).
 *
 * Negative-control gate: re-inject the pending pill block locally;
 * this test goes RED in <10ms with concrete failure messages naming
 * each forbidden string. Revert; goes GREEN. The contract test is the
 * load-bearing oracle that R6's silence-on-uncurated rule does not
 * regress to the amber pending pill on a future worktree-staleness
 * accident.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const SOURCE = readFileSync(
  resolve(__dirname, "AllianceTotals.svelte"),
  "utf8",
);

// Split the source so the contract scans only the TEMPLATE region
// (everything after the last </script>). The instance script comment
// names the deleted doctrine on purpose; the test MUST NOT trip on
// its own docstring.
const TEMPLATE = SOURCE.slice(SOURCE.lastIndexOf("</script>"));

const FORBIDDEN_TEMPLATE_TESTIDS = ["alliance-totals-pending"];

const FORBIDDEN_TEMPLATE_PHRASES = [
  "Alliance data pending",
  "alliance data pending",
  // amber-pending pill classes the prior shape used (bg-amber-50 /
  // text-amber-800). Re-introducing either class signals the pill is
  // back even if the testid was renamed.
  "bg-amber-50",
  "text-amber-800",
];

describe("AllianceTotals.svelte: no pending pill (R6 honesty rule)", () => {
  it("does NOT mount the `alliance-totals-pending` testid in the template", () => {
    const found = FORBIDDEN_TEMPLATE_TESTIDS.filter((id) =>
      TEMPLATE.includes(`data-testid="${id}"`),
    );
    expect(
      found,
      `AllianceTotals.svelte template contains forbidden testid(s): ${found.join(", ")}. ` +
        "R6 (TODO/20260615-state-election-event-page-redesign-plan.md) " +
        "deleted the amber 'Alliance data pending for this event.' pill " +
        "per Max + Hans verdict. The entire <section> is now suppressed " +
        "when the lookup returns zero rows. If you're restoring the pill, " +
        "the doctrine in plan-doc Section 0.1 has changed; update the test.",
    ).toEqual([]);
  });

  it("does NOT contain the pending-pill copy or amber chrome in the template", () => {
    const found = FORBIDDEN_TEMPLATE_PHRASES.filter((p) => TEMPLATE.includes(p));
    expect(
      found,
      `AllianceTotals.svelte template contains forbidden phrase(s): ${found.join(", ")}. ` +
        "Per R6 silence-on-uncurated rule, the pending pill and its amber " +
        "color tokens MUST NOT be reintroduced. Uncurated events render " +
        "no panel at all.",
    ).toEqual([]);
  });

  it("emits the R6 honesty caption in the populated branch", () => {
    // Positive control: the new R6 caption MUST appear in the template
    // alongside the headline + breakdown, so the citizen always sees
    // the pre-poll-vs-post-poll attribution alongside any alliance
    // total. The caption is wired via the source_title prop.
    expect(TEMPLATE).toContain("alliance-totals-honesty-caption");
    expect(TEMPLATE).toContain("Pre-poll alliance composition");
    expect(TEMPLATE).toContain(
      "Post-election government formation may differ",
    );
  });
});
