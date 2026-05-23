// Playwright — CompositionBar A/B mount on the state-hub elections card.
//
// Phase 3.6 (c) of TODO/20260518-frontend-charting-modernisation-plan.md.
// Verifies the three contract surfaces of the experiment:
//
//   1. Treatment bucket on Karnataka (S10, in the rollout list) renders
//      BOTH `<SeatDonut />` AND `<CompositionBar />` in the
//      house-composition card. The composition bar is the new
//      single-entity primitive shipped in PR-30 #142.
//
//   2. Control bucket on Karnataka renders only `<SeatDonut />` — the
//      existing production behaviour. CompositionBar must NOT mount.
//
//   3. Tamil Nadu (S22) is OUT OF TARGETING regardless of bucket per
//      plan resolution R-02 (alliance-led verdict; party-only chart
//      misframes it). The treatment override must still NOT mount
//      CompositionBar on TN.
//
// Karnataka chosen as the smoke state because (a) it is in the
// rollout list per `experiment-definition.json`
// `single-party-dominant-states.condition.state_code.$in`; (b) the
// most recent assembly election (AcGenMay2023) has `data_status:
// complete` in `datasets/taxonomy/election_events.json`; (c) INC won
// a clear majority so the bar projection has a dominant segment to
// render.
//
// Bucket determinism: the bucket is keyed off a sticky cookie
// (`yg_visitor_id`) hashed with the experiment id. Playwright pins
// the variant via the `?yg_variant=<id>` URL override (see
// `frontend/src/lib/experiments/bucket.ts → bucketForWithOverride`)
// so the test does not depend on a specific random seed.
//
// `attachPageErrorTrap` enforces CLAUDE.md §15 — the new mount must
// not throw any runtime error on the citizen-visible page.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

let trap: { getErrors: () => string[] };

test.beforeEach(({ page }) => {
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap.getErrors();
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("CompositionBar A/B mount (Phase 3.6 c)", () => {
  test("treatment bucket on Karnataka renders SeatDonut + CompositionBar", async ({ page }) => {
    await page.goto("/s/karnataka?yg_variant=treatment");
    await page.waitForLoadState("networkidle", { timeout: 20_000 });

    // SeatDonut — the existing production chart. Selected by its
    // aria-label (stable; survives Tailwind refactors).
    await expect(
      page.getByLabel("House composition donut chart"),
    ).toBeVisible({ timeout: 15_000 });

    // CompositionBar — the new primitive. The wrapper carries
    // `data-component="composition-bar"` (set in
    // frontend/src/lib/CompositionBar.svelte).
    const bar = page.locator('[data-component="composition-bar"]');
    await expect(bar).toBeVisible({ timeout: 15_000 });

    // The bar must render at least one segment with the contract
    // attributes (data-segment-id, data-share-pct). Catches a
    // model-loaded-but-empty render.
    const segments = bar.locator("[data-segment-id]");
    expect(await segments.count()).toBeGreaterThan(0);

    // Phase 1.4 task 4 footer actions — `copy_link` + `view_data` are
    // attached by StateOverview when CompositionBar mounts. The action
    // footer is rendered by `<ChartShell>` (sibling of the
    // composition-bar div within the shared shell wrapper), not inside
    // the bar itself. Scope the locator to the shell that hosts the
    // CompositionBar via `:has` so we pick the right instance and not a
    // sibling chart's footer.
    const shell = page.locator(
      '[data-component="chart-shell"]:has([data-component="composition-bar"])',
    );
    const actionsRoot = shell.locator('[data-slot="actions"]');
    await expect(actionsRoot).toBeVisible({ timeout: 15_000 });
    await expect(actionsRoot.locator('[data-action="copy_link"]')).toBeVisible();
    await expect(actionsRoot.locator('[data-action="view_data"]')).toBeVisible();
    // Unapproved ids must NEVER appear — closed-enum gate is enforced
    // in `chart-shell/actions.ts` `filterAllowedActions`, but this
    // covers the case where a future caller adds an ad-hoc spec.
    const actionIds = await actionsRoot
      .locator("[data-action]")
      .evaluateAll(nodes => nodes.map(n => n.getAttribute("data-action")));
    for (const id of actionIds) {
      expect([
        "view_data",
        "download",
        "copy_link",
        "share",
        "reset_view",
        "full_range",
      ]).toContain(id);
    }
  });

  test("control bucket on Karnataka renders SeatDonut only — no CompositionBar", async ({ page }) => {
    await page.goto("/s/karnataka?yg_variant=control");
    await page.waitForLoadState("networkidle", { timeout: 20_000 });

    // SeatDonut still renders.
    await expect(
      page.getByLabel("House composition donut chart"),
    ).toBeVisible({ timeout: 15_000 });

    // CompositionBar MUST NOT be in the DOM. Use locator.count() not
    // toBeHidden — we want to assert absence, not "present but display:none".
    const bar = page.locator('[data-component="composition-bar"]');
    expect(await bar.count()).toBe(0);
  });

  test("Tamil Nadu (out of targeting) does NOT mount CompositionBar even with treatment override", async ({ page }) => {
    // Per plan R-02: TN is excluded from the rollout because the
    // verdict is alliance-led and a party-only bar misframes it. Even
    // forcing the treatment variant must NOT mount the chart on TN —
    // `bucketForWithOverride` checks targeting BEFORE the override so
    // the citizen-visible contract cannot be bypassed by a malformed
    // URL.
    await page.goto("/s/tamil-nadu?yg_variant=treatment");
    await page.waitForLoadState("networkidle", { timeout: 20_000 });

    // TN MUST still render SeatDonut — the rest of the elections card
    // is unchanged for control-state citizens.
    await expect(
      page.getByLabel("House composition donut chart"),
    ).toBeVisible({ timeout: 15_000 });

    // CompositionBar must NOT appear: override is gated by targeting.
    const bar = page.locator('[data-component="composition-bar"]');
    expect(await bar.count()).toBe(0);
  });
});
