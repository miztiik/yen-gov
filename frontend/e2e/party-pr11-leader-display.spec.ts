// PR-11 of TODO/20260613-party-deferred-followups-plan.md section 13.
//
// Playwright e2e for the 4 PR-11 oracles:
//   1. BJP PartyPill on /parties shows the leader line "President: ...
//      Jagat Prakash Nadda . since 20 Jan 2020" on hover.
//   2. /parties/bjp header sub-line shows "Led by Jagat Prakash Nadda
//      (President since 20 Jan 2020)".
//   3. /parties/inc header sub-line shows the CURRENT president
//      (Mallikarjun Kharge) NOT the historic one (Sonia Gandhi) -
//      multi-term filtering via the `valid_to IS NULL` SQL clause.
//   4. /parties/independent (sentinel: parties.IN.IND) header OMITS
//      the leader line gracefully - sentinels do not have a leader
//      in the parliamentary sense and the data file carries no row
//      for them anyway.
//
// Honest-degradation note: the first Wikidata SPARQL snapshot (PR-9
// #1012) bound ~9 of 75 known Indian-party Q-ids. The Indian-party
// leadership graph on Wikidata is genuinely sparse; ~66 parties
// (including most regional + smaller parties) gracefully omit the
// leader line until a future snapshot + community editing fills the
// gap. No code change needed; the loader returns null for
// missing-row parties and the template hides the line.
//
// Path-B framing (per brief): the leader's "since" date is per-leader
// data the citizen cares about (term start). The historic "as of
// <vintage>" framing was dropped because v3.0 sources_simplification
// fixed the vintage on this CSV to the literal "continuous" (the
// SPARQL endpoint is continuously edited) - synthesising a fake
// snapshot date would have been a band-aid.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

// PR-4 party-detail page cold-loads ~177 MB candidate corpus into
// DuckDB-WASM; the /parties index pre-warms parties.csv too. Raise
// per-test timeout to 60s so the loader has headroom (same constraint
// PR-10 + PR-12 hit on cold vite).
test.setTimeout(60_000);

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual(
    [],
  );
});

