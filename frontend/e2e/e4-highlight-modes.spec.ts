// E4 highlight modes + margin sub-filter browser smoke (parent plan
// section 25.5).
//
// CLAUDE.md section 13 gate for the new `MapHighlightLegend` shared
// legend driving BOTH `StateAcMap` (maplibre choropleth) and
// `TileCartogram` (SVG hex cartogram). Vitest covers the pure helpers
// (`marginOpacity`, `cellTreatment`, `advanceLegendState`) and the
// legend reducer; this spec proves the live citizen render wires the
// segmented control, the party-pill tap, and the stepped margin
// slider into a SINGLE legend instance whose state is consumed by
// both map surfaces.
//
// "Legend-drift" contract (parent plan section 22.6): asserts the
// page renders EXACTLY ONE `MapHighlightLegend` instance and no per-
// map bespoke widget. Future drift (a second legend, a per-arm
// slider, a parallel mode toggle) fails this gate.
//
// Mobile project skip: the legend has no breakpoint-specific code
// path; the assertions are click-target-based not pixel-based. Same
// posture as `e3-silhouette-smoke.spec.ts`.

import { test, expect } from "@playwright/test";
import { attachPageErrorTrap } from "./_helpers";

// Tamil Nadu has both a per-state AC choropleth (StateAcMap) AND a
// persisted hex layout (election_tile_layouts.json covers S22 /
// scope=S22, layout_kind=ac, delim_year=2008), so a single state
// covers BOTH arms. AcGenApr2021 is the canonical state-election
// surface used by the E3 silhouette smoke + the state-ac-coverage
// suites - same risk axis here.
const TARGET_PAGE = "/tamil-nadu/elections/AcGenApr2021";

let trap: ReturnType<typeof attachPageErrorTrap> | null = null;

test.beforeEach(({ page }, testInfo) => {
  trap = null;
  test.skip(
    testInfo.project.name === "mobile-pixel-5",
    "E4 highlight modes smoke is desktop-only (no breakpoint-specific code path)",
  );
  trap = attachPageErrorTrap(page);
});

test.afterEach(() => {
  const errors = trap?.getErrors() ?? [];
  trap = null;
  expect(errors, `Page emitted runtime errors:\n${errors.join("\n")}`).toEqual([]);
});

test.describe("E4 - one shared MapHighlightLegend instance", () => {
  test("renders exactly ONE MapHighlightLegend on the state election surface", async ({
    page,
  }) => {
    await page.goto(TARGET_PAGE, { waitUntil: "domcontentloaded" });

    const legend = page.locator(
      `[data-testid="election-map-highlight-legend"]`,
    );
    // Wait for the legend to mount - it's gated on `legend_parties.length`,
    // which only becomes non-empty after the winners view-model resolves.
    await expect(legend).toHaveCount(1, { timeout: 30_000 });
    await expect(legend).toBeVisible();
  });
});

test.describe("E4 - mode toggle (margin <-> party_won)", () => {
  test("flipping mode via segmented control updates legend state + recede pills", async ({
    page,
  }) => {
    await page.goto(TARGET_PAGE, { waitUntil: "domcontentloaded" });

    const legend = page.locator(
      `[data-testid="election-map-highlight-legend"]`,
    );
    await expect(legend).toHaveCount(1, { timeout: 30_000 });

    // Default mode is "margin" - no min-margin slider visible.
    await expect(legend).toHaveAttribute("data-mode", "margin");
    await expect(
      page.locator(
        `[data-testid="election-map-highlight-legend-min-margin"]`,
      ),
    ).toHaveCount(0);

    // Flip mode -> party_won via segmented control's "party_won" segment.
    const modePicker = page.locator(
      `[data-testid="election-map-highlight-legend-mode"]`,
    );
    await expect(modePicker).toBeVisible();
    await modePicker
      .locator(`button[data-segment-value="party_won"]`)
      .click();

    // Legend's data-mode reflects the new mode; auto-pick of the first
    // legend party means data-selected-party-id is now non-empty.
    await expect(legend).toHaveAttribute("data-mode", "party_won");
    const selected_attr = await legend.getAttribute("data-selected-party-id");
    expect(selected_attr, "auto-picks first party on flip").toBeTruthy();

    // The min-margin slider appears in party_won mode.
    await expect(
      page.locator(
        `[data-testid="election-map-highlight-legend-min-margin"]`,
      ),
    ).toHaveCount(1);

    // Flip back to margin mode via the segmented control.
    await modePicker
      .locator(`button[data-segment-value="margin"]`)
      .click();
    await expect(legend).toHaveAttribute("data-mode", "margin");
    // Slider disappears.
    await expect(
      page.locator(
        `[data-testid="election-map-highlight-legend-min-margin"]`,
      ),
    ).toHaveCount(0);
  });
});

