// Unit tests for the pure helpers in india-pc-map-helpers.ts.
//
// Focus: `pcDelimYearForLsEvent` - the era-gating rule that decides
// whether a national Parliament event has a PC-level boundary layer and
// therefore whether the NationalElection route shows its Constituencies
// + Equal-seats choropleth toggles. Pre-2009 events (1962/1989/1991/...)
// have no PC boundary layer; gating on this prevents an all-grey map
// keyed to 2024 boundaries that never existed for those elections.
//
// Repo vitest doctrine: node-env, no jsdom, no component mount - the
// rule lives in a pure module precisely so it can be tested here.

import { describe, it, expect } from "vitest";
import {
  pcDelimYearForLsEvent,
  pcUniqueId,
  buildPartyKeyToPid,
  hiddenPidSet,
} from "./india-pc-map-helpers";

describe("pcDelimYearForLsEvent", () => {
  it("maps LS 2024 (and later) to the 2024 delimitation", () => {
    expect(pcDelimYearForLsEvent("general-2024")).toBe(2024);
    expect(pcDelimYearForLsEvent("general-2029")).toBe(2024);
  });

  it("maps LS 2009 / 2014 / 2019 to the 2008 delimitation", () => {
    expect(pcDelimYearForLsEvent("general-2009")).toBe(2008);
    expect(pcDelimYearForLsEvent("general-2014")).toBe(2008);
    expect(pcDelimYearForLsEvent("general-2019")).toBe(2008);
  });

  it("returns null for pre-2009 events (no PC boundary layer)", () => {
    // These are the partial-coverage historical events: the per-state
    // choropleth still draws (greying states with no rows), but a PC
    // choropleth has no boundary layer to join against.
    expect(pcDelimYearForLsEvent("general-2004")).toBeNull();
    expect(pcDelimYearForLsEvent("general-1991")).toBeNull();
    expect(pcDelimYearForLsEvent("general-1989")).toBeNull();
    expect(pcDelimYearForLsEvent("general-1962")).toBeNull();
  });

  it("returns null for nullish input", () => {
    expect(pcDelimYearForLsEvent(null)).toBeNull();
    expect(pcDelimYearForLsEvent(undefined)).toBeNull();
    expect(pcDelimYearForLsEvent("")).toBeNull();
  });

  it("returns null for non-general slugs and malformed years", () => {
    expect(pcDelimYearForLsEvent("assembly-2024")).toBeNull();
    expect(pcDelimYearForLsEvent("AcGenApr2021")).toBeNull();
    expect(pcDelimYearForLsEvent("general-abc")).toBeNull();
    expect(pcDelimYearForLsEvent("general-204")).toBeNull(); // 3 digits
    expect(pcDelimYearForLsEvent("general-2024-extra")).toBeNull();
  });
});

describe("pcUniqueId", () => {
  it("joins state_code + eci_no with an underscore", () => {
    expect(pcUniqueId("S07", 8)).toBe("S07_8");
  });
});

describe("buildPartyKeyToPid + hiddenPidSet", () => {
  it("bridges PartyBar keys to canonical party_ids and resolves the hidden set", () => {
    const key_to_pid = buildPartyKeyToPid([
      { party_eci_code: "BJP", party_short: "BJP", party_id: "parties.IN.BJP" },
      { party_eci_code: null, party_short: "INC", party_id: "parties.IN.INC" },
    ]);
    expect(key_to_pid.get("BJP")).toBe("parties.IN.BJP");
    expect(key_to_pid.get("INC")).toBe("parties.IN.INC");

    const hidden = hiddenPidSet(new Set(["BJP"]), key_to_pid);
    expect([...hidden]).toEqual(["parties.IN.BJP"]);
  });
});
