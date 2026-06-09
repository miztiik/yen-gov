// Pure-helper tests for MethodDrawer.
//
// The Svelte component itself uses native <dialog> + bind:this; we
// pin only the pure helpers (partitionByValidity, validityTierLabel,
// validityBadgeText) per CLAUDE.md vitest doctrine (no jsdom).

import { describe, expect, it } from "vitest";
import {
  partitionByValidity,
  validityBadgeText,
  validityTierLabel,
  type MethodPickerOption,
} from "./MethodDrawer.svelte";

const SAMPLE: MethodPickerOption[] = [
  { id: "fptp", label: "First-Past-The-Post", validity: "fully_workable" },
  {
    id: "proportional",
    label: "Proportional (Sainte-Lague, state pool)",
    short_label: "Proportional (Sainte-Lague)",
    headline: "Seats follow vote share, pooled across the state.",
    validity: "fully_workable",
  },
  {
    id: "borda",
    label: "Borda Count",
    validity: "medium_validity",
  },
  {
    id: "ranked-choice",
    label: "Ranked-choice (proportional transfer)",
    validity: "medium_validity",
  },
];

describe("partitionByValidity", () => {
  it("splits methods into fully_workable + medium_validity groups", () => {
    const { fully_workable, medium_validity } = partitionByValidity(SAMPLE);
    expect(fully_workable.map((m) => m.id)).toEqual(["fptp", "proportional"]);
    expect(medium_validity.map((m) => m.id)).toEqual(["borda", "ranked-choice"]);
  });

  it("preserves the input order within each group", () => {
    const reordered: MethodPickerOption[] = [
      { id: "a", label: "A", validity: "medium_validity" },
      { id: "b", label: "B", validity: "fully_workable" },
      { id: "c", label: "C", validity: "medium_validity" },
      { id: "d", label: "D", validity: "fully_workable" },
    ];
    const { fully_workable, medium_validity } = partitionByValidity(reordered);
    expect(fully_workable.map((m) => m.id)).toEqual(["b", "d"]);
    expect(medium_validity.map((m) => m.id)).toEqual(["a", "c"]);
  });

  it("handles an empty registry", () => {
    const { fully_workable, medium_validity } = partitionByValidity([]);
    expect(fully_workable).toEqual([]);
    expect(medium_validity).toEqual([]);
  });

  it("returns empty groups when one tier is absent", () => {
    const only_medium: MethodPickerOption[] = [
      { id: "x", label: "X", validity: "medium_validity" },
    ];
    const { fully_workable, medium_validity } = partitionByValidity(only_medium);
    expect(fully_workable).toEqual([]);
    expect(medium_validity).toHaveLength(1);
  });
});

describe("validityTierLabel", () => {
  it("returns 'Fully workable today' for fully_workable", () => {
    expect(validityTierLabel("fully_workable")).toBe("Fully workable today");
  });

  it("returns 'Experimental' for medium_validity", () => {
    expect(validityTierLabel("medium_validity")).toBe("Experimental");
  });

  it("output is ASCII-only", () => {
    for (const tier of ["fully_workable", "medium_validity"] as const) {
      const text = validityTierLabel(tier);
      expect(Array.from(text).every((c) => c.charCodeAt(0) < 128)).toBe(true);
    }
  });
});

describe("validityBadgeText", () => {
  it("returns 'Fully workable' for fully_workable", () => {
    expect(validityBadgeText("fully_workable")).toBe("Fully workable");
  });

  it("returns 'Experimental' for medium_validity", () => {
    expect(validityBadgeText("medium_validity")).toBe("Experimental");
  });
});
