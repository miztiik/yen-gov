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
    // alone is not a data-arrival signal. Use the FIRST top-parties row
    // as the load-complete oracle (it only appears after
    // `loadElectionResults({event})` resolves and `winners` populates).
    // 30s allows for the cold vite compile + DuckDB-WASM worker
    // bootstrap + the 542-row scan.
    await expect(
      page.getByTestId("national-event-top-parties-row").first(),
    ).toBeVisible({ timeout: 30_000 });

    // KPIs strip visible (now carrying data since the load completed).
    await expect(page.getByTestId("national-event-kpis")).toBeVisible();

    // India choropleth visible.
    await expect(page.getByTestId("national-event-map")).toBeVisible();

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
      page.getByTestId("national-event-top-parties-row").first(),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("national-event-kpis")).toBeVisible();
    await expect(page.getByTestId("national-event-map")).toBeVisible();
    await expect(page.getByTestId("national-event-top-parties")).toBeVisible();
  });
});
