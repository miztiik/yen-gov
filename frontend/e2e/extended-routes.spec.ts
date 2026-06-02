// Extended-route smoke tests — non-golden-path routes that still ship in
// the bundle and could regress silently. Each test asserts:
//   1. route mounts (no `pageerror`, attached via beforeEach trap)
//   2. the route's identifying copy is in the DOM
//
// Routes covered:
//   /about                                     — about page
//   /disclaimer                                — legal-style disclaimer
//   /settings                                  — color overrides editor
//   /no-such-route                             — 404 fallback
//   /s/tamil-nadu/party/dmk-DMK                — party page
//   /lab/tamil-nadu/AcGenMay2026               — Psephlab simulator
//   /compare/tamil-nadu/AcGenMay2026           — Compare surface
//
// These routes are NOT pixel-asserted; they're smoke tests. Visual specs
// (screenshot-diff) belong in a separate file when/if added (CLAUDE.md §15).

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

test.describe("extended routes", () => {
  test("about page renders disclaimer header", async ({ page }) => {
    await page.goto("/about");
    await expect(page.getByRole("heading", { level: 1, name: /About yen-gov/i })).toBeVisible();
    // The "broader civic-data hub" framing is the load-bearing copy on
    // this page (cited in commit messages). If it's gone, the doc-code
    // sync (CLAUDE.md Holy Law #4) has drifted.
    await expect(page.getByText(/yen-gov is not just an elections site/i)).toBeVisible();
  });

  test("disclaimer page renders legal-style sections", async ({ page }) => {
    await page.goto("/disclaimer");
    await expect(page.getByRole("heading", { level: 1, name: /^Disclaimer$/ })).toBeVisible();
    // The Accuracy / Completeness / Methodology / Citation / Corrections
    // headings are the load-bearing structure (paste-ready copy from
    // handover §8.2). All five must render.
    await expect(page.getByRole("heading", { level: 2, name: /Accuracy/ })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: /Completeness/ })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: /Methodology/ })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: /Citation/ })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: /Corrections/ })).toBeVisible();
  });

  test("settings page renders the party colour explainer", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { level: 1, name: "Settings" })).toBeVisible();
    // Party colours are no longer editable (one-identity party-colour
    // migration). The page is now a read-only explainer of the
    // three-tier colour resolver rather than a per-browser override
    // editor.
    await expect(
      page.getByRole("heading", { level: 2, name: /How party colours are chosen/i }),
    ).toBeVisible();
  });

  test("404 fallback renders for unknown route", async ({ page }) => {
    await page.goto("/no-such-route-here");
    await expect(page.getByRole("heading", { level: 1, name: "404" })).toBeVisible();
    await expect(page.getByText(/No route matches/i)).toBeVisible();
    // Post-IA-reset copy + recovery links (§7 of the URL grammar
    // handover). "This page has moved" frames the 404 for citizens who
    // followed a stale link from before the reorganisation; the topics
    // index is offered as a discovery surface alongside Home.
    //
    // Scope link assertions to the 404 page's <main>: the chrome's
    // brand wordmark also matches `name: /Home/i` via its
    // `aria-label="Yen Gov home"`, so a page-wide locator would be
    // strict-mode-ambiguous.
    const fourOhFour = page.locator("main");
    await expect(fourOhFour.getByText(/This page has moved/i)).toBeVisible();
    await expect(fourOhFour.getByRole("link", { name: /Home/i })).toBeVisible();
    await expect(fourOhFour.getByRole("link", { name: /Browse topics/i })).toHaveAttribute(
      "href",
      /\/t$/,
    );
  });

  test("party page renders for DMK in Tamil Nadu", async ({ page }) => {
    // Slug shape: <short-slug>-<eci-code-lower>. DMK is short=DMK, eci=DMK.
    await page.goto("/s/tamil-nadu/party/dmk-DMK");
    await page.waitForLoadState("networkidle", { timeout: 15_000 });
    // PR-H (Phase 1.3d): per-event alliance now rides on PartyTotals via
    // the dim_party_alliances LEFT JOIN. DMK for AcGenMay2026 surfaces
    // with alliance=SPA — the citizen-visible coverage improvement (this
    // line never rendered before PR-H). Recognition is NOT asserted: the
    // taxonomy/parties.json seed currently leaves `recognition` unset on
    // every entry, so `dim_parties.recognition` is uniformly NULL today;
    // populating it is a content-only follow-up.
    const meta = page.locator("header p.text-sm");
    await expect(meta).toContainText(/alliance: SPA/);
  });

  test("psephlab loads actuals for tamil-nadu / AcGenMay2026", async ({ page }) => {
    await page.goto("/lab/tamil-nadu/AcGenMay2026");
    await page.waitForLoadState("networkidle", { timeout: 30_000 });
    // Engine produces some seat-count text; we just confirm the route is
    // alive enough to have rendered something other than a blank shell.
    await expect(page.locator("main").first()).toBeVisible();
  });

  test("compare surface loads for tamil-nadu / AcGenMay2026", async ({ page }) => {
    await page.goto("/compare/tamil-nadu/AcGenMay2026");
    await page.waitForLoadState("networkidle", { timeout: 30_000 });
    await expect(page.locator("main").first()).toBeVisible();
  });

  // Phase 1.3b — icon rollout sub-1 (topic cards).
  //
  // /t mounts TopicIndex.svelte. Each topic card now carries a TopicIcon
  // glyph next to the title, sourced from the build-time icon registry
  // (virtual:icon-registry). The contract test in
  // src/lib/TopicIcon.test.ts already asserts that every topic.icon
  // referenced in datasets/taxonomy/topics.json has a registry entry —
  // this smoke proves the registry's data ACTUALLY renders into the DOM
  // at the citizen surface, and that the renderer doesn't trip on the
  // structural icon shape (recursive `{@render}` snippet).
  test("topic index /t renders TopicIcon glyphs on every topic card", async ({ page }) => {
    await page.goto("/t");
    await expect(page.getByRole("heading", { level: 1, name: "Topics" })).toBeVisible({
      timeout: 15_000,
    });
    // The 10 topic.icon refs in topics.json (with duplicates: users x2,
    // trending-up x2) emit 10 SVGs tagged `data-icon-name=<id>`. We
    // assert ≥8 to leave headroom if the taxonomy adds a topic-without-icon
    // before the test is rebaselined.
    const icons = page.locator("svg[data-icon-name]");
    const count = await icons.count();
    expect(count, "TopicIndex should render at least one icon per topic card").toBeGreaterThanOrEqual(8);
    // At least one of each shipped icon id should be present (proves the
    // virtual registry is loaded, not just one icon hardcoded).
    const seen = await icons.evaluateAll((els) =>
      Array.from(new Set(els.map((e) => e.getAttribute("data-icon-name")))).sort(),
    );
    expect(seen).toContain("landmark"); // governance
    expect(seen).toContain("zap");      // energy
    expect(seen).toContain("vote");     // elections
    expect(seen).toContain("users");    // demography / human dev
  });

  // Phase 1.3c — icon rollout sub-2 (topic landings).
  //
  // /t/<topic>            → TopicLanding.svelte (1.3c part A)
  // /s/<state>/t/<topic>  → StateTopic.svelte    (1.3c part B)
  // Each surface inherits the visual identity the citizen tapped on the
  // /t index — the icon prefixes the `<h1>` topic title.
  test("topic landing /t/fiscal renders TopicIcon in <h1>", async ({ page }) => {
    await page.goto("/t/fiscal");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    const h1Icon = page.locator('h1 svg[data-icon-name]').first();
    await expect(h1Icon).toHaveAttribute("data-icon-name", "landmark");
  });

  test("state topic /s/tamil-nadu/t/energy renders TopicIcon in <h1>", async ({ page }) => {
    await page.goto("/s/tamil-nadu/t/energy");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    const h1Icon = page.locator('h1 svg[data-icon-name]').first();
    await expect(h1Icon).toHaveAttribute("data-icon-name", "zap");
  });

  // Phase 1.3d — icon rollout sub-3 (indicator cards).
  //
  // State hub `/s/<state>` renders IndicatorCard.svelte for every
  // catalogued artifact across every topic — typically ≥80 cards. Each
  // card's `<h3>` is now prefixed with the indicator's `meta.icon`
  // (silent on miss). The smoke asserts ≥20 distinct cards carry an
  // icon glyph; this is well under the 83 observed in dev (Tamil Nadu)
  // but high enough to prove the wiring, while leaving headroom for the
  // taxonomy author to remove indicators without forcing this test to
  // be rebaselined.
  test("state hub /s/tamil-nadu renders TopicIcon on IndicatorCard headers", async ({ page }) => {
    await page.goto("/s/tamil-nadu");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    // IndicatorCards load via fetchIndicator() — wait for the first
    // sparkline path (proxy for "≥1 card has data").
    await page.waitForSelector("svg[data-icon-name]", { timeout: 20_000 });
    await page.waitForTimeout(3000); // allow more cards to settle in
    const icons = page.locator("h3 svg[data-icon-name]");
    const count = await icons.count();
    expect(count, "≥20 IndicatorCards should render an icon on /s/tamil-nadu").toBeGreaterThanOrEqual(20);
    const seen = await icons.evaluateAll((els) =>
      Array.from(new Set(els.map((e) => e.getAttribute("data-icon-name")))).sort(),
    );
    // At minimum the fiscal corpus should produce these.
    expect(seen).toContain("landmark");
    expect(seen).toContain("trending-down");
  });

  // Phase 1.3e — icon rollout sub-4 (chart headers).
  //
  // Topic landing /t/<topic> renders IndicatorChoropleth (when an
  // artifact's `presentation_id === "indicator-choropleth"`),
  // IndicatorRanked, and IndicatorSmallMultiples for every catalogued
  // indicator. Each chart's `<h3>` is now prefixed with the indicator's
  // `meta.icon`. The IndicatorChoropleth header was already wiring the
  // legacy `IndicatorIcon` (hardcoded component-local REGISTRY) — this
  // phase swaps that callsite to `TopicIcon` backed by the build-time
  // virtual:icon-registry, unifying with the rest of the rollout.
  //
  // The smoke loads /t/fiscal (every indicator carries icon=landmark in
  // taxonomy) and asserts ≥30 chart headers render with the landmark
  // glyph. Each fiscal indicator emits three headers (choropleth,
  // ranked, small-multiples), so 10+ fiscal indicators → ≥30 icons.
  test("topic landing /t/fiscal renders TopicIcon on chart headers", async ({ page }) => {
    await page.goto("/t/fiscal");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    // Wait for at least one chart header icon (proxy for "≥1 artifact
    // has streamed in and rendered its h3").
    await page.waitForSelector('h3 svg[data-icon-name="landmark"]', { timeout: 25_000 });
    await page.waitForTimeout(3500); // settle in for ranked + small-multiples
    const icons = page.locator("h3 svg[data-icon-name]");
    const total = await icons.count();
    expect(total, "≥30 chart headers should render an icon on /t/fiscal").toBeGreaterThanOrEqual(30);
    const seen = await icons.evaluateAll((els) =>
      Array.from(new Set(els.map((e) => e.getAttribute("data-icon-name")))).sort(),
    );
    // Fiscal corpus → every artifact carries icon=landmark.
    expect(seen).toContain("landmark");
  });

  test("topic landing /t/energy renders TopicIcon on chart headers across multiple ids", async ({ page }) => {
    await page.goto("/t/energy");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    await page.waitForSelector("h3 svg[data-icon-name]", { timeout: 25_000 });
    await page.waitForTimeout(3500);
    const icons = page.locator("h3 svg[data-icon-name]");
    const total = await icons.count();
    // PR #296 (Row 4 IA pass) pruned /t/energy from 23 cards to 5
    // survivors. Live count post-prune (with Fix 3 Zod fix unmasking
    // true render) = 7 icons. Threshold set to 5 with headroom for
    // future re-additions before this test needs re-tuning.
    expect(total, "≥5 chart headers should render an icon on /t/energy (post PR #296 prune)").toBeGreaterThanOrEqual(5);
    const seen = await icons.evaluateAll((els) =>
      Array.from(new Set(els.map((e) => e.getAttribute("data-icon-name")))).sort(),
    );
    // Post-PR #296 (Row 4 IA pass): surviving /t/energy cards expose
    // `activity` + `zap` icons. The `flame` icon was sourced from the
    // retired thermal cards (installed_capacity_thermal_mw etc.) and is
    // no longer present. Broader icon-presence intent is covered by the
    // count threshold + the `zap` assertion below.
    expect(seen).toContain("zap");
  });

  // Phase 1.3f — icon rollout sub-5 (state-hub chips + leaf pages + chrome).
  //
  // Final wave of the icon-rollout series. Covers:
  //   1. State hub section chips (h2 per topic on /s/<state>) — wires
  //      `topic.icon` against the same TopicIcon registry already proven
  //      on TopicIndex / TopicLanding (1.3b–1.3c).
  //   2. Identity icons on the 10 chrome / leaf routes: Constituency,
  //      Party, Compare (state event), CompareIndicator (generic), Psephlab,
  //      Explore, About, Disclaimer, Settings, DataCompleteness. Each h1
  //      now flexes a 6×6 (or 7×7 for the lighter About/Disclaimer)
  //      slate icon.
  //
  // Plan calls for one Playwright smoke on an election surface and one
  // on a chrome surface. We pin /lab/tamil-nadu/ae-2021 (Psephlab,
  // dynamic h1 + named ECI election) and /about (static h1, copy-only)
  // to cover the two ends of the chrome spectrum.
  test("state hub /s/tamil-nadu renders TopicIcon on section chips", async ({ page }) => {
    await page.goto("/s/tamil-nadu");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    // Section chips come from catalogue.topics → render synchronously
    // with the page (no fetch). Wait briefly to allow the catalogue
    // store to settle if it hasn't already.
    await page.waitForSelector('h2 svg[data-icon-name]', { timeout: 15_000 });
    const chipIcons = page.locator('h2 svg[data-icon-name]');
    const count = await chipIcons.count();
    expect(count, "≥5 section chips should render an icon on /s/tamil-nadu").toBeGreaterThanOrEqual(5);
    const seen = await chipIcons.evaluateAll((els) =>
      Array.from(new Set(els.map((e) => e.getAttribute("data-icon-name")))).sort(),
    );
    // The Tamil Nadu state hub always shows fiscal + energy at minimum.
    expect(seen).toContain("landmark");
    expect(seen).toContain("zap");
  });

  test("election surface /lab/tamil-nadu/ae-2021 renders flask identity icon", async ({ page }) => {
    await page.goto("/lab/tamil-nadu/ae-2021");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    const flask = page.locator('h1 svg[data-icon-name="flask"]').first();
    await expect(flask).toHaveAttribute("data-icon-name", "flask");
  });

  test("chrome surface /about renders info identity icon", async ({ page }) => {
    await page.goto("/about");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    const info = page.locator('h1 svg[data-icon-name="info"]').first();
    await expect(info).toHaveAttribute("data-icon-name", "info");
  });

  // ------------------------------------------------------------------
  // Phase 1.4 — SourceList v2 caller migration
  // ------------------------------------------------------------------
  //
  // PR-27 swaps the StateOverview totals-card footer from the legacy
  // SourceList (which consumed SourceRef with `url` + `fetched_at`) to
  // SourceListV2 (which consumes the full v2.0 ledger row from
  // taxonomy.sources per ADR-0032). The render contract:
  //
  //   • The v2 root mounts with `data-component="source-list-v2"`.
  //   • The triangle disclosure is closed by default; the collapsed
  //     line shows "Sources (N)" exactly like v1 (so the existing
  //     `SOURCE_LIST_TEXT` regex in golden-path remains green).
  //   • Once expanded, each row carries `data-confidence-tier` (one of
  //     gold / silver / bronze) and `data-verification-method` (one of
  //     live-fetch / archived-snapshot / transcribed / editorial).
  //
  // R-24 — no fetch-telemetry fields appear in the expanded panel. The
  // contract test `frontend/src/contracts/sources-v2-shape.test.ts`
  // covers the type-system seam; this spec is the citizen-surface seam.

  test("state hub /s/tamil-nadu mounts SourceListV2 with citizen-visible trust signals", async ({ page }) => {
    await page.goto("/s/tamil-nadu");

    const footer = page
      .locator('[data-testid="state-summary-sources"] [data-component="source-list-v2"]')
      .first();
    await expect(footer).toBeAttached({ timeout: 45_000 });
    // Collapsed "Sources (N)" label preserved verbatim from v1.
    await expect(footer.getByText(/Sources \(\d+\)/).first()).toBeVisible({ timeout: 45_000 });

    // Open the disclosure. The button is the only <button> child of the
    // v2 root — the rest of the panel is plain text + anchors.
    await footer.locator("button").first().click();

    // At least one expanded row must carry the v2.0 trust signals as
    // data attributes. These are the citizen-visible structured surfaces
    // SourceListV2 ships, and they're proof the loader-side v2 projection
    // reached the DOM end-to-end.
    const firstRow = footer.locator("[data-confidence-tier]").first();
    await expect(firstRow).toBeVisible({ timeout: 45_000 });
    const tier = await firstRow.getAttribute("data-confidence-tier");
    expect(["gold", "silver", "bronze"]).toContain(tier);

    const method = await firstRow.getAttribute("data-verification-method");
    expect(["live-fetch", "archived-snapshot", "transcribed", "editorial"])
      .toContain(method);
  });
});
