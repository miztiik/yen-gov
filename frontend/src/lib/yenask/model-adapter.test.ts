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
  task: "text-generation",
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

    // PR F (Andre 2026-05-24): the placeholder `downloading 0%` push
    // was removed from prepare(). The first real event from the runtime
    // is the first status the UI sees. Here that is the 42% progress tick.
    expect(events.map((e) => e.kind)).toEqual([
      "downloading",
      "compiling",
      "ready",
    ]);
    const dlEvent = events[0] as Extract<ReadinessStatus, { kind: "downloading" }>;
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

  // PR F (Andre 2026-05-24): cache-hit detection. Transformers.js v3+
  // caches model assets in the Cache Storage API. On a cache hit every
  // `progress` event arrives at exactly `progress: 100` with no preceding
  // `progress < 100` tick — there are no network bytes to count. The
  // adapter must emit `loading-from-cache` for these so the UI does not
  // lie with a phantom "Downloading…" banner.
  it("emits loading-from-cache when every progress event arrives at progress:100 (warm cache)", async () => {
    handles.pipelineFactory.mockImplementationOnce(
      async (_task: string, _id: string, opts: Record<string, unknown>) => {
        const cb = opts.progress_callback as ((ev: { status: string; file?: string; progress?: number }) => void) | undefined;
        // Warm cache: per-file replay tick at 100% only, no prior < 100 tick.
        cb?.({ status: "progress", file: "model.onnx", progress: 100 });
        cb?.({ status: "progress", file: "tokenizer.json", progress: 100 });
        cb?.({ status: "done" });
        return handles.generateFn;
      },
    );
    const events: ReadinessStatus[] = [];
    const a = createAdapter(MODEL);
    await a.prepare((s) => events.push(s));
    const kinds = events.map((e) => e.kind);
    // No `downloading` for the warm-cache path — Andre's UI-lies fix.
    expect(kinds).toEqual([
      "loading-from-cache",
      "loading-from-cache",
      "compiling",
      "ready",
    ]);
    const firstCache = events[0] as Extract<ReadinessStatus, { kind: "loading-from-cache" }>;
    expect(firstCache.file).toBe("model.onnx");
  });

  // PR F: real-download path is unchanged. ANY `progress < 100` tick latches
  // `_sawRealDownload = true` so the trailing `progress: 100` tick is correctly
  // classified as the final frame of a real download, not a cache replay.
  it("emits downloading throughout when bytes flow (cold cache, including the closing 100% tick)", async () => {
    handles.pipelineFactory.mockImplementationOnce(
      async (_task: string, _id: string, opts: Record<string, unknown>) => {
        const cb = opts.progress_callback as ((ev: { status: string; file?: string; progress?: number; loaded?: number; total?: number }) => void) | undefined;
        // Cold cache: bytes flow, then the final 100% tick.
        cb?.({ status: "progress", file: "model.onnx", progress: 42, loaded: 42, total: 100 });
        cb?.({ status: "progress", file: "model.onnx", progress: 100, loaded: 100, total: 100 });
        cb?.({ status: "done" });
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
    // The closing 100% tick is `downloading`, NOT `loading-from-cache`,
    // because `_sawRealDownload` was latched by the 42% tick.
    const last = events[1] as Extract<ReadinessStatus, { kind: "downloading" }>;
    expect(last.percent).toBe(100);
  });

  // PR F: the cache-hit flag is reset per prepare() call so a failed-then-
  // retried prepare doesn't inherit stale state from the prior run.
  it("resets _sawRealDownload between prepare() calls (warm cache after a failed cold prepare)", async () => {
    // First prepare: bytes flow, then explode.
    handles.pipelineFactory.mockImplementationOnce(
      async (_task: string, _id: string, opts: Record<string, unknown>) => {
        const cb = opts.progress_callback as ((ev: { status: string; file?: string; progress?: number }) => void) | undefined;
        cb?.({ status: "progress", file: "model.onnx", progress: 30 });
        throw new Error("network died mid-download");
      },
    );
    const a = createAdapter(MODEL);
    await expect(a.prepare()).rejects.toThrow("network died");

    // Second prepare: warm cache (100% only). Without the per-call reset
    // the prior latched `_sawRealDownload` would mis-classify these as
    // `downloading`. With the reset, they correctly emit `loading-from-cache`.
    handles.pipelineFactory.mockImplementationOnce(
      async (_task: string, _id: string, opts: Record<string, unknown>) => {
        const cb = opts.progress_callback as ((ev: { status: string; file?: string; progress?: number }) => void) | undefined;
        cb?.({ status: "progress", file: "model.onnx", progress: 100 });
        cb?.({ status: "done" });
        return handles.generateFn;
      },
    );
    const events: ReadinessStatus[] = [];
    await a.prepare((s) => events.push(s));
    expect(events.map((e) => e.kind)).toEqual([
      "loading-from-cache",
      "compiling",
      "ready",
    ]);
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
    expect(out.text).toBe("hello world");
    expect(out.wall_ms).toBeGreaterThanOrEqual(0);
  });

  // D-22 (Slice A): the transformers.js adapter MUST return `null` for all
  // four finer-grained timing fields because the pipeline is a black-box
  // round-trip (no streaming, no first-token callback, no encode/decode
  // observability). The Debug log UI renders `null` as `—` to make this
  // visible to the operator. Future provider seams (WebLLM, future SDK
  // versions with streaming) can populate these without changing the
  // contract.
  it("returns null for encode/generate/decode/ttft timings (transformers-js is black-box)", async () => {
    handles.pipelineFactory.mockResolvedValueOnce(handles.generateFn);
    handles.generateFn.mockResolvedValueOnce([{ generated_text: "ok" }]);
    const a = createAdapter(MODEL);
    await a.prepare();
    const out = await a.generate([{ role: "user", content: "hi" }]);
    expect(out.encode_ms).toBeNull();
    expect(out.generate_ms).toBeNull();
    expect(out.decode_ms).toBeNull();
    expect(out.ttft_ms).toBeNull();
    // The aggregate wall_ms remains measurable — only the finer breakdown
    // is unobservable.
    expect(out.wall_ms).toBeGreaterThanOrEqual(0);
  });

  it("reports exact token counts when the pipeline exposes a tokenizer (D-20)", async () => {
    const encode = vi.fn((text: string) =>
      // Simple word-split tokenizer surrogate; lets us assert exact counts.
      text.split(/\s+/).filter(Boolean).map((_, i) => i),
    );
    const innerFn = vi.fn().mockResolvedValueOnce([
      { generated_text: "reply text here" },
    ]);
    const pipelineWithTokenizer = Object.assign(innerFn, {
      tokenizer: { encode },
    });
    handles.pipelineFactory.mockResolvedValueOnce(pipelineWithTokenizer);
    const a = createAdapter(MODEL);
    await a.prepare();
    const out = await a.generate([
      { role: "user", content: "hello there world" },
    ]);
    expect(out.text).toBe("reply text here");
    expect(out.tokens_approximate).toBe(false);
    // input = "user: hello there world" → 4 tokens; output = 3 tokens.
    expect(out.tokens_in).toBe(4);
    expect(out.tokens_out).toBe(3);
    expect(encode).toHaveBeenCalledTimes(2);
  });

  it("falls back to chars/4 approximation when no tokenizer is present (D-20)", async () => {
    const innerFn = vi.fn().mockResolvedValueOnce([{ generated_text: "ABCDEFGH" }]);
    handles.pipelineFactory.mockResolvedValueOnce(innerFn);
    const a = createAdapter(MODEL);
    await a.prepare();
    const out = await a.generate([{ role: "user", content: "hi" }]);
    expect(out.tokens_approximate).toBe(true);
    expect(out.tokens_in).toBeGreaterThan(0);
    // "ABCDEFGH" is 8 chars → ~2 tokens.
    expect(out.tokens_out).toBe(2);
  });

  it("falls back to approximation when tokenizer.encode throws (D-20)", async () => {
    const innerFn = vi.fn().mockResolvedValueOnce([{ generated_text: "out" }]);
    const pipelineWithBadTokenizer = Object.assign(innerFn, {
      tokenizer: {
        encode: () => {
          throw new Error("unicode oops");
        },
      },
    });
    handles.pipelineFactory.mockResolvedValueOnce(pipelineWithBadTokenizer);
    const a = createAdapter(MODEL);
    await a.prepare();
    const out = await a.generate([{ role: "user", content: "in" }]);
    expect(out.tokens_approximate).toBe(true);
    expect(out.tokens_in).toBeGreaterThan(0);
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
