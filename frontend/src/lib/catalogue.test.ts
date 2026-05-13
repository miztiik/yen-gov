import { describe, it, expect } from "vitest";
import {
  displayForArtifact,
  indicatorPathForArtifact,
  resolvePeerSetDefault,
  type CatalogueArtifact,
  type CatalogueTopic,
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

describe("resolvePeerSetDefault", () => {
  const topic: CatalogueTopic = {
    id: "fiscal",
    title: "Fiscal",
    list: "state",
    summary: "x",
    peer_set_default: "general_category",
    artifacts: [],
  };

  it("returns the artifact override when present", () => {
    const a: CatalogueArtifact = {
      kind: "indicator",
      id: "fiscal/net_transfers_from_centre",
      peer_set_default: "all",
    };
    expect(resolvePeerSetDefault(topic, a)).toBe("all");
  });

  it("falls back to topic.peer_set_default when artifact has none", () => {
    const a: CatalogueArtifact = {
      kind: "indicator",
      id: "fiscal/outstanding_debt_pct_gsdp",
    };
    expect(resolvePeerSetDefault(topic, a)).toBe("general_category");
  });

  it("falls back to `all` when neither artifact nor topic declare one", () => {
    const t: CatalogueTopic = {
      id: "x",
      title: "x",
      list: "na",
      summary: "x",
      artifacts: [],
    };
    const a: CatalogueArtifact = { kind: "indicator", id: "x/y" };
    expect(resolvePeerSetDefault(t, a)).toBe("all");
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
