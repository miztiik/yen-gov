import { describe, expect, it } from "vitest";

import {
  buildFacetPanelGridViewModel,
  buildHorizontalGroupedBarViewModel,
} from "./builders";

// ─── grouped bar ───────────────────────────────────────────────────

describe("buildHorizontalGroupedBarViewModel — basics", () => {
  interface PartyResult {
    readonly party: string;
    readonly y2019: number | null;
    readonly y2024: number | null;
  }
  const ROWS: PartyResult[] = [
    { party: "INC", y2019: 52, y2024: 99 },
    { party: "BJP", y2019: 303, y2024: 240 },
    { party: "AAP", y2019: null, y2024: 3 }, // partial
    { party: "BSP", y2019: 10, y2024: null },
  ];

  it("default sum aggregator + value_desc sorts by row total", () => {
    const vm = buildHorizontalGroupedBarViewModel({
      rows: ROWS,
      toRow: (r) => ({
        id: r.party,
        label: r.party,
        cells: [
          { group_id: "y2019", group_label: "2019", value: r.y2019 },
          { group_id: "y2024", group_label: "2024", value: r.y2024 },
        ],
      }),
      policy: "value_desc",
    });
    // Totals: BJP 543, INC 151, BSP 10, AAP 3 → BJP, INC, BSP, AAP.
    expect(vm.rows.map((r) => r.id)).toEqual(["BJP", "INC", "BSP", "AAP"]);
    expect(vm.rows[0].rank).toBe(1);
    expect(vm.group_order.map((g) => g.id)).toEqual(["y2019", "y2024"]);
    expect(vm.max_cell_value).toBe(303);
    expect(vm.present_count).toBe(6); // 4 rows × 2 cols − 2 nulls
    expect(vm.missing_count).toBe(2);
  });

  it("pick_group aggregator sorts by a single year's value", () => {
    const vm = buildHorizontalGroupedBarViewModel({
      rows: ROWS,
      toRow: (r) => ({
        id: r.party,
        label: r.party,
        cells: [
          { group_id: "y2019", group_label: "2019", value: r.y2019 },
          { group_id: "y2024", group_label: "2024", value: r.y2024 },
        ],
      }),
      policy: "value_desc",
      aggregator: { kind: "pick_group", group_id: "y2024" },
    });
    // 2024 values: BJP 240, INC 99, AAP 3, BSP null → BSP last.
    expect(vm.rows.map((r) => r.id)).toEqual(["BJP", "INC", "AAP", "BSP"]);
    expect(vm.rows[3].rank).toBeNull();
  });

  it("rectangularises rows with missing groups", () => {
    interface Row {
      readonly id: string;
      readonly cells: ReadonlyArray<{ g: string; v: number }>;
    }
    const partial: Row[] = [
      { id: "a", cells: [{ g: "x", v: 1 }] },
      { id: "b", cells: [{ g: "y", v: 2 }] },
      { id: "c", cells: [{ g: "x", v: 3 }, { g: "y", v: 4 }] },
    ];
    const vm = buildHorizontalGroupedBarViewModel({
      rows: partial,
      toRow: (r) => ({
        id: r.id,
        label: r.id,
        cells: r.cells.map((c) => ({
          group_id: c.g,
          group_label: c.g.toUpperCase(),
          value: c.v,
        })),
      }),
      policy: "value_desc",
    });
    expect(vm.group_order.map((g) => g.id)).toEqual(["x", "y"]);
    // Row a should have y as null-cell.
    const a = vm.rows.find((r) => r.id === "a")!;
    expect(a.cells.map((c) => c.group_id)).toEqual(["x", "y"]);
    expect(a.cells[1].is_missing).toBe(true);
    expect(a.cells[1].value).toBeNull();
  });

  it("explicit group_order overrides natural order", () => {
    const vm = buildHorizontalGroupedBarViewModel({
      rows: ROWS,
      toRow: (r) => ({
        id: r.party,
        label: r.party,
        cells: [
          { group_id: "y2019", group_label: "2019", value: r.y2019 },
          { group_id: "y2024", group_label: "2024", value: r.y2024 },
        ],
      }),
      policy: "value_desc",
      group_order: ["y2024", "y2019"],
    });
    expect(vm.group_order.map((g) => g.id)).toEqual(["y2024", "y2019"]);
    expect(vm.rows[0].cells.map((c) => c.group_id)).toEqual(["y2024", "y2019"]);
  });

  it("pinned_then_value puts pinned rows first", () => {
    const vm = buildHorizontalGroupedBarViewModel({
      rows: ROWS,
      toRow: (r) => ({
        id: r.party,
        label: r.party,
        pinned_rank: r.party === "AAP" ? 0 : null,
        cells: [
          { group_id: "y2019", group_label: "2019", value: r.y2019 },
          { group_id: "y2024", group_label: "2024", value: r.y2024 },
        ],
      }),
      policy: "pinned_then_value",
    });
    expect(vm.rows[0].id).toBe("AAP");
    expect(vm.rows[0].is_pinned).toBe(true);
    expect(vm.rows[1].id).toBe("BJP"); // then value desc
  });

  it("show_value_label respects threshold per cell", () => {
    const vm = buildHorizontalGroupedBarViewModel({
      rows: [{ id: "x", v1: 100, v2: 3, v3: 50 } as const],
      toRow: (r) => ({
        id: r.id,
        label: r.id,
        cells: [
          { group_id: "a", group_label: "A", value: r.v1 },
          { group_id: "b", group_label: "B", value: r.v2 },
          { group_id: "c", group_label: "C", value: r.v3 },
        ],
      }),
      policy: "value_desc",
    });
    const labels = Object.fromEntries(
      vm.rows[0].cells.map((c) => [c.group_id, c.show_value_label]),
    );
    expect(labels.a).toBe(true); // 100/100
    expect(labels.b).toBe(false); // 3/100 = 0.03 < 0.05
    expect(labels.c).toBe(true); // 50/100
  });

  it("all-null row sort_value is null and ranks null", () => {
    const vm = buildHorizontalGroupedBarViewModel({
      rows: [{ id: "ghost" } as const],
      toRow: (r) => ({
        id: r.id,
        label: r.id,
        cells: [
          { group_id: "a", group_label: "A", value: null },
          { group_id: "b", group_label: "B", value: null },
        ],
      }),
      policy: "value_desc",
    });
    expect(vm.rows[0].sort_value).toBeNull();
    expect(vm.rows[0].is_missing).toBe(true);
    expect(vm.rows[0].rank).toBeNull();
  });

  it("preserves original row reference (identity)", () => {
    const vm = buildHorizontalGroupedBarViewModel({
      rows: ROWS,
      toRow: (r) => ({
        id: r.party,
        label: r.party,
        cells: [{ group_id: "g", group_label: "G", value: r.y2024 }],
      }),
      policy: "value_desc",
    });
    const bjp = vm.rows.find((r) => r.id === "BJP")!;
    expect(bjp.row).toBe(ROWS[1]);
  });

  it("empty input → empty view-model", () => {
    const vm = buildHorizontalGroupedBarViewModel<{ id: string }>({
      rows: [],
      toRow: (r) => ({
        id: r.id,
        label: r.id,
        cells: [],
      }),
      policy: "value_desc",
    });
    expect(vm.rows).toEqual([]);
    expect(vm.group_order).toEqual([]);
    expect(vm.max_cell_value).toBe(0);
  });
});

