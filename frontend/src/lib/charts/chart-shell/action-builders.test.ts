// Vitest gate for the action-builder factories shipped in PR-33 of the
// chart-modernisation plan (Phase 1.4 task 4 — footer action slot
// wiring).
//
// vitest is node-env across the frontend workspace (no jsdom — see the
// comment in `IndicatorChoropleth.boundaries.test.ts:4`). DOM-touching
// helpers are exercised with hand-rolled stubs assigned to globalThis
// for the duration of a `describe` block and torn down after.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ChartShellActionSpec } from "./types";
import {
  buildCopyLinkActionSpec,
  buildViewDataActionSpec,
  copyToClipboard,
  toCsv,
  triggerBrowserDownload,
} from "./action-builders";

// --- toCsv -----------------------------------------------------------

describe("toCsv", () => {
  it("emits CRLF-terminated header + rows per RFC 4180", () => {
    const csv = toCsv(["a", "b"], [
      ["1", "2"],
      ["3", "4"],
    ]);
    expect(csv).toBe("a,b\r\n1,2\r\n3,4");
  });

  it("quotes cells containing commas", () => {
    expect(toCsv(["x"], [["a,b"]])).toBe('x\r\n"a,b"');
  });

  it("quotes cells containing double quotes and doubles the quote", () => {
    expect(toCsv(["x"], [['he said "hi"']])).toBe('x\r\n"he said ""hi"""');
  });

  it("quotes cells containing CR or LF", () => {
    expect(toCsv(["x"], [["line1\nline2"]])).toBe('x\r\n"line1\nline2"');
    expect(toCsv(["x"], [["line1\rline2"]])).toBe('x\r\n"line1\rline2"');
  });

  it("coerces null/undefined to empty string", () => {
    expect(toCsv(["a", "b"], [[null, undefined]])).toBe("a,b\r\n,");
  });

  it("coerces numbers and booleans via String()", () => {
    expect(toCsv(["n", "b"], [[42, true]])).toBe("n,b\r\n42,true");
  });

  it("handles an empty row list (header-only)", () => {
    expect(toCsv(["a", "b"], [])).toBe("a,b");
  });
});

// --- copyToClipboard -------------------------------------------------
//
// Node 22's `navigator` is a getter-only global; direct assignment
// throws. Use `vi.stubGlobal` which records the original via the
// platform's descriptor protocol and restores on `vi.unstubAllGlobals`.

describe("copyToClipboard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("uses navigator.clipboard.writeText when available and returns ok=true", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const r = await copyToClipboard("https://example.test/route");
    expect(writeText).toHaveBeenCalledWith("https://example.test/route");
    expect(r).toEqual({
      ok: true,
      href: "https://example.test/route",
      fallback_used: false,
    });
  });

  it("falls back to execCommand when clipboard.writeText rejects", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const execCommand = vi.fn().mockReturnValue(true);
    const appendChild = vi.fn();
    const removeChild = vi.fn();
    vi.stubGlobal("document", {
      execCommand,
      createElement: vi.fn().mockReturnValue({
        value: "",
        setAttribute: vi.fn(),
        style: {} as Record<string, string>,
        select: vi.fn(),
      }),
      body: { appendChild, removeChild },
    });
    const r = await copyToClipboard("https://x.test/");
    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(appendChild).toHaveBeenCalledTimes(1);
    expect(removeChild).toHaveBeenCalledTimes(1);
    expect(r).toEqual({
      ok: true,
      href: "https://x.test/",
      fallback_used: true,
    });
  });

  it("falls back to execCommand when navigator.clipboard is undefined", async () => {
    vi.stubGlobal("navigator", {});
    const execCommand = vi.fn().mockReturnValue(true);
    vi.stubGlobal("document", {
      execCommand,
      createElement: vi.fn().mockReturnValue({
        value: "",
        setAttribute: vi.fn(),
        style: {} as Record<string, string>,
        select: vi.fn(),
      }),
      body: { appendChild: vi.fn(), removeChild: vi.fn() },
    });
    const r = await copyToClipboard("https://x.test/");
    expect(r.fallback_used).toBe(true);
    expect(r.ok).toBe(true);
  });

  it("returns ok=false fallback when document is also missing", async () => {
    vi.stubGlobal("navigator", {});
    vi.stubGlobal("document", undefined);
    const r = await copyToClipboard("https://x.test/");
    expect(r).toEqual({
      ok: false,
      href: "https://x.test/",
      fallback_used: true,
    });
  });
});

// --- triggerBrowserDownload -----------------------------------------

