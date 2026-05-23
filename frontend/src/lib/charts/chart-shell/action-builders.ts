// ChartShell — concrete action-builder factories.
//
// Per docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md Phase 1.4
// task 4 ("Add footer action slots for `view_data`, `download`,
// `copy_link/share`, `reset_view`, and `full_range`; actions appear
// only when the view-model says they are useful").
//
// The renderer (`frontend/src/lib/charts/ChartShell.svelte`) accepts
// `actions: readonly ChartShellActionSpec[]`; the closed enum is
// enforced upstream by `filterAllowedActions`. This module supplies
// pure factory functions a view-model can compose to produce the
// specs — keeping the per-action plumbing (clipboard, CSV blob, SVG
// blob) out of every adopter.
//
// Why factories not class instances: each spec is a one-shot value
// the renderer reads on mount; there is no shared state to hold.
// Factories also make the unit-test surface trivially small (call
// the factory, then call `spec.on_invoke()` and assert the side
// effect on a stub).
//
// Doctrine ties:
//
//   - R-08 BBA. These helpers do NOT touch existing renderers. The
//     adopter (CompositionBar mount in `StateOverview.svelte` PR-32)
//     opts in by passing the returned spec into the `actions` prop.
//
//   - R-24 zero fetch telemetry. Clipboard / CSV / SVG blob handlers
//     write to the citizen's machine; no upstream calls, no
//     analytics, no third-party endpoints.
//
//   - CLAUDE.md §0 a11y descoped. Buttons are real `<button>` with
//     visible labels supplied by the factory caller; no aria-* here.

import type { ChartShellActionSpec } from "./types";

/**
 * Outcome of a `copy_link` invocation. Returned by the side-effect
 * helpers so callers can show optimistic feedback ("Link copied")
 * without re-implementing clipboard plumbing.
 */
export interface CopyLinkResult {
  readonly ok: boolean;
  readonly href: string;
  readonly fallback_used: boolean;
}

/**
 * Copy a URL to the system clipboard. Tries the async Clipboard API
 * first (Chromium / Firefox / Safari 13.4+); falls back to a
 * `document.execCommand("copy")` shim for legacy browsers AND for
 * non-secure contexts where `navigator.clipboard` is undefined.
 *
 * The fallback uses a hidden `<textarea>` per the WHATWG-blessed
 * pattern; it leaves no DOM trace after the operation completes.
 *
 * Returns `{ ok, href, fallback_used }` so the caller can render
 * citizen feedback (a toast / aria-live region) without owning the
 * clipboard plumbing.
 */
export async function copyToClipboard(href: string): Promise<CopyLinkResult> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(href);
      return { ok: true, href, fallback_used: false };
    } catch {
      // Fall through to execCommand fallback. Most common path here is
      // a permissions denial in a non-secure context (http: site or
      // permissions-policy block). Browsers throw here rather than
      // returning a rejected promise consistently — both arms handled.
    }
  }
  return copyToClipboardLegacy(href);
}

function copyToClipboardLegacy(href: string): CopyLinkResult {
  if (typeof document === "undefined") {
    return { ok: false, href, fallback_used: true };
  }
  const ta = document.createElement("textarea");
  ta.value = href;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.top = "0";
  ta.style.left = "0";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    ok = false;
  } finally {
    document.body.removeChild(ta);
  }
  return { ok, href, fallback_used: true };
}

/**
 * Build a `copy_link` action spec that copies the current
 * `window.location.href` to the clipboard. Optional `on_result`
 * callback fires after the clipboard write so the caller can update
 * citizen-visible feedback.
 *
 * Defaults: label "Copy link". Caller can override.
 */
export interface CopyLinkSpecOptions {
  readonly label?: string;
  readonly resolve_href?: () => string;
  readonly on_result?: (result: CopyLinkResult) => void;
}

export function buildCopyLinkActionSpec(
  opts: CopyLinkSpecOptions = {},
): ChartShellActionSpec {
  return {
    id: "copy_link",
    label: opts.label ?? "Copy link",
    on_invoke: () => {
      const href = opts.resolve_href
        ? opts.resolve_href()
        : typeof window !== "undefined"
          ? window.location.href
          : "";
      // Fire-and-forget; the renderer's onclick is sync but the
      // clipboard API is async — the result callback bridges back to
      // the caller for citizen feedback.
      void copyToClipboard(href).then(r => opts.on_result?.(r));
    },
  };
}

/**
 * Pure CSV serialiser. Quotes any cell containing `,`, `"`, newline,
 * or carriage-return per RFC 4180 §2 rule 6. Doubles embedded `"`.
 * Cells are coerced via `String(...)`; `null` and `undefined` become
 * an empty cell.
 *
 * Returns a single string with `\r\n` line terminators (RFC 4180
 * §2 rule 1). Exported for vitest; consumed by `buildViewDataActionSpec`.
 */
export function toCsv(
  header: readonly string[],
  rows: readonly (readonly unknown[])[],
): string {
  const lines: string[] = [];
  lines.push(header.map(formatCsvCell).join(","));
  for (const row of rows) {
    lines.push(row.map(formatCsvCell).join(","));
  }
  return lines.join("\r\n");
}

function formatCsvCell(value: unknown): string {
  if (value == null) return "";
  const s = String(value);
  if (/[,"\r\n]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

/**
 * Trigger a browser-side download of `content` as a file named
 * `filename`. Uses the standard `Blob` + `URL.createObjectURL` +
 * hidden `<a>.click()` + `URL.revokeObjectURL` pattern. Mirrors
 * `downloadSvg()` in `frontend/src/lib/charts/StackedTrendV2.svelte`
 * (PR-19 Phase 2.7 reference implementation).
 *
 * Pure-ish: requires `document` / `URL` / `Blob`. SSR-safe (becomes
 * a no-op when `document` is undefined).
 */
export function triggerBrowserDownload(
  content: string,
  filename: string,
  mime: string,
): boolean {
  if (typeof document === "undefined" || typeof URL === "undefined") {
    return false;
  }
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  // Style off-screen so the click doesn't flash a focus ring.
  a.style.position = "fixed";
  a.style.top = "0";
  a.style.left = "0";
  a.style.opacity = "0";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  return true;
}

/**
 * Build a `view_data` action spec. The first-cut implementation
 * triggers a CSV download of the currently-visible rows; the plan
 * (line ~1080) reserves the right to swap this for an inline table
 * disclosure in a follow-up PR — the spec contract stays the same.
 *
 * Caller supplies:
 *
 *   - `resolve_rows()`  returning `{header, rows}` at click time so the
 *                       latest visible window is captured (NOT the
 *                       whole corpus — plan rule).
 *   - `filename`        the download filename (caller-controlled so the
 *                       slug includes route / state / event ids).
 *   - `label?`          defaults to "View data".
 */
export interface ViewDataSpecOptions {
  readonly resolve_rows: () => {
    readonly header: readonly string[];
    readonly rows: readonly (readonly unknown[])[];
  };
  readonly filename: string;
  readonly label?: string;
  readonly on_result?: (ok: boolean) => void;
}

export function buildViewDataActionSpec(
  opts: ViewDataSpecOptions,
): ChartShellActionSpec {
  return {
    id: "view_data",
    label: opts.label ?? "View data",
    on_invoke: () => {
      const { header, rows } = opts.resolve_rows();
      const csv = toCsv(header, rows);
      const ok = triggerBrowserDownload(
        csv,
        opts.filename,
        "text/csv;charset=utf-8",
      );
      opts.on_result?.(ok);
    },
  };
}
