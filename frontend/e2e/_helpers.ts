// Shared Playwright helpers.
//
// Why a shared `pageerror` listener: every spec needs one, and forgetting
// it is the #1 way a "passing" test silently regresses (the page renders
// but the runtime threw). Calling `attachPageErrorTrap(page)` at the top
// of each test attaches the listener and returns a getter that the test
// asserts on at the end.
//
// Accessibility scanning is intentionally absent here — it is a
// project-level non-goal per CLAUDE.md §0.

import type { Page } from "@playwright/test";

/**
 * Attach a `pageerror` + `console error` trap to a page. Returns a
 * `getErrors()` thunk that snapshots the accumulated errors at call time.
 * Callers should `expect(getErrors(), ...).toEqual([])` near the end.
 *
 * We capture both `pageerror` (uncaught exceptions) and `console.error`
 * because some Svelte runtime errors only surface as `console.error`
 * without throwing (effects that swallow rejections). 404 fetch responses
 * surface as `requestfailed`; we capture those too — but only for paths
 * the frontend actually owns (`/data/...` etc.), so a third-party 404
 * (favicon, etc.) doesn't fail the test.
 */
export function attachPageErrorTrap(page: Page): { getErrors: () => string[] } {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(`[pageerror] ${e.message}`));
  page.on("console", msg => {
    if (msg.type() === "error") {
      const text = msg.text();
      // Filter out maplibre-gl's "AbortError" on rapid navigation — it's a
      // teardown race, not a regression.
      if (text.includes("AbortError")) return;
      // Filter out the browser's automatic "Failed to load resource:
      // ... 404 (Not Found)" console line. These are graceful-degradation
      // 404s (loaders return null on missing artifacts, ADR-0014). The
      // app intentionally probes URLs that may or may not exist; counting
      // them as errors would punish the 404-as-null contract. Genuine
      // network failures still surface via the `requestfailed` listener
      // for `/data/...` paths below.
      if (text.includes("Failed to load resource")) return;
      errors.push(`[console.error] ${text}`);
    }
  });
  page.on("requestfailed", req => {
    const url = req.url();
    // Only count failures for our own data tier; ignore third-party
    // (e.g. fonts, telemetry) which the test environment doesn't control.
    if (/\/data\//.test(url)) {
      errors.push(`[requestfailed] ${req.method()} ${url} — ${req.failure()?.errorText ?? "?"}`);
    }
  });
  return { getErrors: () => errors.slice() };
}

/** A minimum heading the SourceList component renders ("Sources (N)"). */
export const SOURCE_LIST_TEXT = /Sources \(\d+\)/;
