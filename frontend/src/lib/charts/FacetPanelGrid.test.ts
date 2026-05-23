import { describe, expect, it } from "vitest";

import {
  buildFacetPanelGridViewModel,
  type FacetPanelGridViewModel,
} from "./multi-dim-view-models";

// Renderer contract for FacetPanelGrid.svelte. Component-level DOM
// assertions are deferred to Playwright (vitest = node-env, no jsdom).

interface CellRow {
  panel_id: string;
  panel_label: string;
  panel_order: number;
  id: string;
  label: string;
  pinned?: boolean;
  value: number | null;
}

// Three states, each with three indicators. KL has one missing.
const FIXTURE: readonly CellRow[] = [
  // Karnataka
  { panel_id: "KA", panel_label: "Karnataka",   panel_order: 0, id: "lit", label: "Literacy",  value: 75 },
  { panel_id: "KA", panel_label: "Karnataka",   panel_order: 0, id: "ele", label: "Electrified", value: 90 },
  { panel_id: "KA", panel_label: "Karnataka",   panel_order: 0, id: "imr", label: "IMR",       value: 30 },
  // Tamil Nadu — pinned
  { panel_id: "TN", panel_label: "Tamil Nadu",  panel_order: 1, id: "lit", label: "Literacy",  pinned: true, value: 80 },
  { panel_id: "TN", panel_label: "Tamil Nadu",  panel_order: 1, id: "ele", label: "Electrified", pinned: true, value: 95 },
  { panel_id: "TN", panel_label: "Tamil Nadu",  panel_order: 1, id: "imr", label: "IMR",       pinned: true, value: 25 },
  // Kerala — IMR missing
  { panel_id: "KL", panel_label: "Kerala",      panel_order: 2, id: "lit", label: "Literacy",  value: 94 },
  { panel_id: "KL", panel_label: "Kerala",      panel_order: 2, id: "ele", label: "Electrified", value: 99 },
  { panel_id: "KL", panel_label: "Kerala",      panel_order: 2, id: "imr", label: "IMR",       value: null },
];

function buildVM(
  panel_policy: "value_desc" | "axis_order" | "alphabetical" = "value_desc",
  shared_scale = true,
): FacetPanelGridViewModel<CellRow> {
  return buildFacetPanelGridViewModel({
    rows: FIXTURE,
    toPanelRow: r => ({
      panel_id: r.panel_id,
      panel_label: r.panel_label,
      panel_order: r.panel_order,
      id: r.id,
      label: r.label,
      pinned_rank: r.pinned ? 0 : null,
      value: r.value,
    }),
    row_policy: "value_desc",
    panel_policy,
    shared_scale,
  });
}

describe("FacetPanelGrid renderer contract", () => {
  it("emits one panel per unique panel_id", () => {
    const vm = buildVM();
    expect(vm.panels.length).toBe(3);
    expect(vm.panels.map(p => p.panel_id).sort()).toEqual(["KA", "KL", "TN"]);
  });

  it("each panel carries its own max_abs_value", () => {
    const vm = buildVM();
    const ka = vm.panels.find(p => p.panel_id === "KA")!;
    const kl = vm.panels.find(p => p.panel_id === "KL")!;
    expect(ka.max_abs_value).toBe(90);
    expect(kl.max_abs_value).toBe(99);
  });

  it("shared_scale echoes through + global_max_abs_value is the largest", () => {
    const vm = buildVM("value_desc", true);
    expect(vm.shared_scale).toBe(true);
    expect(vm.global_max_abs_value).toBe(99); // KL Electrified
  });

  it("shared_scale=false echoes through", () => {
    const vm = buildVM("value_desc", false);
    expect(vm.shared_scale).toBe(false);
  });

  it("missing cell stays in the panel (visible)", () => {
    const vm = buildVM();
    const kl = vm.panels.find(p => p.panel_id === "KL")!;
    expect(kl.rows.find(r => r.id === "imr")?.is_missing).toBe(true);
    expect(kl.missing_count).toBeGreaterThanOrEqual(1);
  });

  it("axis_order panel policy preserves input order", () => {
    const vm = buildVM("axis_order");
    expect(vm.panels.map(p => p.panel_id)).toEqual(["KA", "TN", "KL"]);
  });

  it("alphabetical panel policy sorts by label", () => {
    const vm = buildVM("alphabetical");
    expect(vm.panels.map(p => p.panel_label)).toEqual([
      "Karnataka",
      "Kerala",
      "Tamil Nadu",
    ]);
  });
});
