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

  // U4 reader-before-writer (ADR-0047): the plural `chart_types[]` is
  // the new writer; the singular `chart_type` is the deprecated alias.
  // Reader prefers `chart_types[0]` when both are present.
  it("dispatches stacked-trend when chart_types[0] is stacked-trend", () => {
    expect(
      renderKindForArtifact(
        baseArtifact({ chart_types: ["stacked-trend"], dimension: "power_source" }),
      ),
    ).toBe("stacked-trend");
  });

  it("dispatches trio when chart_types[0] is choropleth", () => {
    expect(
      renderKindForArtifact(baseArtifact({ chart_types: ["choropleth"] })),
    ).toBe("trio");
  });

  it("chart_types[0] wins over chart_type when both are present", () => {
    // Plural is the new writer (U4); singular is the deprecated alias.
    // If both disagree, the plural wins so a migrated row beats its
    // pre-migration shadow.
    expect(
      renderKindForArtifact(
        baseArtifact({
          chart_types: ["choropleth"],
          chart_type: "stacked-trend",
        }),
      ),
    ).toBe("trio");
    expect(
      renderKindForArtifact(
        baseArtifact({
          chart_types: ["stacked-trend"],
          chart_type: "choropleth",
        }),
      ),
    ).toBe("stacked-trend");
  });

  it("falls back to chart_type when chart_types is empty array", () => {
    expect(
      renderKindForArtifact(
        baseArtifact({
          chart_types: [],
          chart_type: "stacked-trend",
        }),
      ),
    ).toBe("stacked-trend");
  });
});
