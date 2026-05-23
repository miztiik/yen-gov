// Stacked-trend route smoke: /t/energy renders the new chart, the legend,
// the unit/mode chip, and the SourceList — without runtime errors.
//
// Per CLAUDE.md §15: a citizen-visible route MUST land with at least:
//   • route loads, no `pageerror`
//   • one DOM assertion that proves the new content is there
//   • a SourceList provenance assertion (data-bearing route)

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

test.describe("stacked-trend on /t/energy", () => {
  test("renders the composed installed-capacity stacked chart", async ({ page }) => {
    await page.goto("/t/energy");
    await expect(page.getByRole("heading", { name: "Power & energy", level: 1 })).toBeVisible({
      timeout: 15_000,
    });

    // Mode chip is rendered by StackedTrendV2 once the model resolves.
    // Phase 2.7 (commit 1742eba7) introduced MODE_LABELS — the visible
    // button copy is now "Share"/"Total" while the stable enum token
    // stays "percent"/"absolute" on `data-mode-value`. Anchor the
    // assertion to the stable attribute so future copy tweaks don't
    // re-break this test. /t/energy mounts multiple StackedTrendV2
    // instances (one per fuel breakdown) so .first() honours the
    // "at least one mode toggle rendered" intent.
    await expect(
      page.locator('[data-control="mode-toggle"] [data-mode-value="percent"]').first(),
    ).toBeVisible({ timeout: 15_000 });

    // Legend includes at least one of the known fuel labels.
    await expect(page.getByText("Coal").first()).toBeVisible();

    // Provenance: the chart is data-bearing, so SourceList must appear.
    // It sits inside the AboutThisData <details> accordion (default
    // collapsed) — toBeAttached honours that without depending on the
    // collapsed-by-default UX choice. Mirrors golden-path.spec.ts:108.
    await expect(page.getByText(SOURCE_LIST_TEXT).first()).toBeAttached();
  });

  // Phase 2.7 — SVG export control.
  //
  // The button is data-tagged `data-action="download-svg"` so this spec
  // doesn't depend on the visible glyph or copy. Per /t/energy mounting
  // many StackedTrendV2 instances, there can be N buttons; we assert
  // ≥1 attached and ≥1 visible after scrolling the first into view.
  test("phase 2.7: each StackedTrendV2 chart exposes an SVG download button", async ({ page }) => {
    await page.goto("/t/energy");
    await expect(page.getByRole("heading", { name: "Power & energy", level: 1 })).toBeVisible({
      timeout: 15_000,
    });

    const buttons = page.locator('[data-action="download-svg"]');
    await expect(buttons.first()).toBeAttached({ timeout: 15_000 });
    const count = await buttons.count();
    expect(count, "expected at least one SVG download button on /t/energy").toBeGreaterThan(0);

    // The handler builds a Blob URL + suggested filename WITHOUT
    // navigating. We assert the wiring by spying on document.createElement
    // and capturing the synthetic anchor's `download` attribute when the
    // button is clicked. This avoids depending on a real browser-download
    // dialog (Playwright's `download` event triggers only on user-gesture
    // anchor click in some channels) and proves the helper composed both
    // a blob URL and a slug-shaped filename.
    const captured = await page.evaluate(() => {
      const btn = document.querySelector<HTMLButtonElement>(
        '[data-action="download-svg"]',
      );
      if (!btn) return { err: "no button" };
      const orig = document.createElement.bind(document);
      let result: { href: string; download: string } | null = null;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (document as any).createElement = function (tag: string) {
        const el = orig(tag);
        if (tag === "a") {
          (el as HTMLAnchorElement).click = function () {
            result = {
              href: (el as HTMLAnchorElement).href,
              download: (el as HTMLAnchorElement).download,
            };
          };
        }
        return el;
      };
      try {
        btn.click();
      } finally {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (document as any).createElement = orig;
      }
      return result ?? { err: "no anchor captured" };
    });
    expect(captured, "click handler should have created a download anchor").toMatchObject({
      href: expect.stringMatching(/^blob:/),
      download: expect.stringMatching(/^.+\.svg$/),
    });
  });
});
