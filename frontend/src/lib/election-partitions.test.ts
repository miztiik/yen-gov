import { describe, expect, it } from "vitest";

import { electionStatePartition } from "./election-partitions";

describe("electionStatePartition", () => {
  it("maps ECI state codes to the current election fact partition token", () => {
    expect(electionStatePartition("S22")).toBe("tamil-nadu");
    expect(electionStatePartition("U05")).toBe("delhi");
  });
});
