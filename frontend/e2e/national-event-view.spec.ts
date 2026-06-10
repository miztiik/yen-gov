// E2E smoke for the rebuilt National event view (PR-W3c, 2026-06-10).
//
// Covers the three citizen-visible primitives the rebuild ships:
//   1. KPIs strip       (data-testid="national-event-kpis")
//   2. India choropleth (data-testid="national-event-map")
//   3. Top-parties bar  (data-testid="national-event-top-parties")
//
// Plus two hygiene oracles per the brief:
//   - zero console errors over the whole nav
//   - zero failed network requests over the whole nav
//
// And one legacy-alias assertion — visiting the pre-PR-W2a ECI form
// (`LsGenJun2024`) resolves to the SAME canonical view (the W2b loader's
// `eventYear()` slug-extraction makes both forms hit
// `datasets/elections/parliament/election=2024/summary.csv`). PR-W2a's
// `event_id_aliases[]` strangler is the contract surface; this spec pins
// the citizen-facing behaviour ("old bookmark still works").

import { test, expect } from "@playwright/test";

test.describe("national event view (PR-W3c rebuild)", () => {
  test("renders KPIs + India map + top-parties for /t/elections/general-2024", async ({
    page,
  }) => {
    const errors: string[] = [];
    const failedRequests: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    page.on("requestfailed", (req) =>
      failedRequests.push(
        `${req.method()} ${req.url()} -- ${req.failure()?.errorText ?? "?"}`,
      ),
    );

    await page.goto("/t/elections/general-2024");

    // KPIs strip appears once `loadElectionResults({event})` resolves
    // and `loadStates()` populates the choropleth seed. Allow 30s -
    // the maplibre worker + DuckDB-WASM cold-start dominates the wait.
    await expect(page.getByTestId("national-event-kpis")).toBeVisible({
      timeout: 30_000,
    });

    // India choropleth container renders (boundary GeoJSON fetch is a
    // separate concern; visibility of the maplibre canvas wrapper is
    // the citizen-facing oracle).
    await expect(page.getByTestId("national-event-map")).toBeVisible();

    // Top-parties bar visible AND has at least one row. PR-W3c oracle:
    // 2024 LS had BJP first with 240 seats - we don't pin the party
    // name here (the contract test does that), but we DO pin at least
    // one row renders so the bar isn't empty.
    await expect(page.getByTestId("national-event-top-parties")).toBeVisible();
    await expect(
      page.getByTestId("national-event-top-parties-row").first(),
    ).toBeVisible();

    // Hygiene assertions (CLAUDE.md section 13: smoke must catch
    // regressions in non-renderer consumers too).
    expect(
      errors,
      `Console errors during nav:\n${errors.join("\n")}`,
    ).toEqual([]);
    expect(
      failedRequests,
      `Failed network requests during nav:\n${failedRequests.join("\n")}`,
    ).toEqual([]);
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
    await expect(page.getByTestId("national-event-kpis")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("national-event-map")).toBeVisible();
    await expect(page.getByTestId("national-event-top-parties")).toBeVisible();
  });
});
