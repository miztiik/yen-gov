import { describe, expect, it } from "vitest";
import { padResults } from "./StrongholdDotStrip.svelte";

describe("padResults (StrongholdDotStrip)", () => {
  it("pads short arrays on the LEFT with DNC (right-aligns most recent)", () => {
    expect(padResults(["W", "W", "L"], 10)).toEqual([
      "DNC", "DNC", "DNC", "DNC", "DNC", "DNC", "DNC", "W", "W", "L",
    ]);
  });

  it("returns the array verbatim when its length equals cell_count", () => {
    const exact: ("W" | "L")[] = ["W", "L", "W", "L", "W", "L", "W", "L", "W", "L"];
    expect(padResults(exact, 10)).toEqual(exact);
  });

  it("right-windows longer arrays (drops oldest, keeps most recent)", () => {
    const long: ("W" | "L")[] = [
      "L", "L", "L", "L", "W", "W", "W", "W", "W", "W", "W", "W",
    ];
    // 12 inputs, cell_count=10 -> drop first 2 ("L","L") and keep last 10
    expect(padResults(long, 10)).toEqual([
      "L", "L", "W", "W", "W", "W", "W", "W", "W", "W",
    ]);
  });

  it("pads to the requested cell_count (not hardcoded to 10)", () => {
    expect(padResults(["W"], 5)).toEqual(["DNC", "DNC", "DNC", "DNC", "W"]);
  });

  it("returns an all-DNC strip for an empty input", () => {
    expect(padResults([], 10)).toEqual([
      "DNC", "DNC", "DNC", "DNC", "DNC", "DNC", "DNC", "DNC", "DNC", "DNC",
    ]);
  });
});
