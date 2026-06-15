/**
 * Static-source contract test for StateElection.svelte (R4 of
 * TODO/20260615-state-election-event-page-redesign-plan.md, 2026-06-15).
 *
 * Doctrine: this surface (`/<state>/elections/<event>`) carries a
 * citizen-first IA contract that PR-1048/PR-1049 demonstrated must be
 * frozen at the vitest gate, not just at e2e absence-guard time:
 * worktree-staleness merges have silently reverted similar guarantees
 * before. The test reads `StateElection.svelte` off disk and asserts
 * the four orthogonal section-order / chrome rules baked into the R4
 * verdict (plan-doc Section 5 + Section 0.1 Jony + Citizen converge):
 *
 *  1. StateEventScatter MUST mount BEFORE StateEventConstituencyList in
 *     the template DOM order. The reverse order (current pre-R4
 *     baseline) hid the turnout-vs-margin context behind the long
 *     per-AC table.
 *
 *  2. SiblingEventsRail MUST be present + mounted AFTER StateEventHero
 *     (the year-chip rail replaces the deleted Prev/Next/Compare text
 *     strip; rail goes right under the hero so the citizen sees their
 *     position in time before any visual).
 *
 *  3. InlineCounterfactualSwing MUST NOT be mounted on this surface
 *     (counterfactual ergonomics live on /psephlab; per the
 *     2026-06-15 plan-doc decision the state-event page is the
 *     canonical fact view, not the what-if surface). The component
 *     file is retained because Psephlab still uses it; only this
 *     mount is forbidden.
 *
 *  4. The forbidden phrase "View latest election" (and the related
 *     "Latest election:" / "Go to latest election" set) must not
 *     appear in this route's template - the per-card cross-family
 *     CTA rip (PR-1048 / PR-1049) extends to the per-route page
 *     chrome here too.
 *
 * Negative-control gate: re-inject any of the deleted patterns
 * locally; this test goes RED in <10ms with concrete failure
 * messages naming the offending mount. Revert; goes GREEN. The
 * test is strictly stronger than the e2e absence guard at
 * `frontend/e2e/state-event-view.spec.ts` because it runs on every
 * `bun run test` on every developer's machine - the next
 * worktree-staleness accident will fail at the vitest gate, not
 * after 4 days of users seeing the wrong order.
 *
 * Pattern precedent (user-memory lesson 2026-06-15):
 * `frontend/src/lib/IndicatorCard.no-cross-family-chrome.test.ts` +
 * `frontend/src/lib/elections/AllianceTotals.no-pending-pill.test.ts`.
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const SOURCE = readFileSync(
  resolve(__dirname, "../../routes/StateElection.svelte"),
  "utf8",
);

// Template region = everything after the last </script> tag. The
// instance script's doc comments name the deleted chrome on purpose
// (so future readers know WHY it is gone); the contract test MUST
// NOT trip on its own docstring.
const TEMPLATE_START = SOURCE.lastIndexOf("</script>");
if (TEMPLATE_START < 0) {
  throw new Error(
    "StateElection.svelte has no </script> tag - file shape changed? " +
      "Update this contract test if the script-then-template layout " +
      "was intentionally replaced.",
  );
}
const TEMPLATE = SOURCE.slice(TEMPLATE_START);

describe("StateElection.svelte - R4 IA + chrome contract", () => {
  it("mounts StateEventScatter BEFORE StateEventConstituencyList", () => {
    const scatter_at = TEMPLATE.indexOf("<StateEventScatter");
    const list_at = TEMPLATE.indexOf("<StateEventConstituencyList");
    expect(
      scatter_at,
      "StateEventScatter mount not found in StateElection.svelte template",
    ).toBeGreaterThanOrEqual(0);
    expect(
      list_at,
      "StateEventConstituencyList mount not found in StateElection.svelte template",
    ).toBeGreaterThanOrEqual(0);
    expect(
      scatter_at < list_at,
      `StateEventScatter MUST mount BEFORE StateEventConstituencyList per R4 ` +
        `Section 5 verdict (citizen reads turnout-vs-margin context before ` +
        `diving into the per-AC list). Found: scatter at ${scatter_at}, ` +
        `list at ${list_at}. If this is intentional, the R4 IA contract has ` +
        `changed; update plan-doc Section 5 + this test.`,
    ).toBe(true);
  });

  it("mounts SiblingEventsRail AFTER StateEventHero", () => {
    const hero_at = TEMPLATE.indexOf("<StateEventHero");
    const rail_at = TEMPLATE.indexOf("<SiblingEventsRail");
    expect(
      hero_at,
      "StateEventHero mount not found in StateElection.svelte template",
    ).toBeGreaterThanOrEqual(0);
    expect(
      rail_at,
      "SiblingEventsRail mount not found in StateElection.svelte template - " +
        "R4 J-elevated-4 verdict requires the year-chip rail under the hero.",
    ).toBeGreaterThanOrEqual(0);
    expect(
      hero_at < rail_at,
      `SiblingEventsRail MUST mount AFTER StateEventHero per R4 J-elevated-4 ` +
        `verdict (the citizen reads the headline, then the temporal rail, ` +
        `then dives into visuals). Found: hero at ${hero_at}, rail at ${rail_at}.`,
    ).toBe(true);
  });

  it("does NOT mount InlineCounterfactualSwing", () => {
    const mounted = TEMPLATE.includes("<InlineCounterfactualSwing");
    expect(
      mounted,
      "InlineCounterfactualSwing MUST NOT be mounted on the state-event " +
        "page per R4 plan-doc Section 5 (counterfactual ergonomics live on " +
        "/psephlab; the state-event page is the canonical fact view). The " +
        "component file is retained because Psephlab still mounts it; only " +
        "this mount is forbidden. If you're restoring it, the R4 verdict " +
        "has changed - update plan-doc Section 5 + this test.",
    ).toBe(false);
  });

  it("does NOT import InlineCounterfactualSwing", () => {
    // Import line cleanup tracks the mount deletion: stale imports
    // would survive an attempt to revert just the mount via copy-paste,
    // and the dead-import sweep is part of the R4 RIP doctrine.
    // The check matches only ES-import lines so the post-mortem doc
    // comment in the template that names the deleted mount on purpose
    // (so future readers know WHY it is gone) does not trip the gate.
    const IMPORT_RE =
      /^\s*import\s+[\s\S]*?InlineCounterfactualSwing[\s\S]*?from\s+['"][^'"]+['"]/m;
    const imported = IMPORT_RE.test(SOURCE);
    expect(
      imported,
      "StateElection.svelte must not retain the InlineCounterfactualSwing " +
        "import after R4. The mount is deleted; the import is dead. " +
        "Delete both in the SAME PR (RIP doctrine).",
    ).toBe(false);
  });

  it("does NOT render the forbidden 'View latest election' chrome in the template", () => {
    // Mirrors the IndicatorCard no-cross-family-chrome contract for
    // this per-route surface. Catches the case where a future
    // copy-paste lands the deleted phrase as a header link / footer
    // CTA / etc., bypassing the SiblingEventsRail's structured
    // Compare-pill seam.
    const FORBIDDEN = [
      "View latest election",
      "Latest election:",
      "Go to latest election",
      "See the latest election",
    ];
    const hits = FORBIDDEN.filter((p) => TEMPLATE.includes(p));
    expect(
      hits,
      `StateElection.svelte template contains forbidden CTA phrase(s): ` +
        `${hits.join(", ")}. The structured SiblingEventsRail + the Compare ` +
        `pill at the rail's tail are the ONLY semantic prev/next chrome on ` +
        `this surface; ad-hoc text CTAs are forbidden per R4 J-elevated-4.`,
    ).toEqual([]);
  });
});
