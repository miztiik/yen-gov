import { describe, it, expect } from "vitest";
import { renderKindForArtifact } from "./topic-dispatch";
import type { CatalogueArtifact } from "./catalogue";

const baseArtifact = (over: Partial<CatalogueArtifact> = {}): CatalogueArtifact => ({
  kind: "indicator",
  id: "x/y",
  ...over,
});

describe("renderKindForArtifact", () => {
  it("dispatches stacked-trend when chart_type is stacked-trend", () => {
    expect(
      renderKindForArtifact(
        baseArtifact({ chart_type: "stacked-trend", dimension: "power_source" }),
      ),
    ).toBe("stacked-trend");
  });

  it("dispatches trio when chart_type is choropleth", () => {
    expect(renderKindForArtifact(baseArtifact({ chart_type: "choropleth" }))).toBe(
      "trio",
    );
  });

  it("dispatches trio when chart_type is ranked (no bespoke ranked-only path today)", () => {
    expect(renderKindForArtifact(baseArtifact({ chart_type: "ranked" }))).toBe(
      "trio",
    );
  });

  it("dispatches trio when chart_type is absent (pre-v1.2 catalogues)", () => {
    expect(renderKindForArtifact(baseArtifact())).toBe("trio");
  });
});
