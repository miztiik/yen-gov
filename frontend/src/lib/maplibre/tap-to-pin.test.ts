import { describe, it, expect } from "vitest";

import { resolveTapAction } from "./tap-to-pin";

describe("resolveTapAction", () => {
  it("pins on the first tap of a feature on a coarse-pointer device", () => {
    expect(
      resolveTapAction({
        tapToPin: true,
        coarsePointer: true,
        pinnedKey: null,
        key: 42,
      }),
    ).toBe("pin");
  });

  it("navigates on a second tap of the already-pinned feature", () => {
    expect(
      resolveTapAction({
        tapToPin: true,
        coarsePointer: true,
        pinnedKey: 42,
        key: 42,
      }),
    ).toBe("navigate");
  });

  it("pins when tapping a different feature than the pinned one", () => {
    expect(
      resolveTapAction({
        tapToPin: true,
        coarsePointer: true,
        pinnedKey: 42,
        key: 7,
      }),
    ).toBe("pin");
  });

  it("always navigates on a fine-pointer (desktop) device", () => {
    expect(
      resolveTapAction({
        tapToPin: true,
        coarsePointer: false,
        pinnedKey: null,
        key: 42,
      }),
    ).toBe("navigate");
  });

  it("always navigates when the consumer did not opt in", () => {
    expect(
      resolveTapAction({
        tapToPin: false,
        coarsePointer: true,
        pinnedKey: null,
        key: 42,
      }),
    ).toBe("navigate");
  });

  it("handles string keys", () => {
    expect(
      resolveTapAction({
        tapToPin: true,
        coarsePointer: true,
        pinnedKey: "tn_12",
        key: "tn_12",
      }),
    ).toBe("navigate");
    expect(
      resolveTapAction({
        tapToPin: true,
        coarsePointer: true,
        pinnedKey: "tn_12",
        key: "tn_13",
      }),
    ).toBe("pin");
  });
});
