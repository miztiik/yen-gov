// Golden-path: the four routes a citizen actually traverses on first
// visit. If any of these break, the site is broken.
//
//   1. Home              — India map + state list renders, TN link present
//   2. State overview    — TN page renders party totals + AC list
//   3. Constituency      — drill into one AC, top-N candidates table renders
//   4. Party             — drill into a party from the AC, seats summary
//
// Selectors prefer semantic queries (role, text) over CSS classes so the
// tests survive a Tailwind refactor. The map components are NOT asserted
// pixel-by-pixel — we just check the surrounding header copy is there,
// because canvas content is not addressable through the DOM and the rest
// of the page failing-fast is the real signal.
//
// Every test attaches `attachPageErrorTrap` via beforeEach (CLAUDE.md §15:
// "no `pageerror`" is non-negotiable for any citizen-visible route).
// SourceList provenance is asserted on data-bearing routes.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap, SOURCE_LIST_TEXT } from "./_helpers";

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("golden path", () => {
  test("home renders India map and Tamil Nadu link", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "yen-gov", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: /India.*leading party/i })).toBeVisible();
    // Tamil Nadu must appear in the "Available" bucket (data shipped).
    const tn = page.getByRole("link", { name: /Tamil Nadu/i }).first();
    await expect(tn).toBeVisible({ timeout: 15_000 });
  });

  test("state overview renders party totals and AC list for Tamil Nadu", async ({ page }) => {
    await page.goto("/s/tamil-nadu");
    // result.summary.json fetch + render
    await expect(page.getByText(/Assembly election/i)).toBeVisible({ timeout: 15_000 });
    // At least one AC link rendered (constituencies.json loaded). Filter
    // by href shape — name-based queries are brittle here because the
    // visible text concatenates eci_no + AC name + reservation tag.
    await expect(page.locator('a[href*="/ac/"]').first()).toBeVisible({ timeout: 15_000 });
    // Provenance: SourceList renders "Sources (N)" once result.summary loads.
    await expect(page.getByText(SOURCE_LIST_TEXT).first()).toBeVisible({ timeout: 15_000 });

    // Regression: every indicator card H3 must contain its title exactly
    // once. Bug 2026-05-15: IndicatorChoropleth passed the indicator title
    // to IndicatorIcon as `title={...}`, which renders <svg><title>...
    // </title></svg>. Element.textContent walks into the SVG <title>, so
    // the H3's effective text became "<title> <title> <badge>", e.g.
    // "Outstanding liabilities (% of GSDP) Outstanding liabilities (% of
    // GSDP) Central". Fix at the call site (drop the redundant prop).
    // Detection: a heading whose first half equals its second half (after
    // stripping the legitimate implementing_authority badge suffix).
    const dups = await page.locator("main h3").evaluateAll((nodes) =>
      nodes
        .map((n) => (n.textContent ?? "").replace(/\s+/g, " ").trim())
        .filter((t) => {
          // Strip trailing legitimate badge tokens (implementing_authority).
          const core = t
            .replace(/\s+(Central|Centre \+ state|Local body|Parastatal)$/, "")
            .trim();
          if (core.length < 8) return false; // ignore short headings
          const half = Math.floor(core.length / 2);
          // Treat as duplicated when the first half exactly equals the
          // second half (allowing for an odd-length middle char).
          return core.slice(0, half) === core.slice(-half);
        }),
    );
    expect(dups, `Duplicated H3 titles found:\n${dups.join("\n")}`).toEqual([]);

    // IA-rework Step #1 (TODO/20260515-state-page-ia-rework-plan.md §2,
    // §9 row 1): the per-artifact India choropleth + ranked table +
    // small-multiples trio has been replaced with one IndicatorCard
    // per artifact. The state AC map (top-of-page StateAcMap) is the
    // ONLY maplibre canvas allowed on this surface; every per-indicator
    // India choropleth must be gone. Assert at most one maplibre canvas
    // is mounted (StateAcMap for S22) AND that at least one indicator
    // card rendered.
    await expect(page.locator("canvas.maplibregl-canvas"))
      .toHaveCount(1, { timeout: 15_000 });
    await expect(page.locator('[data-testid="indicator-card"]').first())
      .toBeVisible({ timeout: 15_000 });
  });

  test("constituency page renders top-N candidates", async ({ page }) => {
    // S22 AC #1 = Gummidipoondi (the slice that the live backend test
    // covers; the published artifact is guaranteed to exist).
    await page.goto("/s/tamil-nadu/ac/1-gummidipoondi");
    await expect(page.getByRole("heading", { level: 2, name: /Top \d+ candidates/i }))
      .toBeVisible({ timeout: 15_000 });
    // Header row of the candidates table
    await expect(page.getByRole("columnheader", { name: "Candidate" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Party" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Votes" })).toBeVisible();
  });

  test("explore page lazy-loads sqlite without error", async ({ page }) => {
    // The /explore route mounts sql.js (sqlite-wasm). If the chunk fails
    // to load, the route shows an error banner rather than crashing. The
    // beforeEach pageerror trap covers the failure mode; here we just
    // wait for network idle to confirm the wasm chunk + db both fetched.
    await page.goto("/s/tamil-nadu/explore");
    await page.waitForLoadState("networkidle", { timeout: 30_000 });
  });

  test("per-state topic page (/s/:state/t/:topic) renders cards + breadcrumb", async ({ page }) => {
    // IA-reset Step #2: pick a state → click a topic in the rail → land
    // here. Asserts the route shell (breadcrumb + heading), at least one
    // IndicatorCard rendered, and SourceList provenance per CLAUDE.md §15.
    await page.goto("/s/tamil-nadu/t/fiscal");

    // Breadcrumb: "Tamil Nadu" is clickable, "Money & debt"-equivalent
    // (catalogue title for `fiscal`) is current. We assert the structural
    // landmark + the state link by href shape rather than its label, since
    // states.json drives the display name.
    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(breadcrumb).toBeVisible({ timeout: 15_000 });
    await expect(breadcrumb.locator('a[href$="/s/tamil-nadu"]')).toBeVisible();

    // At least one IndicatorCard renders with TN data.
    await expect(page.locator('[data-testid="indicator-card"]').first())
      .toBeVisible({ timeout: 15_000 });

    // Provenance per CLAUDE.md §15 four-tier policy — SourceList renders
    // inside the IndicatorCard once its underlying indicator artifact
    // loads.
    await expect(page.getByText(SOURCE_LIST_TEXT).first())
      .toBeVisible({ timeout: 15_000 });

    // "See all states →" link on a card points back to the national
    // topic page /t/fiscal.
    await expect(page.locator('a[href$="/t/fiscal"]').first()).toBeVisible();
  });

  test("per-state topic page 404s cleanly on unknown topic", async ({ page }) => {
    await page.goto("/s/tamil-nadu/t/nonsense-topic-slug");
    await expect(page.getByRole("heading", { name: /Topic not found/i }))
      .toBeVisible({ timeout: 15_000 });
  });

  test("per-state topic page 404s cleanly on unknown state slug", async ({ page }) => {
    await page.goto("/s/nonsense-state-slug/t/fiscal");
    await expect(page.getByRole("heading", { name: /State not found/i }))
      .toBeVisible({ timeout: 15_000 });
  });
});
