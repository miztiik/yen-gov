// Tests for size-tier.ts.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-24.

import { describe, expect, it } from "vitest";
import {
  classifySizeTier,
  formatModelSize,
  formatRamLabel,
  isOutOfMemoryError,
  OOM_FAILURE_COPY,
} from "./size-tier";

describe("classifySizeTier", () => {
  it("classifies small models (≤ 500 MB) as 'small'", () => {
    expect(classifySizeTier(1)).toBe("small");
    expect(classifySizeTier(118)).toBe("small"); // SmolLM2-135M
    expect(classifySizeTier(273)).toBe("small"); // SmolLM2-360M
    expect(classifySizeTier(500)).toBe("small"); // boundary
  });

  it("classifies medium models (501–1024 MB) as 'medium'", () => {
    expect(classifySizeTier(501)).toBe("medium");
    expect(classifySizeTier(600)).toBe("medium"); // TinyLlama-1.1B
    expect(classifySizeTier(1024)).toBe("medium"); // boundary
  });

  it("classifies large models (> 1024 MB) as 'large'", () => {
    expect(classifySizeTier(1025)).toBe("large");
    expect(classifySizeTier(1220)).toBe("large"); // Qwen2.5-1.5B
    expect(classifySizeTier(2320)).toBe("large"); // Phi-3.5-mini
    expect(classifySizeTier(10000)).toBe("large");
  });

  it("degrades non-finite / non-positive inputs to 'small' (defensive)", () => {
    expect(classifySizeTier(0)).toBe("small");
    expect(classifySizeTier(-1)).toBe("small");
    expect(classifySizeTier(Number.NaN)).toBe("small");
    expect(classifySizeTier(Number.POSITIVE_INFINITY)).toBe("small");
  });
});

describe("formatModelSize", () => {
  it("renders sub-1024 MB sizes as integer MB", () => {
    expect(formatModelSize(1)).toBe("1 MB");
    expect(formatModelSize(118)).toBe("118 MB");
    expect(formatModelSize(273)).toBe("273 MB");
    expect(formatModelSize(999)).toBe("999 MB");
    expect(formatModelSize(1023)).toBe("1023 MB");
  });

  it("promotes to GB at the 1024 MB boundary with one decimal", () => {
    expect(formatModelSize(1024)).toBe("1.0 GB");
    expect(formatModelSize(1220)).toBe("1.2 GB"); // Qwen2.5-1.5B
    expect(formatModelSize(2320)).toBe("2.3 GB"); // Phi-3.5-mini
    expect(formatModelSize(2048)).toBe("2.0 GB");
  });

  it("rounds non-integer MB sensibly", () => {
    expect(formatModelSize(117.6)).toBe("118 MB");
    expect(formatModelSize(118.4)).toBe("118 MB");
  });

  it("renders an em-dash for invalid sizes", () => {
    expect(formatModelSize(0)).toBe("—");
    expect(formatModelSize(-1)).toBe("—");
    expect(formatModelSize(Number.NaN)).toBe("—");
  });
});

describe("formatRamLabel", () => {
  it("renders MB for sub-GB RAM estimates", () => {
    expect(formatRamLabel(280)).toBe("Needs ~280 MB RAM");
    expect(formatRamLabel(512)).toBe("Needs ~512 MB RAM");
  });

  it("promotes to GB at the 1024 MB boundary with one decimal", () => {
    expect(formatRamLabel(1024)).toBe("Needs ~1.0 GB RAM");
    expect(formatRamLabel(2300)).toBe("Needs ~2.2 GB RAM");
    expect(formatRamLabel(4500)).toBe("Needs ~4.4 GB RAM");
  });

  it("returns null when the field is absent / invalid", () => {
    expect(formatRamLabel(undefined)).toBeNull();
    expect(formatRamLabel(0)).toBeNull();
    expect(formatRamLabel(-1)).toBeNull();
    expect(formatRamLabel(Number.NaN)).toBeNull();
  });
});

describe("isOutOfMemoryError", () => {
  it("detects 'out of memory' substring (case-insensitive)", () => {
    expect(isOutOfMemoryError("out of memory")).toBe(true);
    expect(isOutOfMemoryError("Out Of Memory")).toBe(true);
    expect(isOutOfMemoryError("OUT OF MEMORY")).toBe(true);
    expect(isOutOfMemoryError("Error: out of memory while loading")).toBe(true);
  });

  it("detects 'OOM' substring", () => {
    expect(isOutOfMemoryError("OOM kill")).toBe(true);
    expect(isOutOfMemoryError("process killed: oom")).toBe(true);
  });

  it("detects 'allocation' substring", () => {
    expect(isOutOfMemoryError("Memory allocation failed")).toBe(true);
    expect(isOutOfMemoryError("failed to allocate buffer (allocation)")).toBe(true);
  });

  it("detects 'WebAssembly.Memory' substring (case-insensitive)", () => {
    expect(isOutOfMemoryError("WebAssembly.Memory grow failed")).toBe(true);
    expect(isOutOfMemoryError("webassembly.memory cannot grow")).toBe(true);
  });

  it("returns false for unrelated errors", () => {
    expect(isOutOfMemoryError("Failed to fetch")).toBe(false);
    expect(isOutOfMemoryError("CORS error")).toBe(false);
    expect(isOutOfMemoryError("Model not found")).toBe(false);
  });

  it("returns false for null / undefined / empty / non-string inputs", () => {
    expect(isOutOfMemoryError(null)).toBe(false);
    expect(isOutOfMemoryError(undefined)).toBe(false);
    expect(isOutOfMemoryError("")).toBe(false);
    expect(isOutOfMemoryError(42)).toBe(false);
    expect(isOutOfMemoryError({})).toBe(false);
  });
});

describe("OOM_FAILURE_COPY", () => {
  it("is a non-empty string source-of-truth", () => {
    expect(typeof OOM_FAILURE_COPY).toBe("string");
    expect(OOM_FAILURE_COPY.length).toBeGreaterThan(0);
    expect(OOM_FAILURE_COPY).toContain("Model too large");
    expect(OOM_FAILURE_COPY).toContain("smaller model");
  });
});
