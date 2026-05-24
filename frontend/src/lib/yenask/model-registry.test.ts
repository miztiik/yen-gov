// Tests for model-registry.ts.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-15.

import { describe, expect, it } from "vitest";
import {
  MODEL_REGISTRY,
  DEFAULT_MODEL_ID,
  getModelById,
  getDefaultModel,
} from "./model-registry";

describe("MODEL_REGISTRY", () => {
  it("has at least one entry", () => {
    expect(MODEL_REGISTRY.length).toBeGreaterThan(0);
  });

  it("has unique ids", () => {
    const ids = MODEL_REGISTRY.map((m) => m.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("contains the default id", () => {
    expect(MODEL_REGISTRY.map((m) => m.id)).toContain(DEFAULT_MODEL_ID);
  });

  it("every entry has a known provider", () => {
    for (const m of MODEL_REGISTRY) {
      expect(m.provider).toBe("transformers-js");
    }
  });

  it("every entry declares a non-empty repo_id and dtype", () => {
    for (const m of MODEL_REGISTRY) {
      expect(m.repo_id.length).toBeGreaterThan(0);
      expect(m.dtype.length).toBeGreaterThan(0);
    }
  });

  it("every entry declares an estimated download size", () => {
    for (const m of MODEL_REGISTRY) {
      expect(m.estimated_download_mb).toBeGreaterThan(0);
    }
  });
});

describe("getModelById", () => {
  it("returns the default entry for the default id", () => {
    const m = getModelById(DEFAULT_MODEL_ID);
    expect(m).toBeDefined();
    expect(m!.id).toBe(DEFAULT_MODEL_ID);
  });

  it("returns undefined for an unknown id", () => {
    expect(getModelById("__nonexistent__")).toBeUndefined();
  });
});

describe("getDefaultModel", () => {
  it("returns an entry whose id matches DEFAULT_MODEL_ID", () => {
    expect(getDefaultModel().id).toBe(DEFAULT_MODEL_ID);
  });
});
