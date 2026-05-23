// Vitest — pure footer-action helpers for ChartShell.
//
// These cases nail down the Phase 1.4 contract test
// "action footer does not render unapproved controls" at the helper
// boundary so the Svelte renderer can trust its input and the
// Playwright lane only has to cover the rendered shape, not the
// vocabulary policy.

import { describe, expect, it } from "vitest";

import {
  ALLOWED_ACTIONS,
  filterAllowedActions,
  sortActionsForFooter,
} from "./actions";
import type {
  ChartShellAction,
  ChartShellActionSpec,
} from "./types";

const NOOP = () => {};

function spec(
  id: ChartShellAction | string,
  label: string,
): ChartShellActionSpec {
  // cast through unknown so the test fixture can express invalid ids
  // for the negative cases without TypeScript blocking them at authoring.
  return { id: id as ChartShellAction, label, on_invoke: NOOP };
}

describe("ALLOWED_ACTIONS", () => {
  it("is frozen at runtime", () => {
    expect(Object.isFrozen(ALLOWED_ACTIONS)).toBe(true);
  });

  it("contains exactly the 6 Phase-1.4-approved ids in canonical order", () => {
    expect([...ALLOWED_ACTIONS]).toEqual([
      "view_data",
      "download",
      "copy_link",
      "share",
      "reset_view",
      "full_range",
    ]);
  });

  it("has no duplicate ids", () => {
    const unique = new Set(ALLOWED_ACTIONS);
    expect(unique.size).toBe(ALLOWED_ACTIONS.length);
  });
});

describe("filterAllowedActions", () => {
  it("returns an empty list when given no actions", () => {
    expect(filterAllowedActions([])).toEqual([]);
  });

  it("keeps every spec whose id is on the approved list", () => {
    const specs: ChartShellActionSpec[] = [
      spec("view_data", "View data"),
      spec("download", "Download SVG"),
      spec("copy_link", "Copy link"),
      spec("share", "Share"),
      spec("reset_view", "Reset"),
      spec("full_range", "Full range"),
    ];
    const out = filterAllowedActions(specs);
    expect(out.map(s => s.id)).toEqual([
      "view_data",
      "download",
      "copy_link",
      "share",
      "reset_view",
      "full_range",
    ]);
  });

  it("drops any spec whose id is not on the approved list", () => {
    const specs: ChartShellActionSpec[] = [
      spec("view_data", "View data"),
      spec("export_to_postscript", "PostScript"),
      spec("download", "Download"),
      spec("legend_collapse", "Hide legend"),
      spec("zoom_in", "Zoom in"),
    ];
    const out = filterAllowedActions(specs);
    expect(out.map(s => s.id)).toEqual(["view_data", "download"]);
  });

  it("preserves caller-supplied order across approved specs", () => {
    const specs: ChartShellActionSpec[] = [
      spec("download", "Download"),
      spec("view_data", "View"),
      spec("share", "Share"),
    ];
    const out = filterAllowedActions(specs);
    expect(out.map(s => s.id)).toEqual(["download", "view_data", "share"]);
  });

  it("does not mutate the input array", () => {
    const specs: ChartShellActionSpec[] = [
      spec("view_data", "View"),
      spec("not_approved", "Bad"),
    ];
    const snapshot = [...specs];
    filterAllowedActions(specs);
    expect(specs).toEqual(snapshot);
  });
});

describe("sortActionsForFooter", () => {
  it("returns an empty list when given no actions", () => {
    expect(sortActionsForFooter([])).toEqual([]);
  });

  it("sorts approved actions into the canonical footer order", () => {
    const specs: ChartShellActionSpec[] = [
      spec("full_range", "Full"),
      spec("download", "Download"),
      spec("view_data", "View"),
      spec("reset_view", "Reset"),
      spec("share", "Share"),
      spec("copy_link", "Copy"),
    ];
    const out = sortActionsForFooter(specs);
    expect(out.map(s => s.id)).toEqual([
      "view_data",
      "download",
      "copy_link",
      "share",
      "reset_view",
      "full_range",
    ]);
  });

  it("is stable for equal ranks (preserves input order for duplicates)", () => {
    // Renderer of the future may emit two `download` specs (SVG + CSV).
    // Stable sort keeps the view-model's intended ordering.
    const specs: ChartShellActionSpec[] = [
      spec("download", "Download SVG"),
      spec("download", "Download CSV"),
      spec("view_data", "View"),
    ];
    const out = sortActionsForFooter(specs);
    expect(out.map(s => s.label)).toEqual([
      "View",
      "Download SVG",
      "Download CSV",
    ]);
  });

  it("pushes unknown ids to the end in stable insertion order", () => {
    // Defence-in-depth: even if filterAllowedActions is skipped, the
    // sort never silently reorders unknowns against each other.
    const specs: ChartShellActionSpec[] = [
      spec("download", "Download"),
      spec("zoom_in", "Zoom"),
      spec("view_data", "View"),
      spec("pan", "Pan"),
    ];
    const out = sortActionsForFooter(specs);
    expect(out.map(s => s.id)).toEqual([
      "view_data",
      "download",
      "zoom_in",
      "pan",
    ]);
  });

  it("does not mutate the input array", () => {
    const specs: ChartShellActionSpec[] = [
      spec("full_range", "Full"),
      spec("view_data", "View"),
    ];
    const snapshot = [...specs];
    sortActionsForFooter(specs);
    expect(specs).toEqual(snapshot);
  });
});

describe("filterAllowedActions + sortActionsForFooter composition", () => {
  it("filters then sorts in canonical order, preserving labels", () => {
    const specs: ChartShellActionSpec[] = [
      spec("download", "Download"),
      spec("export_to_postscript", "PostScript"),
      spec("view_data", "View"),
      spec("zoom_in", "Zoom"),
      spec("full_range", "Full range"),
    ];
    const out = sortActionsForFooter(filterAllowedActions(specs));
    expect(out.map(s => s.id)).toEqual([
      "view_data",
      "download",
      "full_range",
    ]);
    expect(out.map(s => s.label)).toEqual([
      "View",
      "Download",
      "Full range",
    ]);
  });
});
