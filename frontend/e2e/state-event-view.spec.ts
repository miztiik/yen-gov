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

    // Row 2 (2026-06-18): the Races-by-competitiveness board now mounts on
    // PARLIAMENT events too (it previously gated on assembly only). With
    // per-PC winners loaded above, the board section is present + visible
    // on this general-2024 page; each race row links to its PC drill via
    // the body-aware hrefFor seam.
    await expect(page.getByTestId("state-event-races-board")).toBeVisible({
      timeout: 30_000,
    });

    // Alliance panel mounts; after the Phase 1 alliance fix (2026-06-12,
    // plan TODO/20260612-alliance-phase-1-structural-fix-plan.md)
    // general-2024 is curated nationally (state=IN rows), so the panel
    // shows the headline with the alliance totals (NDA-2024 / INDIA-2024
    // / Others). The amber pending pill is the regression signal: if it
    // appears, D1 (loader/route key mismatch) has re-leaked.
    await expect(page.getByTestId("alliance-totals")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByTestId("alliance-totals-headline"),
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByTestId("alliance-totals-headline"),
    ).toContainText(/NDA-2024/);
    await expect(
      page.getByTestId("alliance-totals-headline"),
    ).toContainText(/INDIA-2024/);
    await expect(page.getByTestId("alliance-totals-pending")).toHaveCount(0);

    // TODO/20260612 Row C: Parliament events show a PC map placeholder
    // card (the country PC topojson exists but per-state PC integration
    // is follow-up work). The card pins the citizen-facing copy so the
    // TODO/20260612-pc-choropleth-tile plan Row D: Parliament events now
    // render the StatePcMapD3 component (the country PC topojson is
    // filtered by `state_ut_code === state_code` so only the state's
    // PCs paint). The placeholder card from PR #954 is GONE; assert
    // that the d3 PC choropleth container mounts AND the placeholder
    // testid no longer exists.
    await expect(page.getByTestId("state-pc-map-d3")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByTestId("state-event-pc-map-placeholder"),
    ).toHaveCount(0);

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

  test("party-mute via PartyBar reveals 'Show all (N muted)' reset (Row F)", async ({
    page,
  }) => {
    // TODO/20260612 Row F: clicking a PartyBar row mutes that party;
    // the reset button surfaces above the bar with the muted count.
    // Verified on chhattisgarh general-2024 (small party set, stable).
    await page.goto("/chhattisgarh/elections/general-2024");

    // Wait for the bar to populate (PartyBar emits party-bar-row per
    // ranked party).
    await expect(page.getByTestId("party-bar-row").first()).toBeVisible({
      timeout: 30_000,
    });

    // The reset button is absent until at least one party is muted.
    await expect(
      page.getByTestId("state-event-top-parties-reset"),
    ).toHaveCount(0);

    // Click the first PartyBar row to mute.
    await page.getByTestId("party-bar-row").first().click();

    // Reset surfaces with the muted count.
    await expect(
      page.getByTestId("state-event-top-parties-reset"),
    ).toBeVisible();
    await expect(
      page.getByTestId("state-event-top-parties-reset"),
    ).toContainText(/Show all \(1 muted\)/);

    // Click reset; muted count returns to 0 and the button disappears.
    await page.getByTestId("state-event-top-parties-reset").click();
    await expect(
      page.getByTestId("state-event-top-parties-reset"),
    ).toHaveCount(0);
  });

  test("AC events: Map | Equal seats toggle mounts TileCartogram (Row E)", async ({
    page,
  }) => {
    // TODO/20260612 Row E: assembly events get a Map | Equal seats
    // toggle. Karnataka assembly-2023 has the per-state AC tile layout
    // on disk so the toggle is offered; click "Equal seats" -> the
    // hex container mounts (the map-geo container goes away).
    await page.goto("/karnataka/elections/assembly-2023");

    // Map arm is the default; geo container visible.
    await expect(page.getByTestId("state-event-map-geo")).toBeVisible({
      timeout: 30_000,
    });

    // Toggle visible (Karnataka has a tile layout) and offers two arms.
    await expect(page.getByTestId("state-event-map-view")).toBeVisible({
      timeout: 30_000,
    });
    await page
      .getByTestId("state-event-map-view")
      .getByRole("button", { name: "Equal seats" })
      .click();

    // Hex container mounts after the click.
    await expect(page.getByTestId("state-event-map-hex")).toBeVisible({
      timeout: 30_000,
    });
  });

  test("PC events: Map | Equal seats toggle mounts TileCartogram (per-state PC)", async ({
    page,
  }) => {
    // feat/state-pc-equal-seats: Parliament events in states with >= 4 PCs
    // now get a Map | Equal seats toggle, at parity with assembly events.
    // Bihar general-2024 has 40 PCs and a per-state PC tile layout on disk
    // so the toggle is offered; click "Equal seats" -> the hex container
    // mounts (the geo container goes away).
    await page.goto("/bihar/elections/general-2024");

    // Map arm is the default; PC geo container visible.
    await expect(page.getByTestId("state-event-pc-map-geo")).toBeVisible({
      timeout: 30_000,
    });

    // Toggle visible (Bihar has a per-state PC tile layout) + offers two arms.
    await expect(page.getByTestId("state-event-pc-view")).toBeVisible({
      timeout: 30_000,
    });
    await page
      .getByTestId("state-event-pc-view")
      .getByRole("button", { name: "Equal seats" })
      .click();

    // Hex container mounts after the click.
    await expect(page.getByTestId("state-event-pc-map-hex")).toBeVisible({
      timeout: 30_000,
    });
  });

  test("PC events: below-threshold state stays geo-only (no equal-seats toggle)", async ({
    page,
  }) => {
    // Goa general-2024 has only 2 PCs (< MIN_PCS_FOR_STATE_LAYOUT), so no
    // per-state PC tile layout is authored and the equal-seats toggle is
    // NOT offered. The geographic PC map still renders - nothing regresses.
    await page.goto("/goa/elections/general-2024");

    await expect(page.getByTestId("state-pc-map-d3")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("state-event-pc-view")).toHaveCount(0);
  });

  test("alliance panel: Maharashtra assembly-2024 shows populated headline (Mahayuti / MVA)", async ({
    page,
  }) => {
    // Phase 1 alliance fix smoke 1 (plan TODO/20260612-): the 11 already-
    // curated Mahayuti / MVA rows in datasets/data/entities/party_alliances.csv
    // (state=maharashtra, event_id=assembly-2024) MUST light up after the
    // v2.0 schema rename + state filter. Pre-fix this was the placeholder
    // path because the loader filtered on period_label='AcGenNov2024'
    // strict-equality but the route passed event_id='assembly-2024'.
    await page.goto("/maharashtra/elections/assembly-2024");
    await expect(page.getByTestId("alliance-totals")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByTestId("alliance-totals-headline"),
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByTestId("alliance-totals-headline"),
    ).toContainText(/Mahayuti/);
    await expect(
      page.getByTestId("alliance-totals-headline"),
    ).toContainText(/MVA/);
    await expect(page.getByTestId("alliance-totals-pending")).toHaveCount(0);
  });

  test("alliance panel: Kerala assembly-2021 is silently absent (R6 honesty: no pending pill)", async ({
    page,
  }) => {
    // R6 of TODO/20260615-state-election-event-page-redesign-plan.md
    // (replaces the Phase 1 D2 state-scoping test that asserted the
    // amber pending pill was visible). Max + Hans verdict in plan-doc
    // Section 0.1 (alliance honesty): when the (event_id, state)
    // lookup returns zero alliance rows, the entire panel is
    // SUPPRESSED rather than rendering a debt-tracking pending pill.
    // Kerala asking the lookup for assembly-2021 still MUST NOT
    // inherit the WB Sanyukta Morcha rows (the D2 state-scoping
    // invariant), so the panel stays silent here.
    await page.goto("/kerala/elections/assembly-2021");
    // The section is suppressed when no alliance data; both the
    // panel container AND every sub-testid must be absent.
    await expect(page.getByTestId("alliance-totals")).toHaveCount(0);
    await expect(page.getByTestId("alliance-totals-pending")).toHaveCount(0);
    await expect(page.getByTestId("alliance-totals-headline")).toHaveCount(0);
    // Negative: even when silent, the WB Sanyukta Morcha label MUST
    // NOT leak onto the Kerala page anywhere on the surface.
    await expect(page.locator("body")).not.toContainText(
      "Sanyukta Morcha",
    );
  });
});

