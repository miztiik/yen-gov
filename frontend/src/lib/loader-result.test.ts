import { describe, expect, it, vi, afterEach } from "vitest";
import { describeFailure } from "./loader-result";

describe("describeFailure", () => {
  afterEach(() => vi.restoreAllMocks());

  it("maps manifest fetch failure to catalogue-unavailable copy", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(describeFailure(new Error("manifest fetch failed: 500 Server Error"))).toMatch(
      /data catalogue/i,
    );
  });

  it("maps unknown table_id to dataset-not-available copy", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(describeFailure(new Error("manifest: table_id not found: foo"))).toMatch(
      /not available/i,
    );
  });

  it("maps HTTP 404 to fetch-failed copy", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(describeFailure(new Error("fetch parquet: HTTP 404"))).toMatch(/could not be fetched/i);
  });

  it("maps duckdb/wasm errors to start-database copy", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(describeFailure(new Error("duckdb worker failed to start"))).toMatch(
      /in-browser database/i,
    );
  });

  it("falls back to the generic citizen-readable copy", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    expect(describeFailure(new Error("something weird"))).toMatch(/could not load right now/i);
  });

  it("never leaks a raw stack trace into the citizen-facing string", () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const stacky = new Error("boom\n    at Foo.bar (file:///x.js:10:1)\n    at quux");
    const msg = describeFailure(stacky);
    expect(msg).not.toMatch(/at /);
    expect(msg).not.toMatch(/file:\/\//);
    expect(msg).not.toMatch(/\.js:/);
  });

  it("logs the raw reason to console.warn for devs", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    describeFailure(new Error("technical detail"));
    expect(warn).toHaveBeenCalledWith("[duckdb-loader] failure:", "technical detail");
  });
});
