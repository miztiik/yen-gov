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
  test("home renders India map and topic-grid front door", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "yen-gov", level: 1 })).toBeVisible();
    // Map section header. The caption after "India — " rotates daily through
    // the curated-5 indicator pool (PR-2, day-of-year), so the prior
    // /winning party by state/i regex was brittle (only true on election-theme
    // days). Assert the stable "India — " prefix instead. This keeps the
    // "map mounted" guard without coupling to the rotating caption.
    await expect(page.getByRole("heading", { level: 2, name: /^India/i })).toBeVisible({ timeout: 15_000 });

    // PR-3 (2026-06-11): the alphabetical state lists ("Available" +
    // "Other states (no data yet)") are GONE; the home front door is the
    // catalogue-driven topic grid. Positive + negative assertions locked
    // in one bundle so a regression on either side trips this spec.
    await expect(page.getByTestId("home-topic-grid")).toBeVisible({ timeout: 15_000 });
    const cardCount = await page.getByTestId("home-topic-card").count();
    expect(cardCount).toBeGreaterThanOrEqual(1);
    await expect(page.locator("h2:has-text('Available')")).toHaveCount(0);
    await expect(page.locator("h2:has-text('Other states')")).toHaveCount(0);

    // Theme-dropdown humanised labels + temporal-caption vocabulary are
    // asserted by vitest (frontend/src/lib/home-theme.test.ts and
    // frontend/src/lib/indicators.test.ts deriveTemporalRange suite).
    // Per docs/archive/plans/20260531-e2e-runtime-trim-plan.md PR-3, the cheaper tier
    // owns the exhaustive assertion; e2e keeps only the mount + render
    // + bulk-JOIN-evidence guards.

    // D.1.A (2026-05-30): the unmapped-region chip strip and the legacy
    // Lakshadweep polygon inset were both retired per user mandate
    // ("REMOVE ANY SIDE FIXES FOR LAKSHADWEEP..."). All UTs now render on
    // the map at true geographic location; if a polygon is sub-pixel at
    // current zoom, the citizen zooms in to see. No chip-strip assertion
    // belongs in this spec.

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
    await page.goto("/tamil-nadu");
    // result.summary.json fetch + render. Target the recency heading
    // explicitly — `/Assembly election/i` alone now matches both the H1
    // ("Most recent assembly election: …") and a downstream chart caption
    // ("Each bar = one assembly election …"), which trips strict mode.
    await expect(page.getByText(/Most recent assembly election/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("event-picker")).toHaveValue("AcGenMay2026");
    // At least one AC link rendered (constituencies.json loaded). Filter
    // by href shape — name-based queries are brittle here because the
    // visible text concatenates eci_no + AC name + reservation tag.
    await expect(page.locator('a[href*="/ac/"]').first()).toBeVisible({ timeout: 45_000 });
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

  test("state overview never flashes the bootstrap notice during slow constituencies load (race-condition guard)", async ({ page }) => {
    // Regression for the 2026-05-23 bug where /tamil-nadu briefly showed
    // "Per-constituency directory for Tamil Nadu Assembly · May 2026 isn't
    // available yet — the constituencies reference file for this state still
    // needs to be bootstrapped" even though the JSON existed on disk and was
    // about to load. Root cause: StateOverview's empty-state branch fired
    // on `acs === null`, which is true BOTH while the fetch is in flight
    // AND on failure — the DuckDB-WASM summary loader routinely beat the
    // JSON fetch, exposing the wrong branch for a few hundred ms.
    //
    // Fix: a 3-state `acs_status` discriminator (loading / ready / failed).
    // This test throttles the JSON fetch to a 1.5s delay so the race window
    // is wide and deterministic; the bootstrap copy must NOT appear at any
    // point during that window, and the AC list must still arrive.
    await page.route("**/data/data/entities/boundaries_sot/S22/constituencies.json", async (route) => {
      await new Promise((r) => setTimeout(r, 1500));
      await route.continue();
    });
    await page.goto("/tamil-nadu");
    // Summary should land first (DuckDB-WASM JOIN against the canonical
    // store), establishing the race window.
    await expect(page.getByText(/Most recent assembly election/i)).toBeVisible({ timeout: 15_000 });
    // Pre-fix: the bootstrap notice rendered here for ~1.5s. Post-fix the
    // page shows "Loading constituency directory…" instead.
    await expect(page.getByText(/constituency directory unavailable/i)).toHaveCount(0);
    await expect(page.getByText(/bootstrap_constituencies_from_results/)).toHaveCount(0);
    // And the directory eventually renders (proves the fix didn't break
    // the success arm — `acs_status` transitions through "ready").
    await expect(page.locator('a[href*="/ac/"]').first()).toBeVisible({ timeout: 15_000 });
  });

  test("constituency page renders top-N candidates via DuckDB-WASM loader", async ({ page }) => {
    // PR-E (Phase 1.3a): /ac/* now reads through the canonical Parquet
    // store via DuckDB-WASM (`lib/view-models/constituency.ts`) rather
    // than per-shard JSON. AC #1 (Gummidipoondi) is the slice the live
    // backend test covers; the canonical dim_candidates table holds the
    // AcGenMay2026 contest (TN's default event).
    await page.goto("/tamil-nadu/ac/1-gummidipoondi");
    // ADR-0051: the bare /ac/ entry is not canonical — it replaceState-
    // redirects to the identity-complete nested form
    // /<state>/elections/<event>/ac/<n-slug>. Assert the address bar
    // settled on the nested shape before checking content.
    await expect
      .poll(() => new URL(page.url()).pathname, { timeout: 30_000 })
      .toMatch(/\/s\/tamil-nadu\/elections\/[^/]+\/ac\/1-gummidipoondi$/);
    // exists, else "N candidate(s)". AC#1 has more than top_n_cutoff
    // contestants so the "Top N of M" form is expected here; the regex
    // tolerates the no-tail form too in case the seed shrinks.
    await expect(page.getByRole("heading", { level: 2, name: /(Top \d+ of \d+ candidates|^\d+ candidates?$)/i }))
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

    // Biographics: dim_candidates.parquet schema v1.2 (PR-S.1) carries
    // sex/age/education/profession/constituency_type/party_type as inline
    // columns. The view-model loader projects them onto
    // `CandidateResult.bio`; the row renders a chip whenever at least one
    // field is populated (the citizen sees e.g. "Male · age 60 · 10th
    // Pass · Business"). The TN default election is now AcGenMay2026
    // (no Statistical Report adapter run yet), so this route surfaces bio
    // for the AcGenApr2021 candidates only when that event is chosen.
    // Assert the biographics testid renders for at least one candidate;
    // the citizen-facing render path is covered, the SQL projection by
    // view-models/constituency.test.ts. PR-S.2 (canonical pivot 1.8f)
    // retired the per-candidate JSON sidecar fetch path entirely. When no
    // bio is ingested the node renders EMPTY (no "Not declared" label), so
    // we assert `toBeAttached` (testid present in the DOM) rather than
    // `toBeVisible` (which an empty node fails by design).
    const bio = page.getByTestId("candidate-biographics").first();
    await expect(bio).toBeAttached({ timeout: 30_000 });
  });

  // PR-P (row 1.8c) gate: the canonical loader (`view-models/constituency.ts`)
  // is the sole reader of /ac/* after the per-AC `results/<n>.json` shards
  // are deleted. The TN test above proves the dim-tables/observations JOIN
  // shape works for one state. KL + WB are added as the "3-state representative
  // sample" the row 1.8c gate calls for: different state codes (S11, S25),
  // different AC numbering/slug families, and (for WB) a reservation suffix
  // in the AC name (MEKLIGANJ (SC) → slug `1-mekliganj-sc`) that exercises the
  // url.ts slug-roundtrip on a non-trivial source string. These tests are
  // intentionally structural-only (no per-state winner-name assertions) — TN
  // owns the data-correctness assertion; KL/WB own the route-resolution +
  // canonical-loader-fan-out-across-states assertion.
  for (const [state_label, state_slug, ac_slug] of [
    ["Kerala", "kerala", "1-manjeshwar"],
    ["West Bengal", "west-bengal", "1-mekliganj-sc"],
  ] as const) {
    test(`constituency page renders via canonical loader for ${state_label} AC#1`, async ({ page }) => {
      await page.goto(`/${state_slug}/ac/${ac_slug}`);
      // Same Phase 1.6 (PR-K) "Top N of M candidates" heading shape the TN
      // test asserts; the loader's reconstruction of `others` (when the
      // canonical adapter ships an `ac-others-{votes,pct}` pair) is what
      // produces the "of M" tail. Both KL and WB AcGenMay2026 slices have
      // >5 contestants per AC so the "Top N of M" form is expected.
      await expect(page.getByRole("heading", { level: 2, name: /(Top \d+ of \d+ candidates|^\d+ candidates?$)/i }))
        .toBeVisible({ timeout: 30_000 });
      // Header row of the candidates table — proves dim_candidates JOIN
      // returned at least one row.
      await expect(page.getByRole("columnheader", { name: "Candidate" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Party" })).toBeVisible();
      await expect(page.getByRole("columnheader", { name: "Votes" })).toBeVisible();
      // Provenance: taxonomy/sources rows for AcGenMay2026 carry ECI URLs;
      // asserting the link surfaced proves the canonical sources JOIN ran
      // for non-TN states too (the most likely regression mode if the
      // loader hard-coded an event/state filter).
      await expect(page.locator('a[href*="eci.gov.in"]').first())
        .toBeVisible({ timeout: 30_000 });
      // Biographics testid presence (404-as-null contract — see TN test
      // above). KL/WB AcGenMay2026 have no biographics sidecar ingest yet
      // so all candidates render EMPTY, but the testid must still be in the
      // DOM for at least the first row — assert attachment, not visibility.
      const bio = page.getByTestId("candidate-biographics").first();
      await expect(bio).toBeAttached({ timeout: 30_000 });
    });
  }

  test("explore page lazy-loads DuckDB-WASM without error", async ({ page }) => {
    // The /explore route mounts DuckDB-WASM (Phase 1.6b — migrated off
    // sql.js). If the wasm chunk fails to load, the route shows an error
    // banner rather than crashing. The beforeEach pageerror trap covers
    // the failure mode; the waitForTimeout gives DuckDB-WASM time to boot
    // so any runtime error fires before afterEach checks the trap.
    // Note: networkidle never resolves on DuckDB-WASM apps (persistent
    // worker connections); use load + explicit timeout instead.
    await page.goto("/tamil-nadu/explore", { waitUntil: "load" });
    await page.waitForTimeout(7_000);
  });

  test("state elections landing page (/:state/elections) renders breadcrumb + both body tables with year-as-link", async ({ page }) => {
    // R2 of TODO/20260615-state-election-event-page-redesign-plan.md
    // (PR #1066 + R2.1 gap-close): the bare `/<state>/elections` URL
    // mounts `StateElectionsLanding.svelte`, which lists every assembly
    // + parliament event the state has on record. Maharashtra has both
    // bodies represented in the catalogue so it exercises the
    // two-table arm. The router compiles `/:state/elections` to a
    // strict `^/([^/]+)/elections$` regex (no trailing slash) per the
    // pattern compiler in `lib/router.svelte.ts`, mirroring every
    // other case in this file.
    await page.goto("/maharashtra/elections");

    // Breadcrumb landmark + the state link by href shape (display name
    // comes from states.json so we assert structure, not copy).
    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(breadcrumb).toBeVisible({ timeout: 15_000 });
    await expect(breadcrumb.locator('a[href$="/maharashtra"]')).toBeVisible();

    // Page header renders the "{State} elections" heading.
    await expect(page.getByTestId("state-elections-landing-header"))
      .toBeVisible({ timeout: 15_000 });

    // Both body tables present (Maharashtra has both assembly +
    // parliament events on record). If either is missing the citizen
    // sees only half the per-state archive.
    await expect(page.getByTestId("state-elections-landing-assembly-table"))
      .toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("state-elections-landing-parliament-table"))
      .toBeVisible({ timeout: 15_000 });

    // At least one year-link points back to the per-event detail page
    // under `/maharashtra/elections/<event_id>` (the canonical W3b URL
    // shape — see ADR-0052 + url-grammar.md). This is the partner the
    // `Last viewed` badge eventually annotates.
    const eventLinks = page.locator(
      'a[href*="/maharashtra/elections/"]',
    );
    expect(await eventLinks.count()).toBeGreaterThanOrEqual(1);
  });

  test("per-state topic page (/:state/t/:topic) renders cards + breadcrumb", async ({ page }) => {
    // IA-reset Step #2: pick a state → click a topic in the rail → land
    // here. Asserts the route shell (breadcrumb + heading), at least one
    // IndicatorCard rendered, and SourceList provenance per CLAUDE.md §15.
    await page.goto("/tamil-nadu/t/fiscal");

    // Breadcrumb: "Tamil Nadu" is clickable, "Money & debt"-equivalent
    // (catalogue title for `fiscal`) is current. We assert the structural
    // landmark + the state link by href shape rather than its label, since
    // states.json drives the display name.
    const breadcrumb = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(breadcrumb).toBeVisible({ timeout: 15_000 });
    await expect(breadcrumb.locator('a[href$="/tamil-nadu"]')).toBeVisible();

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
    await page.goto("/tamil-nadu/t/nonsense-topic-slug");
    await expect(page.getByRole("heading", { name: /Topic not found/i }))
      .toBeVisible({ timeout: 15_000 });
  });

  test("per-state topic page 404s cleanly on unknown state slug", async ({ page }) => {
    await page.goto("/nonsense-state-slug/t/fiscal");
    await expect(page.getByRole("heading", { name: /State not found/i }))
      .toBeVisible({ timeout: 15_000 });
  });
});
