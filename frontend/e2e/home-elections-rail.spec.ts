// home-elections-rail.spec.ts (PR-W4d, 2026-06-10)
//
// Playwright smoke for the 3-card elections rail mounted on Home (`/`).
// Confirms: anchor + hook + door render with non-empty content + working
// hrefs; the anchor card routes to /t/elections/<event>; the door card
// routes to /t/elections.
//
// The hook card href changes per-state when the data ingest updates, so
// we assert it matches the generic /<state>/elections/<event> shape
// rather than a fixed slug.

import { expect, test } from "@playwright/test";

test.describe("Home elections rail (PR-W4d)", () => {
  test("renders 3 cards with non-empty content and routes correctly", async ({ page }) => {
    const failedRequests: string[] = [];
    page.on("requestfailed", (req) => {
      failedRequests.push(`${req.method()} ${req.url()} - ${req.failure()?.errorText ?? "unknown"}`);
    });
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto("/");

    // Wait for the rail to mount (it loads lazily via fetchElectionEvents +
    // loadElectionResults). The loading skeleton sits in for it until then.
    const rail = page.getByTestId("home-elections-rail");
    await rail.waitFor({ state: "visible", timeout: 15_000 });

    const anchor = page.getByTestId("rail-anchor");
    const hook = page.getByTestId("rail-hook");
    const door = page.getByTestId("rail-door");

    await expect(anchor).toBeVisible();
    await expect(hook).toBeVisible();
    await expect(door).toBeVisible();

    // Anchor: title shape "Parliament <year>" + subtitle "National results".
    const anchorText = (await anchor.innerText()).trim();
    expect(anchorText).toMatch(/Parliament \d{4}/);
    expect(anchorText).toContain("National results");
    const anchorHref = await anchor.getAttribute("href");
    expect(anchorHref).toMatch(/^\/t\/elections\/[a-z0-9-]+$/);

    // Hook: title contains "closest seat" OR degrades to "Parliament <year>".
    // Subtitle non-empty in both arms.
    const hookText = (await hook.innerText()).trim();
    expect(hookText.length).toBeGreaterThan(20);
    const hookHref = await hook.getAttribute("href");
    // Either /<state>/elections/<event> (closest race) OR /t/elections/<event> (degraded).
    expect(hookHref).toMatch(/^\/([a-z0-9-]+\/elections\/[a-z0-9-]+|t\/elections\/[a-z0-9-]+)$/);

    // Door: routes to firehose.
    await expect(door).toContainText(/All elections/);
    expect(await door.getAttribute("href")).toBe("/t/elections");

    // No console errors + no failed requests during the rail mount.
    expect(consoleErrors, `Console errors:\n${consoleErrors.join("\n")}`).toEqual([]);
    expect(failedRequests, `Failed requests:\n${failedRequests.join("\n")}`).toEqual([]);
  });

  test("anchor card navigates to the national event view", async ({ page }) => {
    await page.goto("/");
    const anchor = page.getByTestId("rail-anchor");
    await anchor.waitFor({ state: "visible", timeout: 15_000 });
    const href = await anchor.getAttribute("href");
    expect(href).toBeTruthy();

    await Promise.all([
      page.waitForURL(/\/t\/elections\/[a-z0-9-]+$/, { timeout: 10_000 }),
      anchor.click(),
    ]);
    // Landed on /t/elections/<event>. The NationalElection.svelte route
    // owns its own smoke spec; here we only assert the URL transition.
    expect(page.url()).toMatch(/\/t\/elections\/[a-z0-9-]+$/);
  });

  test("door card navigates to /t/elections firehose", async ({ page }) => {
    await page.goto("/");
    const door = page.getByTestId("rail-door");
    await door.waitFor({ state: "visible", timeout: 15_000 });

    await Promise.all([
      page.waitForURL(/\/t\/elections$/, { timeout: 10_000 }),
      door.click(),
    ]);
    expect(page.url()).toMatch(/\/t\/elections$/);
  });
});