// Gap-closure G5 of TODO/20260616-state-event-page-gap-closure-plan.md
// (2026-06-16). The vote-flow APPROXIMATION was replaced by the FACTUAL
// seat-flow (hold/loss) Sankey. Two oracles:
//   1. /maharashtra/elections/assembly-2024  -> holds/flips headline
//      visible, "Show seat flow" pill present, expand reveals the
//      bipartite seat-flow diagram with a FACTUAL caption.
//   2. /jammu-and-kashmir-ut/elections/assembly-2024 -> first event on
//      record for J&K UT; no-prior copy with NO button.
test.describe("state event seat-flow (G5)", () => {
  // Same cold-compile budget as the W3b siblings above; the catalogue
  // + prev-winners loader fetches add ~3-5s on top of route mount.
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

  test("maharashtra/assembly-2024: holds/flips headline + always-on seat-flow diagram", async ({
    page,
  }) => {
    // assembly-2024 has assembly-2019 as the prior same-body event in
    // the on-disk corpus, so the model resolves with ok status and the
    // headline + diagram render.
    await page.goto("/maharashtra/elections/assembly-2024");

    // Section anchor mounts once StateElection's loader resolves the
    // prev-winners state.
    await expect(page.getByTestId("state-event-seat-flow")).toBeVisible({
      timeout: 30_000,
    });

    // Always-on factual headline present (holds / flips of N seats).
    // 60s budget: cold dev-server compile + cold catalogue load +
    // cold loadElectionResults for BOTH assembly-2024 and assembly-2019
    // (the prev-winners loader fires a second roundtrip after the
    // current-event one resolves) can take 30-45s on a freshly-started
    // worker.
    await expect(
      page.getByTestId("state-event-seat-flow-headline"),
    ).toBeVisible({ timeout: 60_000 });
    await expect(
      page.getByTestId("state-event-seat-flow-headline"),
    ).toContainText(/held/);

    // Diagram is ALWAYS-ON (no toggle): it renders directly whenever a
    // prior election exists.
    await expect(
      page.getByTestId("state-event-seat-flow-diagram"),
    ).toBeVisible({ timeout: 10_000 });

    // Caption inside the diagram is FACTUAL - it names the exact
    // seat-transition mechanic, NOT an approximation.
    await expect(
      page.getByTestId("state-event-seat-flow-caption"),
    ).toContainText(/Ribbon width = number of\s+seats/);

    // No-prior copy MUST NOT render here (Maharashtra has a prior
    // event); guards against the no-prior branch leaking when ok data
    // is present.
    await expect(
      page.getByTestId("state-event-seat-flow-no-prior"),
    ).toHaveCount(0);
  });

  test("jammu-and-kashmir-ut/assembly-2024: no-prior copy renders, no headline/diagram", async ({
    page,
  }) => {
    // J&K UT was carved out of J&K state in 2019; assembly-2024 is the
    // first Assembly event on record under the UT state_code. The
    // prev-winners loader resolves no_prior, the model returns
    // { no_prior: true }, and the section renders the no-prior copy.
    await page.goto("/jammu-and-kashmir-ut/elections/assembly-2024");

    await expect(page.getByTestId("state-event-seat-flow")).toBeVisible({
      timeout: 30_000,
    });

    // No-prior copy mounts and pins the load-bearing string.
    await expect(
      page.getByTestId("state-event-seat-flow-no-prior"),
    ).toBeVisible({ timeout: 30_000 });
    await expect(
      page.getByTestId("state-event-seat-flow-no-prior"),
    ).toContainText(/Seat-flow needs a prior election/);
    // \s+ absorbs the JSX newline + leading whitespace gap between
    // "first" and "{body_pretty}" in the multi-line template literal.
    await expect(
      page.getByTestId("state-event-seat-flow-no-prior"),
    ).toContainText(/first\s+Assembly\s+event\s+on\s+record/);

    // Neither the headline nor the diagram may render in the no-prior
    // branch (the seat-flow diagram is always-on only when a prior
    // election exists).
    await expect(
      page.getByTestId("state-event-seat-flow-headline"),
    ).toHaveCount(0);
    await expect(
      page.getByTestId("state-event-seat-flow-diagram"),
    ).toHaveCount(0);
  });
});

