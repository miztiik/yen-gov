// E2E smoke for the rebuilt National event view (PR-W3c, 2026-06-10).
//
// Covers the three citizen-visible primitives the rebuild ships:
//   1. KPIs strip       (data-testid="national-event-kpis")
//   2. India choropleth (data-testid="national-event-map")
//   3. Top-parties bar  (data-testid="national-event-top-parties")
//
// Plus the project-wide page-error trap (`attachPageErrorTrap`) which
// surfaces uncaught exceptions + console.error + `/data/` requestfailed
// events while filtering the graceful-degradation 404-as-null pattern
// (ADR-0014) and maplibre's teardown AbortError. Replicating its
// behaviour inline would re-introduce the project's pre-helper churn.
//
// And one legacy-alias assertion - visiting the pre-PR-W2a ECI form
// (`LsGenJun2024`) resolves to the SAME canonical view (the W2b loader's
// `eventYear()` slug-extraction makes both forms hit
// `datasets/elections/parliament/election=2024/summary.csv`). PR-W2a's
// `event_id_aliases[]` strangler is the contract surface; this spec pins
// the citizen-facing behaviour ("old bookmark still works").

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

test.describe("national event view (PR-W3c rebuild)", () => {
  // First-hit cold compile (vite-plugin-svelte + maplibre-gl + DuckDB-WASM
  // worker) takes ~30s on a warm machine and >60s on Windows; the default
  // 30s per-test timeout fires on `page.goto` alone. Bump to 90s for the
  // describe.
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

  test("renders KPIs + India map + top-parties for /t/elections/general-2024", async ({
    page,
  }) => {
    await page.goto("/t/elections/general-2024");

    // The KPIs strip + map + top-parties containers all mount as soon as
    // the loader transitions out of `failed`. They render skeleton-ish
    // content during `loading` though, so visibility of the CONTAINER
    // alone is not a data-arrival signal. TODO/20260612 Row F: top-
    // parties now uses PartyBar, which emits `party-bar-row` per
    // ranked party (replacing the retired `national-event-top-parties-
    // row` testid).
    // 30s allows for the cold vite compile + DuckDB-WASM worker
    // bootstrap + the 542-row scan.
    await expect(
      page.getByTestId("party-bar-row").first(),
    ).toBeVisible({ timeout: 30_000 });

    // KPIs strip visible (now carrying data since the load completed).
    await expect(page.getByTestId("national-event-kpis")).toBeVisible();

    // India choropleth visible (TODO/20260612 Row C: this container
    // now hosts a 3-way map view; the States arm is the default and
    // renders the IndiaPartyMap inside `national-event-map-states`).
    await expect(page.getByTestId("national-event-map")).toBeVisible();
    await expect(page.getByTestId("national-event-map-states")).toBeVisible({
      timeout: 30_000,
    });

    // Top-parties bar visible (container; row check above pinned the data).
    await expect(page.getByTestId("national-event-top-parties")).toBeVisible();

    // TODO/20260612 Row C + E: the "Event slug general-2024" developer
    // metadata is gone from the header. Assert its absence so a future
    // refactor cannot silently re-leak it.
    await expect(page.locator("header").first()).not.toContainText(
      "Event slug",
    );
  });

  test("legacy event-id alias (LsGenJun2024) resolves to the same view", async ({
    page,
  }) => {
    // PR-W2a alias strangler: visiting the pre-rename ECI form
    // `LsGenJun2024` should render the SAME national view as
    // `general-2024`. Today the route does not redirect (no path
    // rewrite); both forms hit the same CSV via the loader's
    // `eventYear()` slug-extraction. The W3c view-model surfaces
    // them identically because it does not filter on `period_label`.
    await page.goto("/t/elections/LsGenJun2024");
    // Same data-arrival oracle as the happy-path test.
    await expect(
      page.getByTestId("party-bar-row").first(),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("national-event-kpis")).toBeVisible();
    await expect(page.getByTestId("national-event-map")).toBeVisible();
    await expect(page.getByTestId("national-event-top-parties")).toBeVisible();
  });

  test("3-way map toggle: Constituencies arm mounts IndiaPcMapD3 (Row C)", async ({
    page,
  }) => {
    // TODO/20260612 Row C: clicking "Constituencies" on the 3-way
    // toggle swaps the States arm for the IndiaPcMapD3 543-PC
    // choropleth. The hex arm is gated by the tile-scopes manifest
    // (national PC layout present -> button is offered).
    await page.goto("/t/elections/general-2024");

    // Wait for the load oracle (PartyBar populated).
    await expect(page.getByTestId("party-bar-row").first()).toBeVisible({
      timeout: 30_000,
    });

    // Default arm: States.
    await expect(page.getByTestId("national-event-map-states")).toBeVisible();

    // Click the Constituencies button on the 3-way toggle.
    await page
      .getByTestId("national-event-map-view")
      .getByRole("button", { name: "Constituencies" })
      .click();

    // IndiaPcMapD3 container mounts.
    await expect(page.getByTestId("national-event-map-pc")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("india-pc-map-d3")).toBeVisible({
      timeout: 30_000,
    });

    // Winner|Margin sub-toggle is now visible (only on the non-States
    // arms per the verdict text).
    await expect(page.getByTestId("national-event-map-mode")).toBeVisible();
  });

  test("party-mute via PartyBar reveals reset button (Row F)", async ({
    page,
  }) => {
    // TODO/20260612 Row F: click a PartyBar row to mute; the reset
    // button surfaces above the bar with the muted count. Same
    // affordance as StateOverview + Psephlab.
    await page.goto("/t/elections/general-2024");

    await expect(page.getByTestId("party-bar-row").first()).toBeVisible({
      timeout: 30_000,
    });

    // Reset absent on first paint.
    await expect(
      page.getByTestId("national-event-top-parties-reset"),
    ).toHaveCount(0);

    // Click the first PartyBar row.
    await page.getByTestId("party-bar-row").first().click();

    // Reset surfaces with the muted count.
    await expect(
      page.getByTestId("national-event-top-parties-reset"),
    ).toBeVisible();
    await expect(
      page.getByTestId("national-event-top-parties-reset"),
    ).toContainText(/Show all \(1 muted\)/);

    // Click reset; the button disappears again.
    await page.getByTestId("national-event-top-parties-reset").click();
    await expect(
      page.getByTestId("national-event-top-parties-reset"),
    ).toHaveCount(0);
  });

  test("party-mute recedes the states map + the scatter, not only the per-PC arms", async ({
    page,
  }) => {
    // Regression: muting a party via the PartyBar must recede that party's
    // marks on the "Winning party by state" choropleth (IndiaPartyMap) AND
    // the "Turnout vs winning margin" scatter. Both surfaces previously
    // ignored the mute (IndiaPartyMap "owns its own fills"; the scatter
    // projected every winner). The recede idiom is slate-300 (#cbd5e1) at a
    // low fill-opacity - 0.3 on the big state polygons, 0.15 on the dots.
    await page.goto("/t/elections/general-2024");

    await expect(page.getByTestId("party-bar-row").first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("national-event-map-states")).toBeVisible({
      timeout: 30_000,
    });

    const recededState = page
      .getByTestId("national-event-map-states")
      .locator('path[fill="#cbd5e1"][fill-opacity="0.3"]');
    const recededDot = page
      .getByTestId("scatter-chart")
      .locator('circle[fill="#cbd5e1"][fill-opacity="0.15"]');

    // Nothing receded before the mute.
    await expect(recededState).toHaveCount(0);
    await expect(recededDot).toHaveCount(0);

    // Mute the top party (first PartyBar row).
    await page.getByTestId("party-bar-row").first().click();
    await expect(
      page.getByTestId("national-event-top-parties-reset"),
    ).toBeVisible();

    // Both surfaces now carry receded marks for the muted party.
    await expect
      .poll(async () => recededState.count(), { timeout: 30_000 })
      .toBeGreaterThan(0);
    await expect
      .poll(async () => recededDot.count(), { timeout: 30_000 })
      .toBeGreaterThan(0);

    // Un-muting clears the recede on both surfaces.
    await page.getByTestId("national-event-top-parties-reset").click();
    await expect
      .poll(async () => recededState.count(), { timeout: 10_000 })
      .toBe(0);
    await expect
      .poll(async () => recededDot.count(), { timeout: 10_000 })
      .toBe(0);
  });
});
