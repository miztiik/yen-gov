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

// R5 of TODO/20260625-election-constituency-list-redesign-plan.md
// (2026-06-25). Smoke for the redesigned NATIONAL constituency list. The
// per-state rail and the embedded PC-mode StateEventConstituencyList ride
// ONE shared 6-track grid-cols-subgrid ruler (GRID_COLS), so the citizen
// reads aligned columns down the State -> Parliament-seat -> Assembly-seat
// hierarchy. This pins the contract DOM-measured live during R5:
//   - the rail <ul> carries the explicit GRID_COLS ruler; rows are
//     grid-cols-subgrid children of it;
//   - PC-header groups render on the subgrid (parliament result chip);
//   - Assembly-seat leaves are whole-row <a> jump links (arrow-up-right
//     glyph) with a map-pin district cell;
//   - the "Parliament seat pending" bucket (ACs not yet backfilled to a
//     parent PC - the deferred P0b data row) renders AND is sorted LAST so
//     it never wedges mid-list.
//
// DOM-click bypass (page.evaluate(... .click())): the live India choropleth
// keeps re-laying-out paths, so Playwright's actionability check on the
// state-toggle never settles. Clicking in page context sidesteps it - the
// proven idiom from the election-map specs.
test.describe("national constituency list - subgrid + pending bucket (R5)", () => {
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

  test("Telangana: PC subgrid groups, AC-leaf jump links, pending bucket last", async ({
    page,
  }) => {
    await page.goto("/t/elections/general-2024", {
      waitUntil: "load",
      timeout: 30_000,
    });

    // Data-arrival oracle: the per-state rail mounts once the winners +
    // AC-entity loaders resolve (cold DuckDB-WASM worker -> 45s budget).
    const stateRow = page
      .getByTestId("national-event-constituency-state-row")
      .first();
    await expect(stateRow).toBeVisible({ timeout: 45_000 });

    // The rail <ul> carries the explicit GRID_COLS ruler; each state row is a
    // grid-cols-subgrid child of it. MarginLegend (the only other block in
    // the section) renders no <ul>, so .first() is the rail.
    const railUl = page
      .getByTestId("national-event-constituency-list")
      .locator("ul")
      .first();
    await expect(railUl).toHaveClass(/grid-cols-\[/);
    await expect(stateRow).toHaveClass(/grid-cols-subgrid/);

    // Expand Telangana (DOM-click bypass for the animating India map).
    await page.evaluate(() => {
      const b = Array.from(
        document.querySelectorAll(
          '[data-testid="national-event-constituency-state-toggle"]',
        ),
      ).find((x) =>
        /Telangana/i.test(x.querySelector(".col-start-2")?.textContent ?? ""),
      );
      (b as HTMLButtonElement | undefined)?.click();
    });

    // Scope to Telangana's row (a state may auto-expand; never assume the
    // first open panel is ours).
    const telanganaRow = page
      .getByTestId("national-event-constituency-state-row")
      .filter({ hasText: "Telangana" });
    const panel = telanganaRow.getByTestId(
      "national-event-constituency-state-panel",
    );
    await expect(panel).toBeVisible({ timeout: 15_000 });

    // The embedded PC-mode list: PC headers carry the parliament result chip
    // and ride grid-cols-subgrid too.
    await expect(
      panel.getByTestId("state-event-constituency-pc-header").first(),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      panel.getByTestId("state-event-constituency-district-row").first(),
    ).toHaveClass(/grid-cols-subgrid/);

    // Expand the "Bhongir" PC -> its Assembly-seat leaves render.
    await page.evaluate(() => {
      const rows = Array.from(
        document.querySelectorAll(
          '[data-testid="national-event-constituency-state-row"]',
        ),
      );
      const row = rows.find((r) =>
        /Telangana/i.test(
          r.querySelector(
            '[data-testid="national-event-constituency-state-toggle"] .col-start-2',
          )?.textContent ?? "",
        ),
      );
      const p = row?.querySelector(
        '[data-testid="national-event-constituency-state-panel"]',
      );
      const t = Array.from(
        p?.querySelectorAll(
          '[data-testid="state-event-constituency-district-toggle"]',
        ) ?? [],
      ).find((x) =>
        /Bhongir/i.test(x.querySelector(".col-start-2")?.textContent ?? ""),
      );
      (t as HTMLButtonElement | undefined)?.click();
    });

    const leaf = panel.getByTestId("state-event-constituency-row").first();
    await expect(leaf).toBeVisible({ timeout: 15_000 });
    // The leaf is a whole-row anchor (not a button/div) -> navigation.
    await expect(leaf).toHaveJSProperty("tagName", "A");
    await expect(leaf).toHaveAttribute("href", /\/telangana\/ac\//);
    // Trailing jump glyph + map-pin district cell.
    await expect(
      leaf.locator('svg[data-icon-name="arrow-up-right"]'),
    ).toHaveCount(1);
    await expect(
      leaf.getByTestId("state-event-constituency-leaf-district"),
    ).toBeVisible();

    // The "Parliament seat pending" bucket renders AND is the LAST group
    // (sorted last so the not-yet-backfilled ACs never wedge mid-list).
    const headers = await page.evaluate(() => {
      const rows = Array.from(
        document.querySelectorAll(
          '[data-testid="national-event-constituency-state-row"]',
        ),
      );
      const row = rows.find((r) =>
        /Telangana/i.test(
          r.querySelector(
            '[data-testid="national-event-constituency-state-toggle"] .col-start-2',
          )?.textContent ?? "",
        ),
      );
      const p = row?.querySelector(
        '[data-testid="national-event-constituency-state-panel"]',
      );
      return Array.from(
        p?.querySelectorAll(
          '[data-testid="state-event-constituency-district-toggle"] .col-start-2',
        ) ?? [],
      ).map((s) => (s.textContent ?? "").trim());
    });
    expect(headers.some((h) => /Parliament seat pending/i.test(h))).toBe(true);
    expect(headers[headers.length - 1]).toMatch(/Parliament seat pending/i);
  });
});
