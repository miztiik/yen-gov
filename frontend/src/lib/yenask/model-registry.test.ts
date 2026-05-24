// Tests for model-registry.ts.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-15 (Slice C registry shape), D-32 (Slice E.1 embeddings entry).

import { describe, expect, it } from "vitest";
import {
  MODEL_REGISTRY,
  DEFAULT_MODEL_ID,
  getModelById,
  getDefaultModel,
  listTextGenerationModels,
  listEmbeddingsModels,
} from "./model-registry";

describe("MODEL_REGISTRY", () => {
  it("has at least one entry", () => {
    expect(MODEL_REGISTRY.length).toBeGreaterThan(0);
  });

  it("has the five Slice C/D text-generation entries plus the Slice E.1 MiniLM-L6-v2 embeddings entry", () => {
    // D-24: registry expanded from 1 → 4 entries.
    // D-26 (Slice D-1): 360M added as the new default.
    // D-32 (Slice E.1): minilm-l6-v2-embeddings added for retrieval-augmented
    //   intent extraction (ADR-0039). NOT a text-generation model — the
    //   picker filters via listTextGenerationModels() so citizens don't see
    //   it as a chat option.
    const ids = MODEL_REGISTRY.map((m) => m.id);
    expect(ids).toContain("smollm2-360m-instruct");
    expect(ids).toContain("smollm2-135m-instruct");
    expect(ids).toContain("tinyllama-1-1b-chat");
    expect(ids).toContain("qwen2-5-1-5b-instruct");
    expect(ids).toContain("phi-3-5-mini-instruct");
    expect(ids).toContain("minilm-l6-v2-embeddings");
    expect(MODEL_REGISTRY.length).toBeGreaterThanOrEqual(6);
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

  it("every entry declares a task discriminator (text-generation | embeddings) — D-32", () => {
    // Slice E.1 ADR-0039: discriminated-union on `task` separates the picker
    // surface (text-generation) from the Slice E retrieval surface
    // (embeddings). Hand-author drift = next picker render shows the embeddings
    // model as a chat option; this test catches that.
    for (const m of MODEL_REGISTRY) {
      expect(["text-generation", "embeddings"]).toContain(m.task);
    }
  });
});

describe("listTextGenerationModels", () => {
  it("returns exactly the text-generation entries", () => {
    const list = listTextGenerationModels();
    for (const m of list) {
      expect(m.task).toBe("text-generation");
    }
    // The five Slice C/D entries — bump on intentional adds.
    expect(list.length).toBe(5);
  });

  it("excludes the Slice E.1 embeddings entry from the picker surface", () => {
    // D-32 Jony: the picker UI iterates listTextGenerationModels(); the
    // embeddings entry would confuse a citizen who picked it expecting
    // it to answer questions.
    const list = listTextGenerationModels();
    expect(list.map((m) => m.id)).not.toContain("minilm-l6-v2-embeddings");
  });

  it("contains the default model", () => {
    const list = listTextGenerationModels();
    expect(list.map((m) => m.id)).toContain(DEFAULT_MODEL_ID);
  });
});

describe("listEmbeddingsModels", () => {
  it("returns exactly the embeddings entries with embedding_dim", () => {
    const list = listEmbeddingsModels();
    for (const m of list) {
      expect(m.task).toBe("embeddings");
      expect(m.embedding_dim).toBeGreaterThan(0);
    }
    expect(list.length).toBe(1);
  });

  it("the MiniLM-L6-v2 entry has the Xenova repo_id and 384-dim output (D-32 lock)", () => {
    // ADR-0039 locks the embeddings choice to Xenova/all-MiniLM-L6-v2.
    // Swapping the repo_id or dimension is an ADR-level decision, not a
    // casual refactor.
    const list = listEmbeddingsModels();
    expect(list.length).toBe(1);
    const minilm = list[0];
    expect(minilm.id).toBe("minilm-l6-v2-embeddings");
    expect(minilm.repo_id).toBe("Xenova/all-MiniLM-L6-v2");
    expect(minilm.embedding_dim).toBe(384);
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
