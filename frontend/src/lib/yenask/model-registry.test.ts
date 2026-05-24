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

  it("has the four Slice C entries (SmolLM2-135M + TinyLlama + Qwen2.5 + Phi-3.5) plus the Slice D-1 SmolLM2-360M default", () => {
    // D-24: registry expanded from 1 → 4 entries.
    // D-26 (Slice D-1): 360M added as the new default.
    const ids = MODEL_REGISTRY.map((m) => m.id);
    expect(ids).toContain("smollm2-360m-instruct");
    expect(ids).toContain("smollm2-135m-instruct");
    expect(ids).toContain("tinyllama-1-1b-chat");
    expect(ids).toContain("qwen2-5-1-5b-instruct");
    expect(ids).toContain("phi-3-5-mini-instruct");
    expect(MODEL_REGISTRY.length).toBeGreaterThanOrEqual(5);
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

  it("SmolLM2-135M estimated_download_mb is the D-26-corrected 118 MB (not the stale 88)", () => {
    const smol = MODEL_REGISTRY.find((m) => m.id === "smollm2-135m-instruct");
    expect(smol).toBeDefined();
    expect(smol!.estimated_download_mb).toBe(118);
  });

  it("estimated_ram_mb is optional and when present is positive", () => {
    // D-24: "ModelEntry gains an optional estimated_ram_mb?: number field".
    for (const m of MODEL_REGISTRY) {
      if (m.estimated_ram_mb !== undefined) {
        expect(m.estimated_ram_mb).toBeGreaterThan(0);
      }
    }
  });

  it("large entries (>1024 MB) declare estimated_ram_mb so the picker can warn", () => {
    // Not a hard contract, but a useful Slice C invariant: any model
    // big enough to trigger the D-24 Large-tier confirm is also big
    // enough to warrant a RAM hint for the citizen.
    for (const m of MODEL_REGISTRY) {
      if (m.estimated_download_mb > 1024) {
        expect(m.estimated_ram_mb).toBeDefined();
      }
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

  it("the default is SmolLM2-360M per D-26 (Slice D-1) strict-upgrade verdict", () => {
    // Locks in the Slice D-1 flip so a casual rebase / refactor can't
    // silently regress the default back to 135M. If a future PR
    // intentionally swaps the default, this test moves in the same PR.
    expect(DEFAULT_MODEL_ID).toBe("smollm2-360m-instruct");
    const def = getDefaultModel();
    expect(def.display_name).toBe("SmolLM2-360M-Instruct");
    expect(def.params_label).toBe("360M");
    expect(def.repo_id).toBe("HuggingFaceTB/SmolLM2-360M-Instruct");
    expect(def.estimated_download_mb).toBe(273);
    // Default model must stay in D-24 Small tier (≤500 MB) so the
    // first-run citizen flow has no friction.
    expect(def.estimated_download_mb).toBeLessThanOrEqual(500);
  });
});