describe("buildHorizontalGroupedBarViewModel — aggregators", () => {
  const ROWS = [
    { id: "a", cells: [10, 20] },
    { id: "b", cells: [5, 50] },
  ];
  const toRow = (r: (typeof ROWS)[number]) => ({
    id: r.id,
    label: r.id,
    cells: r.cells.map((v, i) => ({
      group_id: `g${i}`,
      group_label: `G${i}`,
      value: v,
    })),
  });

  it("max aggregator", () => {
    const vm = buildHorizontalGroupedBarViewModel({
      rows: ROWS,
      toRow,
      policy: "value_desc",
      aggregator: { kind: "max" },
    });
    // b max 50 vs a max 20 → b first.
    expect(vm.rows.map((r) => r.id)).toEqual(["b", "a"]);
  });

  it("mean aggregator", () => {
    const vm = buildHorizontalGroupedBarViewModel({
      rows: ROWS,
      toRow,
      policy: "value_desc",
      aggregator: { kind: "mean" },
    });
    // a mean 15, b mean 27.5 → b first.
    expect(vm.rows.map((r) => r.id)).toEqual(["b", "a"]);
  });
});

// ─── facet panel grid ──────────────────────────────────────────────

describe("buildFacetPanelGridViewModel — basics", () => {
  interface PanelRow {
    readonly panel: string;
    readonly cat: string;
    readonly v: number | null;
  }
  const ROWS: PanelRow[] = [
    { panel: "KL", cat: "M", v: 96 },
    { panel: "KL", cat: "F", v: 92 },
    { panel: "BR", cat: "M", v: 73 },
    { panel: "BR", cat: "F", v: 51 },
    { panel: "MP", cat: "M", v: 79 },
    { panel: "MP", cat: "F", v: 60 },
  ];

  const toPanelRow = (r: PanelRow) => ({
    panel_id: r.panel,
    panel_label: r.panel,
    id: `${r.panel}-${r.cat}`,
    label: r.cat,
    value: r.v,
  });

  it("groups rows by panel and sorts panels by sum desc by default", () => {
    const vm = buildFacetPanelGridViewModel({
      rows: ROWS,
      toPanelRow,
      row_policy: "value_desc",
      panel_policy: "value_desc",
    });
    // Sums: KL 188, MP 139, BR 124 → KL, MP, BR
    expect(vm.panels.map((p) => p.panel_id)).toEqual(["KL", "MP", "BR"]);
    expect(vm.panels[0].rows.map((r) => r.id)).toEqual(["KL-M", "KL-F"]);
    expect(vm.panels[0].rows[0].rank).toBe(1);
  });

  it("shared_scale=true → label threshold uses global max", () => {
    const vm = buildFacetPanelGridViewModel({
      rows: [
        { panel: "X", cat: "a", v: 100 },
        { panel: "Y", cat: "b", v: 4 },
      ],
      toPanelRow,
      row_policy: "value_desc",
      panel_policy: "value_desc",
    });
    // global max = 100; threshold default 0.05 → 5. Y's 4 < 5 → no label.
    const y = vm.panels.find((p) => p.panel_id === "Y")!;
    expect(y.rows[0].show_value_label).toBe(false);
    expect(vm.global_max_abs_value).toBe(100);
    expect(vm.shared_scale).toBe(true);
  });

  it("shared_scale=false → labels use panel-local max", () => {
    const vm = buildFacetPanelGridViewModel({
      rows: [
        { panel: "X", cat: "a", v: 100 },
        { panel: "Y", cat: "b", v: 4 },
      ],
      toPanelRow,
      row_policy: "value_desc",
      panel_policy: "value_desc",
      shared_scale: false,
    });
    const y = vm.panels.find((p) => p.panel_id === "Y")!;
    // Y's own max is 4, so its bar IS the max — label shows.
    expect(y.rows[0].show_value_label).toBe(true);
    expect(y.rows[0].is_max_in_panel).toBe(true);
    expect(vm.shared_scale).toBe(false);
  });

  it("panel_policy axis_order respects panel_order field", () => {
    const vm = buildFacetPanelGridViewModel({
      rows: [
        { panel: "Z", cat: "a", v: 100 },
        { panel: "A", cat: "a", v: 1 },
        { panel: "M", cat: "a", v: 50 },
      ] as Array<PanelRow & { order?: number }>,
      toPanelRow: (r) => ({
        ...toPanelRow(r),
        panel_order:
          r.panel === "A" ? 1 : r.panel === "M" ? 2 : 3,
      }),
      row_policy: "value_desc",
      panel_policy: "axis_order",
    });
    expect(vm.panels.map((p) => p.panel_id)).toEqual(["A", "M", "Z"]);
  });

  it("missing values stay visible; panel with only null still appears", () => {
    const vm = buildFacetPanelGridViewModel({
      rows: [
        { panel: "ok", cat: "a", v: 10 },
        { panel: "ghost", cat: "a", v: null },
      ],
      toPanelRow,
      row_policy: "value_desc",
      panel_policy: "value_desc",
    });
    expect(vm.panels.map((p) => p.panel_id)).toEqual(["ok", "ghost"]);
    const ghost = vm.panels[1];
    expect(ghost.panel_value).toBeNull();
    expect(ghost.rows[0].is_missing).toBe(true);
    expect(ghost.rows[0].rank).toBeNull();
  });

  it("row pinned_rank pins inside the panel", () => {
    const vm = buildFacetPanelGridViewModel({
      rows: ROWS,
      toPanelRow: (r) => ({
        ...toPanelRow(r),
        pinned_rank: r.cat === "F" ? 0 : null,
      }),
      row_policy: "pinned_then_value",
      panel_policy: "value_desc",
    });
    for (const p of vm.panels) {
      expect(p.rows[0].id.endsWith("-F")).toBe(true);
      expect(p.rows[0].is_pinned).toBe(true);
    }
  });

  it("empty input → empty view-model", () => {
    const vm = buildFacetPanelGridViewModel<PanelRow>({
      rows: [],
      toPanelRow,
      row_policy: "value_desc",
      panel_policy: "value_desc",
    });
    expect(vm.panels).toEqual([]);
    expect(vm.global_max_abs_value).toBe(0);
  });
});
