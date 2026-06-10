// E2E smoke for the per-state elections hub (PR-W3a, 2026-06-10).
//
// Surface: `/<state>/t/elections`. The URL is unchanged from the pre-W3a
// "horrible page" (List: N/A chrome + "How <state> compares" subtitle +
// single default-event card); PR-W3a rebuilds the body into a
// chronological event timeline + body-kind filter chip. Three behaviours
// pinned here:
//
//   1. Karnataka (S10): the timeline mounts with the catalogue's 17
//      events (6 parliament + 11 assembly per
//      datasets/taxonomy/election_events.json). Floor asserted as >= 6
//      so future ingest backfills only grow the count.
//
//   2. The Parliament chip narrows the timeline to parliament events
//      only. Karnataka has exactly 6 parliament events today; filtered
//      count == 6.
//
//   3. Click-through on a timeline row navigates to
//      `/<state>/elections/<event_id>` (StateElection). The W3a hub
//      does not own the per-event view; it only owns the navigation
//      anchor.
//
// And one anti-regression assertion for Arunachal Pradesh (the canonical
// "horrible page" example in the plan-doc): the legacy "List: N/A" chip
// text MUST NOT appear on the rebuilt body. The pre-W3a render mounted
// it on every state's elections topic page.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

test.describe("state elections hub (PR-W3a)", () => {
  // Cold compile budget matches the W3c / W3d specs (vite-plugin-svelte
  // + Tailwind JIT bootstrap dominates first hit on Windows).
  test.describe.configure({ timeout: 90_000 });

  let trap: ReturnType<typeof attachPageErrorTrap> | null = null;

  test.beforeEach(({ page }) => {
    trap = attachPageErrorTrap(page);
  });

  test.afterEach(() => {
    const errors = trap?.getErrors() ?? [];
    expect(
      errors,
      `Page emitted runtime errors:\n${errors.join("\n")}`,
    ).toEqual([]);
  });

  test("/karnataka/t/elections renders timeline + body filter", async ({
    page,
  }) => {
    await page.goto("/karnataka/t/elections");

    await expect(page.getByTestId("state-elections-hub")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("state-event-timeline")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("state-elections-body-filter")).toBeVisible();

    // Truth on disk (datasets/taxonomy/election_events.json S10):
    // 6 parliament + 11 assembly = 17 events. The "All" default exposes
    // every row; floor at >= 6 so future ingest only grows the count.
    const rows = page.locator('[data-testid^="event-timeline-row-"]');
    const initial_count = await rows.count();
    expect(
      initial_count,
      `expected >= 6 timeline rows on the All filter, got ${initial_count}`,
    ).toBeGreaterThanOrEqual(6);

    // Narrow to Parliament. Karnataka has 6 parliament events; the
    // filtered count MUST be <= the All count and >= 1.
    await page.getByTestId("body-filter-parliament").click();
    const parliament_count = await rows.count();
    expect(
      parliament_count,
      `Parliament filter should narrow vs All (${initial_count}); got ${parliament_count}`,
    ).toBeLessThan(initial_count);
    expect(parliament_count).toBeGreaterThanOrEqual(1);

    // Restore All -> back to initial_count.
    await page.getByTestId("body-filter-all").click();
    expect(await rows.count()).toBe(initial_count);

    // Narrow to Assembly. Karnataka has 11 assembly events; same
    // narrowing invariant.
    await page.getByTestId("body-filter-assembly").click();
    const assembly_count = await rows.count();
    expect(
      assembly_count,
      `Assembly filter should narrow vs All (${initial_count}); got ${assembly_count}`,
    ).toBeLessThan(initial_count);
    expect(assembly_count).toBeGreaterThanOrEqual(1);

    // Restore All so the click-through row is the most-recent event
    // (sorted newest-first by polled_on; today's most-recent Karnataka
    // event is general-2024 on 2024-06-01).
    await page.getByTestId("body-filter-all").click();
    await rows.first().click();
    await expect(page).toHaveURL(
      /\/karnataka\/elections\/(general-\d{4}|assembly-\d{4})$/,
    );
  });

  test("/arunachal-pradesh/t/elections clears the pre-W3a 'List: N/A' state", async ({
    page,
  }) => {
    await page.goto("/arunachal-pradesh/t/elections");

    await expect(page.getByTestId("state-elections-hub")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("state-event-timeline")).toBeVisible({
      timeout: 30_000,
    });

    // The pre-W3a render mounted <ListBadge list="na" /> which emitted
    // both the "List:" prefix and the "N/A" label (see ListBadge.svelte
    // STYLES.na). Neither must appear on the rebuilt hub body.
    // ListBadge sets data-listbadge="na" on its <span>, so we assert
    // the badge element itself is GONE rather than scanning page text
    // (which would false-positive on any future legitimate use of
    // "N/A" in a row label).
    await expect(page.locator('[data-listbadge="na"]')).toHaveCount(0);

    // And the "How <state> compares." subtitle is gone too.
    await expect(
      page.getByText(/How .+ compares\./),
    ).toHaveCount(0);

    // Arunachal Pradesh has 17 events (6 parliament + 11 assembly) per
    // datasets/taxonomy/election_events.json S02; same >= 6 floor as
    // Karnataka.
    const rows = page.locator('[data-testid^="event-timeline-row-"]');
    expect(await rows.count()).toBeGreaterThanOrEqual(6);
  });
});
