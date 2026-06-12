// Unit tests for pickEventPanelState (fix/state-parl-seats-0-loader).
//
// The function is pure; node-env vitest, no @testing-library/svelte
// mount (project doctrine; see Skeleton.test.ts header).

import { describe, expect, it } from "vitest";

import type { LoaderResult } from "../loader-result";
import { pickEventPanelState } from "./election-result-panel";

describe("pickEventPanelState", () => {
  it("returns 'loading' when the LoaderResult status is 'loading' regardless of count", () => {
    const result: LoaderResult<number[]> = { status: "loading" };
    expect(pickEventPanelState(result, 0)).toBe("loading");
    expect(pickEventPanelState(result, 48)).toBe("loading");
  });

  it("returns 'error' when the LoaderResult status is 'failed'", () => {
    const result: LoaderResult<number[]> = {
      status: "failed",
      reason: "anything",
    };
    expect(pickEventPanelState(result, 0)).toBe("error");
    // count is irrelevant when failed; pin both arms anyway
    expect(pickEventPanelState(result, 99)).toBe("error");
  });

  it("returns 'pending' when the LoaderResult status is 'partial'", () => {
    const result: LoaderResult<number[]> = {
      status: "partial",
      data: [],
      reason: "not_published",
    };
    expect(pickEventPanelState(result, 0)).toBe("pending");
  });

  it("returns 'empty' when status is 'ok' and the filtered count is 0", () => {
    const result: LoaderResult<number[]> = {
      status: "ok",
      data: [],
    };
    expect(pickEventPanelState(result, 0)).toBe("empty");
  });

  it("returns 'empty' for status 'ok' when the raw loader has rows but the local filter narrows them to 0", () => {
    // This pins the "NATIONAL-PC fetched 542 rows but state filter
    // matched 0" arm. The contract is: the consumer narrows BEFORE
    // calling pickEventPanelState; the helper only sees the post-filter
    // count.
    const result: LoaderResult<number[]> = {
      status: "ok",
      data: [1, 2, 3, 4, 5],
    };
    expect(pickEventPanelState(result, 0)).toBe("empty");
  });

  it("returns 'data' when status is 'ok' and the filtered count is >= 1", () => {
    const result: LoaderResult<number[]> = {
      status: "ok",
      data: [1, 2, 3],
    };
    expect(pickEventPanelState(result, 3)).toBe("data");
    expect(pickEventPanelState(result, 1)).toBe("data");
    expect(pickEventPanelState(result, 48)).toBe("data");
  });

  it("does NOT collapse 'loading' to 'empty' even when filtered count is 0 - the regression oracle", () => {
    // This is the exact bug the PR fixes: prior to the fix the
    // template branched on `seat_rows.length === 0` and rendered
    // "No constituency rows yet" during the loader-in-flight window,
    // misleading citizens into thinking data was missing. Pinning the
    // distinction here so a future refactor cannot silently fold
    // `loading` and `empty` together.
    const loadingState: LoaderResult<number[]> = { status: "loading" };
    const emptyOkState: LoaderResult<number[]> = {
      status: "ok",
      data: [],
    };
    expect(pickEventPanelState(loadingState, 0)).not.toBe(
      pickEventPanelState(emptyOkState, 0),
    );
    expect(pickEventPanelState(loadingState, 0)).toBe("loading");
    expect(pickEventPanelState(emptyOkState, 0)).toBe("empty");
  });
});
