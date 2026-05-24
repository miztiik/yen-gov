// Tests for model-adapter.ts.
//
// See plan-doc TODO/20260518-browser-governance-insight-assistant-plan.md §17
// D-15. We mock @huggingface/transformers entirely — the adapter is the
// only seam that imports it, so the mock here covers every codepath under
// test without ever pulling the real 50 MB SDK into vitest.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ModelEntry } from "./model-registry";
import {
  createAdapter,
  extractAssistantText,
  type ReadinessStatus,
} from "./model-adapter";

// ----- transformers.js mock --------------------------------------------------

// `vi.hoisted` so the mock factory below sees the same shared handles.
const handles = vi.hoisted(() => ({
  pipelineFactory: vi.fn(),
  generateFn: vi.fn(),
}));

vi.mock("@huggingface/transformers", () => ({
  pipeline: handles.pipelineFactory,
}));

const MODEL: ModelEntry = {
  id: "test-model",
  display_name: "Test Model",
  params_label: "10M",
  provider: "transformers-js",
  repo_id: "test/repo",
  dtype: "q4f16",
  device: "auto",
  estimated_download_mb: 5,
  notes: "test fixture",
};

beforeEach(() => {
  handles.pipelineFactory.mockReset();
  handles.generateFn.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("createAdapter", () => {
  it("dispatches transformers-js entries to the transformers.js adapter", () => {
    const a = createAdapter(MODEL);
    expect(a.model).toBe(MODEL);
    expect(a.status().kind).toBe("idle");
  });
});

describe("ReadinessStatus state machine", () => {
  it("transitions idle → downloading → compiling → ready", async () => {
    let onProgress: ((ev: { status: string; file?: string; progress?: number; loaded?: number; total?: number }) => void) | undefined;
    handles.pipelineFactory.mockImplementationOnce(
      async (_task: string, _id: string, opts: Record<string, unknown>) => {
        onProgress = opts.progress_callback as typeof onProgress;
        onProgress!({ status: "progress", file: "model.onnx", progress: 42, loaded: 42, total: 100 });
        onProgress!({ status: "ready" });
        return handles.generateFn;
      },
    );

    const events: ReadinessStatus[] = [];
    const a = createAdapter(MODEL);
    await a.prepare((s) => events.push(s));

    expect(events.map((e) => e.kind)).toEqual([
      "downloading",
      "downloading",
      "compiling",
      "ready",
    ]);
    const dlEvent = events[1] as Extract<ReadinessStatus, { kind: "downloading" }>;
    expect(dlEvent.file).toBe("model.onnx");
    expect(dlEvent.percent).toBe(42);
    expect(a.status().kind).toBe("ready");
  });

  it("transitions to failed on download error and preserves the message", async () => {
    handles.pipelineFactory.mockRejectedValueOnce(new Error("boom"));
    const events: ReadinessStatus[] = [];
    const a = createAdapter(MODEL);
    await expect(a.prepare((s) => events.push(s))).rejects.toThrow("boom");
    const last = events.at(-1)!;
    expect(last.kind).toBe("failed");
    if (last.kind === "failed") expect(last.error).toBe("boom");
  });

  it("is idempotent once ready — second prepare() resolves without re-downloading", async () => {
    handles.pipelineFactory.mockImplementation(
      async (_task: string, _id: string, opts: Record<string, unknown>) => {
        const cb = opts.progress_callback as ((ev: { status: string }) => void) | undefined;
        cb?.({ status: "ready" });
        return handles.generateFn;
      },
    );
    const a = createAdapter(MODEL);
    await a.prepare();
    await a.prepare();
    expect(handles.pipelineFactory).toHaveBeenCalledTimes(1);
  });
});

describe("generate", () => {
  it("throws when called before prepare resolves", async () => {
    const a = createAdapter(MODEL);
    await expect(a.generate([{ role: "user", content: "hi" }])).rejects.toThrow(
      /before prepare/,
    );
  });

  it("returns the assistant text from a chat-array result", async () => {
    handles.pipelineFactory.mockResolvedValueOnce(handles.generateFn);
    handles.generateFn.mockResolvedValueOnce([
      {
        generated_text: [
          { role: "user", content: "hi" },
          { role: "assistant", content: "hello world" },
        ],
      },
    ]);
    const a = createAdapter(MODEL);
    await a.prepare();
    const out = await a.generate([{ role: "user", content: "hi" }]);
    expect(out).toBe("hello world");
  });

  it("passes options through to the pipeline call", async () => {
    handles.pipelineFactory.mockResolvedValueOnce(handles.generateFn);
    handles.generateFn.mockResolvedValueOnce([{ generated_text: "ok" }]);
    const a = createAdapter(MODEL);
    await a.prepare();
    await a.generate([{ role: "user", content: "hi" }], {
      max_new_tokens: 32,
      temperature: 0.7,
      top_p: 0.9,
    });
    expect(handles.generateFn).toHaveBeenCalledTimes(1);
    const [, opts] = handles.generateFn.mock.calls[0]!;
    expect(opts).toMatchObject({
      max_new_tokens: 32,
      temperature: 0.7,
      top_p: 0.9,
      do_sample: true,
      return_full_text: false,
    });
  });
});

describe("extractAssistantText", () => {
  it("unwraps single-element arrays", () => {
    expect(extractAssistantText([{ generated_text: "x" }])).toBe("x");
  });

  it("returns chat-array last assistant turn", () => {
    expect(
      extractAssistantText({
        generated_text: [
          { role: "user", content: "q" },
          { role: "assistant", content: "a" },
        ],
      }),
    ).toBe("a");
  });

  it("returns a bare string passthrough", () => {
    expect(extractAssistantText("plain")).toBe("plain");
  });

  it("throws on unrecognised shapes", () => {
    expect(() => extractAssistantText(42)).toThrow();
    expect(() => extractAssistantText({})).toThrow();
  });
});
