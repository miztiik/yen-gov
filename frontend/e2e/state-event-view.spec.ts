// E2E smoke for the rebuilt state event view (PR-W3b, 2026-06-10).
//
// Surface: `/<state>/elections/<event-slug>`. Covers the citizen-visible
// primitives the rebuild ships:
//   1. KPIs strip          (data-testid="state-event-kpis")
//   2. Top-parties bar     (data-testid="state-event-top-parties")
//   3. AllianceTotals      (data-testid="alliance-totals")
//   4. InlineSwing panel   (data-testid="inline-counterfactual-swing")
//   5. Constituency table  (data-testid="state-event-constituency-table")
//
// Two assertions on the new bare-slug constituency leaf route added in
// PR-W3b:
//   - The constituency-table row links use the bare-name slug
//     (`/<state>/elections/<event>/<constituency>`), NOT the legacy
//     5-segment `/ac/<n-slug>` shape.
//   - Visiting `/chhattisgarh/elections/general-2024/bastar` loads the
//     Constituency page with PC kind inferred (no `/ac/` literal) and
//     shows the seat name.
//
// One swing-slider behaviour test: dragging the inline slider updates
// the seat-card delta (component state only, NO URL change).

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

test.describe("state event view (PR-W3b rebuild)", () => {
  // First-hit cold compile (vite-plugin-svelte + DuckDB-WASM worker)
  // dominates on Windows. Bump to 90s like the W3a / W3c siblings.
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

  test("renders KPIs + top-parties + alliance + table for /chhattisgarh/elections/general-2024", async ({
    page,
  }) => {
    // general-2024 = parliament event. The W2b loader uses NATIONAL-PC
    // dispatch and the StateElection page filters by state_slug locally.
    // 11 PCs in Chhattisgarh; the constituency table should mount with
    // at least 8 rows once the per-PC rows arrive.
    await page.goto("/chhattisgarh/elections/general-2024");

    // The page header is the first thing that paints after the
    // catalogue + states stores resolve. Use it as the route-mounted
    // anchor before asserting data-driven primitives.
    await expect(page.getByTestId("state-event-header")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("state-event-body-chip")).toHaveText(
      /Parliament/,
    );

    // TODO/20260612 Row C: the "Event slug general-2024" developer
    // metadata is gone from the header. Assert its absence so a future
    // refactor cannot silently re-leak it.
    await expect(
      page.locator("header").filter({ has: page.getByTestId("state-event-header") }),
    ).not.toContainText("Event slug");

    // KPIs strip mounts even on empty data (4 cards always render).
    await expect(page.getByTestId("state-event-kpis")).toBeVisible({
      timeout: 30_000,
    });

    // TODO/20260612 Row D: top-parties bar now reuses PartyBar; oracle
    // shifts from the retired `state-event-top-parties-row` to the new
    // additive `party-bar-row` testid the PartyBar primitive emits per
    // ranked party.
    await expect(
      page.getByTestId("party-bar-row").first(),
    ).toBeVisible({ timeout: 30_000 });

    // Constituency table also mounts once data arrives.
    await expect(
      page.getByTestId("state-event-constituency-row").first(),
    ).toBeVisible({ timeout: 30_000 });

    // Alliance panel mounts (either with totals or with the
    // "alliance data pending" placeholder for events without curated
    // alliance rows; general-2024 has no rows for Chhattisgarh today
    // so the placeholder path is the expected one).
    await expect(page.getByTestId("alliance-totals")).toBeVisible({
      timeout: 30_000,
    });

    // TODO/20260612 Row C: Parliament events show a PC map placeholder
    // card (the country PC topojson exists but per-state PC integration
    // is follow-up work). The card pins the citizen-facing copy so the
    // page doesn't silently degrade.
    await expect(
      page.getByTestId("state-event-pc-map-placeholder"),
    ).toBeVisible({ timeout: 30_000 });

    // Inline swing panel mounts; for parliament events it renders the
    // disabled placeholder (the psephlab canonical loader is assembly-
    // only). The container is always present; the disabled note marks
    // the parliament code path.
    await expect(
      page.getByTestId("inline-counterfactual-swing"),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("inline-swing-disabled")).toBeVisible();
  });

  test("constituency-table links use bare-name slug shape (no /ac/ literal)", async ({
    page,
  }) => {
    await page.goto("/chhattisgarh/elections/general-2024");
    await expect(
      page.getByTestId("state-event-constituency-link").first(),
    ).toBeVisible({ timeout: 30_000 });

    // Sample the first link's href; assert it matches the W3b bare-slug
    // shape `/chhattisgarh/elections/general-2024/<slug>` and that the
    // `<slug>` segment is a plain name-slug (no `/ac/` literal, no
    // numeric prefix, no body-prefix collision with the event-slug
    // regex).
    const first = page.getByTestId("state-event-constituency-link").first();
    const href = await first.getAttribute("href");
    expect(href).toMatch(
      /^\/chhattisgarh\/elections\/general-2024\/[a-z0-9-]+$/,
    );
    // STOP-AND-SURFACE if the legacy 5-segment AC shape leaks back.
    expect(href).not.toContain("/ac/");
  });

  test("inline swing slider updates seat-card delta on assembly events", async ({
    page,
  }) => {
    // Karnataka assembly-2023 has the on-disk per-AC tallies the
    // psephlab loader needs (election=2023 directory present in
    // datasets/elections/assembly/state=karnataka/).
    await page.goto("/karnataka/elections/assembly-2023");

    await expect(
      page.getByTestId("inline-counterfactual-swing"),
    ).toBeVisible({ timeout: 30_000 });

    // TODO/20260612 Row C: assembly events render the StateAcMap with
    // a sub-threshold marker legend below it. The legend is the only
    // place the page explains the circular markers overlay on small ACs.
    await expect(
      page.getByTestId("state-ac-map-legend"),
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByTestId("state-ac-map-legend"),
    ).toContainText(/dense urban constituencies/i);

    // Slider mounts only after the canonical loader resolves; once it
    // does, the seats card is visible too.
    await expect(page.getByTestId("inline-swing-slider")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByTestId("inline-swing-seats-card"),
    ).toBeVisible();

    // Snapshot the baseline url (NO ?s= query, NO # fragment) and the
    // first seat-row delta cell.
    const url_before = page.url();
    expect(url_before).not.toMatch(/[?#]/);

    // Drive the slider to a 15% swing via a deterministic .fill().
    // bind:value on the range input updates on input, so the seats
    // card re-derives immediately.
    const slider = page.getByTestId("inline-swing-slider");
    await slider.evaluate((el: HTMLInputElement) => {
      el.value = "15";
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    });

    // URL stays unchanged after the swing (W3b: ephemeral state only).
    const url_after = page.url();
    expect(url_after).toBe(url_before);

    // The seats card now shows the delta column with at least one
    // non-zero entry. (At 15% swing the bottom-of-pack source loses
    // votes and the runner-up gains some — at least one party row
    // shifts.)
    const delta_texts = await page
      .getByTestId("inline-swing-seats-delta")
      .allTextContents();
    expect(delta_texts.length).toBeGreaterThan(0);
    const has_nonzero = delta_texts.some(
      (t) => t.trim() !== "+0" && t.trim() !== "",
    );
    expect(
      has_nonzero,
      `expected at least one non-zero delta after 15% swing; got ${JSON.stringify(delta_texts)}`,
    ).toBe(true);
  });

  test("drill into Bastar via bare slug: /chhattisgarh/elections/general-2024/bastar", async ({
    page,
  }) => {
    // W3b oracle URL: PC kind inferred from `general-` prefix; the
    // bare slug `bastar` resolves to the chhattisgarh PC named
    // "Bastar" (eci_no=9) via `findConstituencyBySlug`. The legacy
    // 5-segment `/ac/<n-slug>` URL is NOT involved.
    await page.goto("/chhattisgarh/elections/general-2024/bastar");

    // Constituency header is the load-complete oracle for the new leaf.
    await expect(page.getByTestId("constituency-header")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("constituency-header")).toContainText(
      "Bastar",
      { ignoreCase: true },
    );
  });
});
