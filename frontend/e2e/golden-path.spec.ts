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

    // IA-reset Step #3b: the Theme <select> shows humanised indicator
    // titles (e.g. "Outstanding liabilities (% of GSDP)") rather than
    // raw schema slugs ("fiscal/outstanding_debt_pct_gsdp"). Titles are
    // pulled from each indicator artifact's own `indicator.title` and
    // populated after the per-indicator JSON fetches resolve, so we
    // wait on the humanised label before asserting absence of slugs.
    const theme_select = page.getByRole("combobox").first();
    await expect(theme_select).toBeVisible({ timeout: 15_000 });
    await expect(
      theme_select.locator("option", { hasText: /Outstanding liabilities/i }),
    ).toHaveCount(1, { timeout: 15_000 });
    const option_text = await theme_select.locator("option").allInnerTexts();
    const joined = option_text.join(" | ");
    expect(joined, `Theme dropdown leaked raw slugs:\n${joined}`).not.toMatch(/fiscal\//);
    expect(joined, `Theme dropdown leaked raw slugs:\n${joined}`).not.toMatch(/energy\//);

    // Phase #3 of TODO/20260517-coverage-temporal-range-plan.md: when an
    // IndicatorChoropleth has a derivable temporal range, it renders a
    // citizen-facing caption ("YYYY → YYYY · cadence-word"). The caption
    // is gated on deriveTemporalRange() returning non-null — point-in-time
    // indicators legitimately render no caption. So we assert shape only
    // IF a caption is present on the home default; otherwise the wiring
    // is covered by vitest (frontend/src/lib/indicators.test.ts).
    const caption = page.getByTestId("indicator-temporal-caption").first();
    if ((await caption.count()) > 0) {
      const caption_text = (await caption.textContent())?.trim() ?? "";
      expect(
        caption_text,
        `Temporal caption empty or missing cadence vocabulary: "${caption_text}"`,
    ).toMatch(/(annual|quarterly|monthly|every 10 years|irregular updates|As of)/i);
    }

    // Unmapped-region chip strip (ADR-0029): Lakshadweep + A&N Islands are
    // sub-pixel on the India choropleth, so their indicator value is
    // surfaced as a value chip on the legend strip instead. The strip only
    // mounts when the active indicator has values for those entities; the
    // default home indicator may not, so assert the Lakshadweep label only
    // when the strip is actually present. Chip-model construction is
    // covered by frontend/src/lib/unmapped-region-chips.test.ts.
    const chip_strip = page
      .getByTestId("unmapped-region-chip-strip")
      .first();
    if ((await chip_strip.count()) > 0) {
      await expect(
        chip_strip.locator('[data-entity-id="U04"]'),
      ).toContainText(/Lakshadweep/i);
    }

    // PR-G (Phase 1.3c) — canonical bulk JOIN evidence for IndiaMap.
    // The map now resolves all ~36 state leading-party fills through one
    // DuckDB-WASM call (loadIndiaLeadingParties) instead of per-state
    // fetchResultSummary fan-out. The failure path renders an inline
    // rose banner ("Failed to load state summaries"). Asserting that
    // banner is NOT present after the canvas mounts proves the bulk
    // pivot succeeded against the canonical store. (Tooltip HTML is
    // only injected on hover into a maplibre popup div, which is
    // pixel-coord dependent on the canvas — not addressable by Playwright
    // without brittle hover targeting. The negative assertion + the
    // unit-tested loader contract together give us the regression guard.)
    await expect(page.getByText(/Failed to load state summaries/i))
      .toHaveCount(0, { timeout: 15_000 });
  });

  test("state overview renders party totals and AC list for Tamil Nadu", async ({ page }) => {
    await page.goto("/s/tamil-nadu");
    // result.summary.json fetch + render. Target the recency heading
    // explicitly — `/Assembly election/i` alone now matches both the H1
    // ("Most recent assembly election: …") and a downstream chart caption
    // ("Each bar = one assembly election …"), which trips strict mode.
    await expect(page.getByText(/Most recent assembly election/i)).toBeVisible({ timeout: 15_000 });
    // At least one AC link rendered (constituencies.json loaded). Filter
    // by href shape — name-based queries are brittle here because the
    // visible text concatenates eci_no + AC name + reservation tag.
    await expect(page.locator('a[href*="/ac/"]').first()).toBeVisible({ timeout: 15_000 });
    // Provenance: SourceList renders "Sources (N)" once data loads. It now
    // sits inside the AboutThisData <details> accordion (default collapsed),
    // so it is attached to the DOM but not visible until the citizen opens
    // the disclosure. CLAUDE.md §15 only requires that the provenance
    // surface exists; toBeAttached() honours that without depending on the
    // collapsed-by-default UX choice.
    await expect(page.getByText(SOURCE_LIST_TEXT).first()).toBeAttached({ timeout: 15_000 });

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

    // PR-F (Phase 1.3b) — canonical JOIN evidence. StateOverview now reads
    // party totals through view-models/state-overview.ts (DuckDB-WASM →
    // observations ⋈ dim_parties ⋈ sources). DMK is the largest seat-winning
    // party in every TN assembly election in the canonical store; if the
    // pivot JOIN regresses, the party directory + PartyBar lose its name.
    await expect(page.getByText(/\bDMK\b/).first())
      .toBeVisible({ timeout: 15_000 });
  });

  test("constituency page renders top-N candidates via DuckDB-WASM loader", async ({ page }) => {
    // PR-E (Phase 1.3a): /ac/* now reads through the canonical Parquet
    // store via DuckDB-WASM (`lib/view-models/constituency.ts`) rather
    // than per-shard JSON. AC #1 (Gummidipoondi) is the slice the live
    // backend test covers; the canonical dim_candidates table holds the
    // AcGenMay2026 contest (TN's default event).
    await page.goto("/s/tamil-nadu/ac/1-gummidipoondi");
    await expect(page.getByRole("heading", { level: 2, name: /Top \d+ candidates/i }))
      .toBeVisible({ timeout: 30_000 });
    // Header row of the candidates table
    await expect(page.getByRole("columnheader", { name: "Candidate" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Party" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Votes" })).toBeVisible();

    // The JOIN actually fired: a known AcGenMay2026 AC#1 candidate must
    // render in the table cell. "Vijayakumar" is the winning candidate
    // for AC#1 in the canonical dim_candidates 2026 partition. If the
    // dim → observations JOIN regresses, this row will be missing.
    await expect(page.getByRole("cell", { name: /Vijayakumar/i }).first())
      .toBeVisible({ timeout: 30_000 });

    // Provenance: the canonical loader projects URLs from taxonomy/sources
    // into the legacy SourceList shape. Asserting an ECI link is present
    // proves the sources JOIN to taxonomy/sources.parquet wired up.
    await expect(page.locator('a[href*="eci.gov.in"]').first())
      .toBeVisible({ timeout: 30_000 });

    // people.entity sidecar: AC 1 winner GOVINDARAJAN T.J has a sidecar
    // shipped via the TN AE 2021 ingest (datasets/people/AcGenApr2021/1/
    // govindarajan-t-j.json). The biographic line ("Male · age 60 · 10th
    // Pass · Business") only surfaces when TN's default election event is
    // AcGenApr2021. The default is now AcGenMay2026 (no biographics ingest),
    // so the route legitimately renders "Not declared" via the 404-as-null
    // contract. Assert the biographics testid renders for at least one
    // candidate; the populated-fields path is covered by vitest
    // (frontend/src/lib/data.test.ts — fetchPersonEntity contract).
    const bio = page.getByTestId("candidate-biographics").first();
    await expect(bio).toBeVisible({ timeout: 30_000 });
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
    // inside the IndicatorCard's AboutThisData <details> accordion (default
    // collapsed). Assert it is attached, not visible; the §15 contract is
    // "provenance surface exists on the route", not "is expanded by default".
    await expect(page.getByText(SOURCE_LIST_TEXT).first())
      .toBeAttached({ timeout: 15_000 });

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
