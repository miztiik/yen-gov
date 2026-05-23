import { describe, expect, it } from "vitest";

import {
  buildDumbbellRangeViewModel,
  type DumbbellRangeViewModel,
} from "./time-view-models";

// Renderer contract for DumbbellRange.svelte. Component-level DOM
// assertions are deferred to Playwright (vitest = node-env, no jsdom).

interface StateRow {
  id: string;
  label: string;
  pinned?: boolean;
  earliest: number | null;
  latest: number | null;
}

const FIXTURE: readonly StateRow[] = [
  { id: "AP",          label: "Andhra Pradesh", earliest: 50, latest: 70 },
  { id: "KA",          label: "Karnataka",      earliest: 60, latest: 55 },
  { id: "TN",          label: "Tamil Nadu",     pinned: true, earliest: 65, latest: 65 },
  { id: "KL",          label: "Kerala",         earliest: null, latest: 80 },
  { id: "BR",          label: "Bihar",          earliest: 30, latest: null },
  { id: "GH",          label: "Ghost State",    earliest: null, latest: null },
];

function buildVM(policy: "value_desc" | "latest_change" | "pinned_then_value" | "alphabetical"): DumbbellRangeViewModel<StateRow> {
  return buildDumbbellRangeViewModel({
    rows: FIXTURE,
    toEndpoints: r => ({
      id: r.id,
      label: r.label,
      pinned_rank: r.pinned ? 0 : null,
      earliest: { period_label: "2011", value: r.earliest },
      latest:   { period_label: "2021", value: r.latest },
    }),
    policy,
  });
}

describe("DumbbellRange renderer contract", () => {
  const vm = buildVM("value_desc");

  it("emits one row per input row", () => {
    expect(vm.rows.length).toBe(FIXTURE.length);
  });

  it("computes delta and direction per row", () => {
    const ap = vm.rows.find(r => r.id === "AP")!;
    expect(ap.delta).toBe(20);
    expect(ap.direction).toBe("up");

    const ka = vm.rows.find(r => r.id === "KA")!;
    expect(ka.delta).toBe(-5);
    expect(ka.direction).toBe("down");

    const tn = vm.rows.find(r => r.id === "TN")!;
    expect(tn.delta).toBe(0);
    expect(tn.direction).toBe("flat");
  });

  it("flags missing endpoints", () => {
    const kl = vm.rows.find(r => r.id === "KL")!;
    expect(kl.earliest.is_missing).toBe(true);
    expect(kl.latest.is_missing).toBe(false);
    expect(kl.delta).toBeNull();
    expect(kl.direction).toBe("missing");
  });

  it("flags a fully missing row", () => {
    const gh = vm.rows.find(r => r.id === "GH")!;
    expect(gh.is_missing).toBe(true);
    expect(gh.direction).toBe("missing");
  });

  it("max_abs_value tracks the largest endpoint", () => {
    expect(vm.max_abs_value).toBe(80); // KL.latest
  });

  it("pinned_then_value puts pinned rows first", () => {
    const sorted = buildVM("pinned_then_value");
    expect(sorted.rows[0].id).toBe("TN");
    expect(sorted.rows[0].is_pinned).toBe(true);
  });
});