describe("triggerBrowserDownload", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("creates a Blob URL, clicks an anchor, and revokes the URL", () => {
    const click = vi.fn();
    const anchor = {
      href: "",
      download: "",
      style: {} as Record<string, string>,
      click,
    };
    const createElement = vi.fn().mockReturnValue(anchor);
    const appendChild = vi.fn();
    const removeChild = vi.fn();
    vi.stubGlobal("document", {
      createElement,
      body: { appendChild, removeChild },
    });
    const createObjectURL = vi.fn().mockReturnValue("blob:fake-url");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    vi.stubGlobal(
      "Blob",
      class FakeBlob {
        constructor(
          public parts: BlobPart[],
          public opts: BlobPropertyBag,
        ) {}
      },
    );

    const ok = triggerBrowserDownload("a,b\r\n1,2", "test.csv", "text/csv");

    expect(ok).toBe(true);
    expect(createElement).toHaveBeenCalledWith("a");
    expect(anchor.href).toBe("blob:fake-url");
    expect(anchor.download).toBe("test.csv");
    expect(click).toHaveBeenCalledTimes(1);
    expect(appendChild).toHaveBeenCalledWith(anchor);
    expect(removeChild).toHaveBeenCalledWith(anchor);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:fake-url");
  });

  it("returns false when document is missing (SSR-safe)", () => {
    vi.stubGlobal("document", undefined);
    expect(triggerBrowserDownload("x", "y.csv", "text/csv")).toBe(false);
  });
});

// --- buildCopyLinkActionSpec -----------------------------------------

describe("buildCopyLinkActionSpec", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns a copy_link spec with default label", () => {
    const spec: ChartShellActionSpec = buildCopyLinkActionSpec();
    expect(spec.id).toBe("copy_link");
    expect(spec.label).toBe("Copy link");
    expect(typeof spec.on_invoke).toBe("function");
  });

  it("honours a custom label", () => {
    const spec = buildCopyLinkActionSpec({ label: "Share link" });
    expect(spec.label).toBe("Share link");
  });

  it("uses resolve_href override when supplied", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const onResult = vi.fn();
    const spec = buildCopyLinkActionSpec({
      resolve_href: () => "https://override.test/x",
      on_result: onResult,
    });
    spec.on_invoke();
    // Flush microtasks so the async handler resolves before assertions.
    await Promise.resolve();
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith("https://override.test/x");
    expect(onResult).toHaveBeenCalledWith({
      ok: true,
      href: "https://override.test/x",
      fallback_used: false,
    });
  });

  it("falls back to window.location.href when no resolver is provided", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    vi.stubGlobal("window", { location: { href: "https://wnd.test/route" } });
    const spec = buildCopyLinkActionSpec();
    spec.on_invoke();
    await Promise.resolve();
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith("https://wnd.test/route");
  });
});

// --- buildViewDataActionSpec -----------------------------------------

describe("buildViewDataActionSpec", () => {
  beforeEach(() => {
    const anchor = {
      href: "",
      download: "",
      style: {} as Record<string, string>,
      click: vi.fn(),
    };
    vi.stubGlobal("document", {
      createElement: vi.fn().mockReturnValue(anchor),
      body: { appendChild: vi.fn(), removeChild: vi.fn() },
    });
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn().mockReturnValue("blob:test"),
      revokeObjectURL: vi.fn(),
    });
    vi.stubGlobal(
      "Blob",
      class FakeBlob {
        constructor(
          public parts: BlobPart[],
          public opts: BlobPropertyBag,
        ) {}
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns a view_data spec with the supplied filename and default label", () => {
    const spec = buildViewDataActionSpec({
      filename: "data.csv",
      resolve_rows: () => ({ header: ["a"], rows: [["1"]] }),
    });
    expect(spec.id).toBe("view_data");
    expect(spec.label).toBe("View data");
  });

  it("invokes resolve_rows lazily at click time", () => {
    const resolve_rows = vi.fn().mockReturnValue({
      header: ["x"],
      rows: [["1"], ["2"]],
    });
    const spec = buildViewDataActionSpec({
      filename: "x.csv",
      resolve_rows,
    });
    expect(resolve_rows).not.toHaveBeenCalled();
    spec.on_invoke();
    expect(resolve_rows).toHaveBeenCalledTimes(1);
  });

  it("calls on_result with download outcome", () => {
    const onResult = vi.fn();
    const spec = buildViewDataActionSpec({
      filename: "data.csv",
      resolve_rows: () => ({ header: ["a"], rows: [["1"]] }),
      on_result: onResult,
    });
    spec.on_invoke();
    expect(onResult).toHaveBeenCalledWith(true);
  });
});