test.describe("PR-11 leader display (PartyPill tooltip + Party header)", () => {
  test("Oracle 1: BJP PartyPill tooltip on /parties shows 'President: ... Nadda . since 2020'", async ({
    page,
  }) => {
    await page.goto("/parties", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("parties-loading")).toBeHidden({
      timeout: 30_000,
    });

    // BJP row in the index. The wrapping <a> carries data-party-id so
    // the test pins down the right row deterministically (party shorts
    // can collide via aliases - data-party-id is the safest selector).
    const bjp_row = page.locator('a[data-party-id="parties.IN.BJP"]');
    await expect(bjp_row).toBeAttached({ timeout: 10_000 });
    // Scroll into view (the parties index is alphabetically bucketed
    // A-Z; BJP can fall below the initial viewport even though it is
    // near the top alphabetically).
    await bjp_row.scrollIntoViewIfNeeded();
    await expect(bjp_row).toBeVisible();

    // PartyPill inside the row. PartiesIndex passes no `onclick` prop
    // so PartyPill renders the <span data-component="party-pill"
    // role="presentation"> branch (NOT the button branch); the
    // attribute-only selector covers both render paths.
    const bjp_pill = bjp_row.locator('[data-component="party-pill"]');
    await expect(bjp_pill).toBeVisible();
    // Hover triggers PartyPill.onmouseenter -> opens the portalled
    // PartyTooltip. force=true skips the actionability re-check (the
    // <a> wrapper sometimes intercepts pointer events on its hit-box;
    // the inner span is the real target).
    await bjp_pill.hover({ force: true });

    // Tooltip's BJP card surfaces. PartyTooltip.svelte stamps both
    // data-component AND data-party-id, so the selector pins exactly
    // ONE card even if a stale tooltip from a previous hover is still
    // animating out.
    const tooltip = page.locator(
      '[data-component="party-tooltip"][data-party-id="parties.IN.BJP"]',
    );
    await expect(tooltip).toBeVisible({ timeout: 10_000 });

    const leader_line = tooltip.getByTestId("tooltip-leader");
    await expect(leader_line).toBeVisible();
    // Anchor on the citizen-recognisable tokens (Nadda + President +
    // 2020 year). The exact rendered form is "President: Jagat Prakash
    // Nadda . since 20 Jan 2020" - asserting on tokens leaves the
    // formatter free to evolve typography (date separator, dot vs
    // bullet) without breaking the test.
    await expect(leader_line).toContainText("Nadda");
    await expect(leader_line).toContainText("President");
    await expect(leader_line).toContainText("2020");
  });

  test("Oracle 2: /parties/bjp header sub-line shows 'Led by Nadda (President since 20 Jan 2020)'", async ({
    page,
  }) => {
    await page.goto("/parties/bjp", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("party-loading")).toBeHidden({
      timeout: 30_000,
    });

    // Confirm we're on the right party detail page.
    await expect(page.getByTestId("party-detail")).toHaveAttribute(
      "data-party-id",
      "parties.IN.BJP",
    );

    const header = page.getByTestId("party-header");
    const leader_line = header.getByTestId("party-leader-line");
    await expect(leader_line).toBeVisible();
    await expect(leader_line).toContainText("Nadda");
    await expect(leader_line).toContainText("President");
    // "20 Jan 2020" -> year anchor + month anchor pin the formatter.
    await expect(leader_line).toContainText("2020");
    await expect(leader_line).toContainText("Jan");
  });

  test("Oracle 3: /parties/inc header shows CURRENT president (Kharge), historic (Sonia) suppressed", async ({
    page,
  }) => {
    await page.goto("/parties/inc", { waitUntil: "domcontentloaded" });
    await expect(page.getByTestId("party-loading")).toBeHidden({
      timeout: 30_000,
    });

    await expect(page.getByTestId("party-detail")).toHaveAttribute(
      "data-party-id",
      "parties.IN.INC",
    );

    const header = page.getByTestId("party-header");
    const leader_line = header.getByTestId("party-leader-line");
    await expect(leader_line).toBeVisible();
    // Current row per parties_leadership.csv: Mallikarjun Kharge,
    // valid_from = 2022-10-26, valid_to empty.
    await expect(leader_line).toContainText("Kharge");
    await expect(leader_line).toContainText("President");
    await expect(leader_line).toContainText("2022");
    await expect(leader_line).toContainText("Oct");
    // Historic row (Sonia Gandhi, valid_to = 2022-10-26) MUST NOT
    // surface - the loader's SQL filter `WHERE valid_to IS NULL OR
    // valid_to = ''` plus the per-key Map first-write-wins guard
    // both block it.
    await expect(leader_line).not.toContainText("Sonia");
  });

  test("Oracle 4: /parties/independent (IND sentinel) header omits leader line gracefully", async ({
    page,
  }) => {
    await page.goto("/parties/independent", {
      waitUntil: "domcontentloaded",
    });
    await expect(page.getByTestId("party-loading")).toBeHidden({
      timeout: 30_000,
    });

    // Confirm we landed on the IND sentinel page (the SENTINEL_SLUG_
    // OVERRIDES map routes /parties/independent -> parties.IN.IND).
    await expect(page.getByTestId("party-detail")).toHaveAttribute(
      "data-party-id",
      "parties.IN.IND",
    );

    const header = page.getByTestId("party-header");
    // Header MUST be present (the sentinel render path mounts the
    // same header card with the neutral grey avatar).
    await expect(header).toBeVisible();

    // Leader line MUST NOT render for sentinels. The dual guard is
    // (a) data carries no leadership row for parties.IN.IND, AND
    // (b) the template `{#if meta.leader && !meta.is_sentinel}` would
    // hide it even if a row appeared upstream.
    await expect(header.getByTestId("party-leader-line")).toHaveCount(0);

    // Defensive: the header MUST NOT carry the citizen-facing leader
    // phrasing tokens either - neither "President" nor "Led by".
    await expect(header).not.toContainText("Led by");
    await expect(header).not.toContainText("President");
  });
});
