// E2E smoke for the 2014 LS MP affidavit panel (Row D of
// TODO/20260614-three-ephemeral-ingests-plan.md).
//
// Visits the PR-W3b bare 4-segment leaf route for a Maharashtra
// PC with non-null Form-26 affidavit data:
//
//   /maharashtra/elections/general-2014/buldhana
//
// (state=maharashtra, event=general-2014, pc=Buldhana,
//  delim=2008, eci_no=5; affidavit row has criminal_cases=2 and
//  non-null assets/liabilities/expense). The PC was chosen because
//  ALL four affidavit columns are populated AND criminal_cases > 0
//  so the panel surfaces every row including the rare "non-zero
//  criminal cases" case.
//
// Asserts:
//   1. The EntityProfilePanel mounts.
//   2. The amber banner is visible (self-declared, not adjudicated).
//   3. The provenance footer is visible.
//   4. The rows list mounts with at least one row.
//   5. The panel does NOT mount on a 2024 LS event (affidavit data
//      not yet ingested for 2024 — that's a future PR).

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

test.describe("MP affidavit panel (Row D, general-2014)", () => {
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

  test("renders panel + banner + provenance for /maharashtra/elections/general-2014/buldhana", async ({
    page,
  }) => {
    await page.goto("/maharashtra/elections/general-2014/buldhana");

    // Wait for the PC drill-down section to render (the panel mounts
    // alongside it, so this is the right gate).
    await expect(
      page.getByTestId("constituency-pc-winner"),
    ).toBeVisible({ timeout: 30_000 });

    // The EntityProfilePanel mounts only when the loader returned
    // non-null rows. 15s allows for the post-mount DuckDB-WASM read.
    const panel = page.getByTestId("entity-profile-panel");
    await expect(panel).toBeVisible({ timeout: 15_000 });

    // entity_kind="mp" passes through to a data-attr (cosmetic; e2e/QA only).
    await expect(panel).toHaveAttribute("data-entity-kind", "mp");

    // The amber banner ("Self-declared at nomination, not adjudicated")
    // is gated on the `amber_banner` prop being non-null; the
    // Constituency mount always passes it for this surface.
    await expect(
      page.getByTestId("entity-profile-panel-amber"),
    ).toBeVisible();

    // The provenance footer is also gated on the prop being non-null;
    // the Constituency mount always passes it.
    await expect(
      page.getByTestId("entity-profile-panel-provenance"),
    ).toBeVisible();

    // The rows container is always present when the panel mounts;
    // verify at least one <dt>/<dd> pair under it.
    const rows = page.getByTestId("entity-profile-panel-rows");
    await expect(rows).toBeVisible();
    await expect(rows.locator("dt").first()).toBeVisible();
    await expect(rows.locator("dd").first()).toBeVisible();
  });

  test("does NOT mount panel for a 2024 LS event (no affidavit data yet)", async ({
    page,
  }) => {
    // The same PC, but for general-2024 which has no affidavit data
    // ingested today. The panel mount is guarded on the event_id
    // being in EVENTS_WITH_AFFIDAVITS.
    await page.goto("/maharashtra/elections/general-2024/buldhana");
    await expect(
      page.getByTestId("constituency-pc-winner"),
    ).toBeVisible({ timeout: 30_000 });
    // Give the loader a moment to confirm no panel mounts.
    await page.waitForTimeout(2_000);
    await expect(
      page.getByTestId("entity-profile-panel"),
    ).toHaveCount(0);
  });
});
