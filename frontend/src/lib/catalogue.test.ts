import { describe, it, expect } from "vitest";
import {
  displayForArtifact,
  indicatorPathForArtifact,
  type CatalogueArtifact,
} from "./catalogue";

describe("displayForArtifact", () => {
  it("returns the explicit display when present", () => {
    const a: CatalogueArtifact = {
      kind: "election",
      id: "AcGenMay2026",
      display: "TN Assembly Election 2026",
    };
    expect(displayForArtifact(a)).toBe("TN Assembly Election 2026");
  });

  it("falls back to id when display is missing", () => {
    const a: CatalogueArtifact = {
      kind: "indicator",
      id: "fiscal/outstanding_debt_pct_gsdp",
    };
    expect(displayForArtifact(a)).toBe("fiscal/outstanding_debt_pct_gsdp");
  });
});

describe("indicatorPathForArtifact", () => {
  it("composes the dataset path for an indicator artifact", () => {
    const a: CatalogueArtifact = {
      kind: "indicator",
      id: "fiscal/outstanding_debt_pct_gsdp",
    };
    expect(indicatorPathForArtifact(a)).toBe(
      "/indicators/in/fiscal/outstanding_debt_pct_gsdp.json",
    );
  });

  it("returns null for non-indicator kinds", () => {
    const election: CatalogueArtifact = { kind: "election", id: "AcGenMay2026" };
    const fc: CatalogueArtifact = { kind: "feature_collection", id: "power_plants" };
    expect(indicatorPathForArtifact(election)).toBeNull();
    expect(indicatorPathForArtifact(fc)).toBeNull();
  });
});