test.describe("E4 - margin sub-filter slider steps", () => {
  test("clicking a margin step updates data-min-margin", async ({ page }) => {
    await page.goto(TARGET_PAGE, { waitUntil: "domcontentloaded" });
    const legend = page.locator(
      `[data-testid="election-map-highlight-legend"]`,
    );
    await expect(legend).toHaveCount(1, { timeout: 30_000 });
    // Activate party_won mode so the slider is rendered.
    await page
      .locator(
        `[data-testid="election-map-highlight-legend-mode"] button[data-segment-value="party_won"]`,
      )
      .click();
    await expect(legend).toHaveAttribute("data-mode", "party_won");

    const slider = page.locator(
      `[data-testid="election-map-highlight-legend-min-margin"]`,
    );
    await expect(slider).toBeVisible();

    // Click the 20% step and confirm the legend's data-min-margin updates.
    await slider.locator(`button[data-min-margin-step="20"]`).click();
    await expect(legend).toHaveAttribute("data-min-margin", "20");
    // The active step button reports its active state via data-active="true".
    await expect(
      slider.locator(`button[data-min-margin-step="20"]`),
    ).toHaveAttribute("data-active", "true");

    // Click "Any" (0) to clear the filter.
    await slider.locator(`button[data-min-margin-step="0"]`).click();
    await expect(legend).toHaveAttribute("data-min-margin", "0");
  });
});

test.describe("E4 - TileCartogram recede styling in party_won mode", () => {
  test("hex tiles non-matching the selected party get data-recede='true'", async ({
    page,
  }) => {
    // The hex arm renders by appending ?view=hex to the route. Tamil Nadu
    // has a persisted layout for AcGenApr2021 so the cartogram mounts.
    await page.goto(`${TARGET_PAGE}?view=hex`, {
      waitUntil: "domcontentloaded",
    });

    // Wait for the hex container + at least one polygon.
    const hexBox = page.locator(`[data-testid="election-map-hex"]`);
    await expect(hexBox).toBeVisible({ timeout: 30_000 });

    const polygons = hexBox.locator(`polygon[data-unit-id]`);
    await expect(polygons.first()).toBeVisible({ timeout: 30_000 });

    // Default mode = margin -> NO polygon should carry data-recede="true".
    const receded_default = await hexBox
      .locator(`polygon[data-recede="true"]`)
      .count();
    expect(
      receded_default,
      "margin mode: no polygon recedes (every polygon is at margin opacity)",
    ).toBe(0);

    // Flip to party_won via the shared legend.
    const legend = page.locator(
      `[data-testid="election-map-highlight-legend"]`,
    );
    await expect(legend).toHaveCount(1, { timeout: 30_000 });
    await page
      .locator(
        `[data-testid="election-map-highlight-legend-mode"] button[data-segment-value="party_won"]`,
      )
      .click();
    await expect(legend).toHaveAttribute("data-mode", "party_won");

    // After the flip: at LEAST one polygon should be receding (cells not
    // won by the auto-picked first party) AND at LEAST one polygon should
    // NOT be receding (cells won by the selected party).
    await expect
      .poll(
        () => hexBox.locator(`polygon[data-recede="true"]`).count(),
        { timeout: 30_000 },
      )
      .toBeGreaterThan(0);
    await expect
      .poll(
        () => hexBox.locator(`polygon[data-recede="false"]`).count(),
        { timeout: 30_000 },
      )
      .toBeGreaterThan(0);

    // The cartogram's SVG also exposes the highlight-mode + selected
    // party as data attrs - cross-check they're in sync with the legend.
    const svg = hexBox.locator(`svg[data-highlight-mode]`);
    await expect(svg).toHaveAttribute("data-highlight-mode", "party_won");
    const svg_party = await svg.getAttribute("data-selected-party-id");
    const legend_party = await legend.getAttribute("data-selected-party-id");
    expect(
      svg_party,
      "TileCartogram + MapHighlightLegend share the SAME selected party",
    ).toBe(legend_party);
  });
});

test.describe("E4 - party pill tap drives the highlight selection", () => {
  test("tapping a party pill in margin mode flips to party_won + selects", async ({
    page,
  }) => {
    await page.goto(`${TARGET_PAGE}?view=hex`, {
      waitUntil: "domcontentloaded",
    });
    const legend = page.locator(
      `[data-testid="election-map-highlight-legend"]`,
    );
    await expect(legend).toHaveCount(1, { timeout: 30_000 });
    await expect(legend).toHaveAttribute("data-mode", "margin");

    // Find the first party pill and tap it. Defensive: the legend pills
    // are rendered inside the parties container with data-component on
    // each PartyPill button.
    const parties_box = page.locator(
      `[data-testid="election-map-highlight-legend-parties"]`,
    );
    const first_pill = parties_box
      .locator(`button[data-component="party-pill"]`)
      .first();
    await expect(first_pill).toBeVisible({ timeout: 30_000 });
    const tapped_pid = await first_pill.getAttribute("data-party-id");
    expect(tapped_pid).toBeTruthy();
    await first_pill.click();

    // Legend flips to party_won + selects the tapped party.
    await expect(legend).toHaveAttribute("data-mode", "party_won");
    await expect(legend).toHaveAttribute(
      "data-selected-party-id",
      tapped_pid!,
    );

    // Tapping the SAME pill again clears + reverts to margin mode.
    await first_pill.click();
    await expect(legend).toHaveAttribute("data-mode", "margin");
    await expect(legend).toHaveAttribute("data-selected-party-id", "");
  });
});
