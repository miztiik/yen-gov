// PR-1 vitest for PartyTooltip's pure view-model projection.
//
// Per project doctrine (Skeleton.test.ts precedent + memories note):
// the @testing-library/svelte mounting library is NOT installed, so
// node-env vitest cannot drive Svelte template render. The testable
// surface is `buildTooltipViewModel` + `clampTooltipPlacement` exported
// from PartyTooltip.svelte's `<script module>`. The §13 in-browser
// smoke on /dev/charts (a PartyPill consumer) verifies the visual
// render once PR-2 wires the tooltip into citizen-facing routes.
//
// Brief items (a)..(f) are all covered through the view-model:
//   (a) symbol present  -> view.hasSymbol === true, view.symbolAsset !== ""
//   (b) symbol absent   -> view.hasSymbol === false (no placeholder)
//   (c) founded line    -> view.foundedLine === "Founded YYYY" iff populated
//   (d) wiki link       -> view.wikipediaUrl is non-null when populated;
//                          the template renders <a target="_blank" rel="noopener noreferrer">
//                          (the rel/target attributes are baked into the
//                          .svelte template; smoke verifies render).
//   (e) loading state   -> view.isLoading true means render only the spinner
//   (f) sentinel        -> IND/NOTA suppress wiki link AND founded line

import { describe, expect, it } from "vitest";
import {
  buildTooltipViewModel,
  clampTooltipPlacement,
} from "./PartyTooltip.svelte";
import type { PartyMeta } from "../view-models/parties";

function mkMeta(overrides: Partial<PartyMeta> = {}): PartyMeta {
  return {
    party_id: "parties.IN.BJP",
    short: "BJP",
    full: "Bharatiya Janata Party",
    founded_year: 1980,
    dissolved_year: null,
    recognition_scope: "national",
    home_state_codes: [],
    symbol_asset: "party-symbols/lotus.svg",
    brand_colour: "#ea580c",
    wikipedia: "https://en.wikipedia.org/wiki/Bharatiya_Janata_Party",
    name_native_script: null,
    aliases: [],
    predecessor_party_ids: [],
    successor_party_ids: [],
    is_sentinel: false,
    leader: null,
    ...overrides,
  };
}

describe("buildTooltipViewModel - loading + missing", () => {
  it("emits an isLoading-only view-model when the loader is in-flight", () => {
    const view = buildTooltipViewModel(null, true);
    expect(view.isLoading).toBe(true);
    expect(view.isMissing).toBe(false);
    expect(view.hasSymbol).toBe(false);
    expect(view.short).toBe("");
    expect(view.full).toBeNull();
    expect(view.foundedLine).toBeNull();
    expect(view.wikipediaUrl).toBeNull();
  });

  it("flags isMissing=true when the loader resolved null (party_id absent from CSV)", () => {
    const view = buildTooltipViewModel(null, false);
    expect(view.isLoading).toBe(false);
    expect(view.isMissing).toBe(true);
    expect(view.hasSymbol).toBe(false);
  });
});

describe("buildTooltipViewModel - (a) symbol present", () => {
  it("flags hasSymbol=true when meta.symbol_asset is a non-empty string", () => {
    const view = buildTooltipViewModel(mkMeta({ symbol_asset: "party-symbols/lotus.svg" }), false);
    expect(view.hasSymbol).toBe(true);
    expect(view.symbolAsset).toBe("party-symbols/lotus.svg");
  });
});

describe("buildTooltipViewModel - (b) symbol absent (no placeholder)", () => {
  it("flags hasSymbol=false when meta.symbol_asset is null (Jony A3 + user 2026-06-12)", () => {
    const view = buildTooltipViewModel(mkMeta({ symbol_asset: null }), false);
    expect(view.hasSymbol).toBe(false);
    expect(view.symbolAsset).toBe("");
  });

  it("flags hasSymbol=false when meta.symbol_asset is empty string", () => {
    // toPartyMeta normalises empty to null upstream, but the
    // view-model guard is defensive against any future loader change.
    const view = buildTooltipViewModel(mkMeta({ symbol_asset: "" }), false);
    expect(view.hasSymbol).toBe(false);
  });
});

describe("buildTooltipViewModel - (c) founded line conditional", () => {
  it('emits "Founded YYYY" when founded_year is populated', () => {
    const view = buildTooltipViewModel(mkMeta({ founded_year: 1980 }), false);
    expect(view.foundedLine).toBe("Founded 1980");
  });

  it("omits the founded line when founded_year is null", () => {
    const view = buildTooltipViewModel(mkMeta({ founded_year: null }), false);
    expect(view.foundedLine).toBeNull();
  });

  it('emits "Dissolved YYYY" when dissolved_year is populated', () => {
    const view = buildTooltipViewModel(
      mkMeta({ founded_year: 1936, dissolved_year: 1996 }),
      false,
    );
    expect(view.dissolvedLine).toBe("Dissolved 1996");
  });

  it("omits the dissolved line when dissolved_year is null", () => {
    const view = buildTooltipViewModel(mkMeta({ dissolved_year: null }), false);
    expect(view.dissolvedLine).toBeNull();
  });
});

describe("buildTooltipViewModel - (d) wiki link", () => {
  it("surfaces wikipediaUrl when meta.wikipedia is populated", () => {
    const view = buildTooltipViewModel(
      mkMeta({ wikipedia: "https://en.wikipedia.org/wiki/Bharatiya_Janata_Party" }),
      false,
    );
    expect(view.wikipediaUrl).toBe(
      "https://en.wikipedia.org/wiki/Bharatiya_Janata_Party",
    );
  });

  it("omits wikipediaUrl when meta.wikipedia is null", () => {
    const view = buildTooltipViewModel(mkMeta({ wikipedia: null }), false);
    expect(view.wikipediaUrl).toBeNull();
  });
});

describe("buildTooltipViewModel - (f) sentinel handling", () => {
  it("suppresses wiki link for sentinel rows even if meta.wikipedia were populated", () => {
    // Sentinels (IND/NOTA) have no wiki entry in real data; the
    // defensive test passes a hypothetical wiki URL and confirms the
    // view-model still strips it.
    const view = buildTooltipViewModel(
      mkMeta({
        party_id: "parties.IN.NOTA",
        short: "NOTA",
        full: "None of the Above",
        founded_year: 2013,
        recognition_scope: "sentinel",
        wikipedia: "https://en.wikipedia.org/wiki/None_of_the_above",
        is_sentinel: true,
      }),
      false,
    );
    expect(view.wikipediaUrl).toBeNull();
  });

  it("suppresses founded line for sentinels (NOTA 2013 is the PUCL ruling, not a founding)", () => {
    const view = buildTooltipViewModel(
      mkMeta({
        party_id: "parties.IN.NOTA",
        short: "NOTA",
        founded_year: 2013,
        recognition_scope: "sentinel",
        is_sentinel: true,
      }),
      false,
    );
    expect(view.foundedLine).toBeNull();
  });

  it("PRESERVES short + full + recognition for sentinels (those ARE meaningful)", () => {
    const view = buildTooltipViewModel(
      mkMeta({
        party_id: "parties.IN.IND",
        short: "IND",
        full: "Independent",
        recognition_scope: "sentinel",
        founded_year: null,
        wikipedia: null,
        is_sentinel: true,
      }),
      false,
    );
    expect(view.short).toBe("IND");
    expect(view.full).toBe("Independent");
    expect(view.recognitionScope).toBe("sentinel");
  });
});

describe("clampTooltipPlacement", () => {
  const cardSize = { width: 280, height: 160 };
  const viewport = { width: 1024, height: 768 };

  it("pins the card below + left-aligned with the anchor by default", () => {
    const anchor = { left: 100, right: 160, top: 100, bottom: 120 };
    const pos = clampTooltipPlacement(anchor, cardSize, viewport);
    // 6px margin below anchor.bottom
    expect(pos.top).toBe(126);
    expect(pos.left).toBe(100);
  });

  it("slides left when the default position would overflow the right edge", () => {
    const anchor = { left: 900, right: 960, top: 100, bottom: 120 };
    const pos = clampTooltipPlacement(anchor, cardSize, viewport);
    // viewport.width 1024 - cardSize.width 280 - edge 4 = 740
    expect(pos.left).toBe(740);
  });

  it("flips above the anchor when the default position would overflow the bottom", () => {
    const anchor = { left: 100, right: 160, top: 700, bottom: 720 };
    const pos = clampTooltipPlacement(anchor, cardSize, viewport);
    // 700 - 160 - 6 = 534
    expect(pos.top).toBe(534);
  });

  it("clamps to viewport edges (left & top) so the card never goes negative", () => {
    const anchor = { left: 0, right: 60, top: 0, bottom: 20 };
    const pos = clampTooltipPlacement(anchor, cardSize, viewport);
    // 4px safety edge: the clamp never lets the card touch the
    // viewport border, so both axes are >= 4.
    expect(pos.left).toBeGreaterThanOrEqual(4);
    expect(pos.top).toBeGreaterThanOrEqual(4);
  });
});

// --- PR-11: leader projection --------------------------------------------
//
// The tooltip body now carries a "President: <name> . since <date>"
// line when the loader resolved a current leader (parties_leadership.csv
// row with empty valid_to). Hidden when null OR when the party is a
// sentinel (Jony A2 sentinel-suppression doctrine extended to leader).

describe("buildTooltipViewModel - (g) leader line projection", () => {
  it("surfaces leader.role + leader.name + formatted since-date when populated", () => {
    const view = buildTooltipViewModel(
      mkMeta({
        leader: {
          name: "Jagat Prakash Nadda",
          role: "President",
          person_wikidata_qid: "Q16193764",
          since: "2020-01-20",
        },
      }),
      false,
    );
    expect(view.leader).not.toBeNull();
    expect(view.leader!.role).toBe("President");
    expect(view.leader!.name).toBe("Jagat Prakash Nadda");
    expect(view.leader!.sinceLabel).toBe("20 Jan 2020");
  });

  it("hides leader when meta.leader is null (no leadership row - the common case)", () => {
    const view = buildTooltipViewModel(mkMeta({ leader: null }), false);
    expect(view.leader).toBeNull();
  });

  it("suppresses leader for sentinel parties (Jony A2 sentinel-suppression doctrine)", () => {
    // Defensive: even if a future Wikidata snapshot bound IND/NOTA to
    // a fake leader, the tooltip MUST NOT render it - sentinels have
    // no leader in the parliamentary sense.
    const view = buildTooltipViewModel(
      mkMeta({
        party_id: "parties.IN.IND",
        short: "IND",
        full: "Independent",
        recognition_scope: "sentinel",
        is_sentinel: true,
        leader: {
          name: "Someone Hypothetical",
          role: "Spokesperson",
          person_wikidata_qid: null,
          since: "2024-01-01",
        },
      }),
      false,
    );
    expect(view.leader).toBeNull();
  });

  it("hides leader when the view-model is loading", () => {
    const view = buildTooltipViewModel(null, true);
    expect(view.leader).toBeNull();
  });

  it("hides leader when meta is missing (loader returned null)", () => {
    const view = buildTooltipViewModel(null, false);
    expect(view.leader).toBeNull();
  });

  it("preserves the raw role string verbatim (open-ended Wikidata position labels)", () => {
    // The CSV `role` column has no enum closure (Wikidata position
    // labels are open-ended); the tooltip MUST render whatever the
    // upstream emits without re-mapping. Verifies the projector does
    // not normalise "General Secretary" -> "President".
    const view = buildTooltipViewModel(
      mkMeta({
        leader: {
          name: "Some Person",
          role: "General Secretary",
          person_wikidata_qid: null,
          since: "2024-04-06",
        },
      }),
      false,
    );
    expect(view.leader!.role).toBe("General Secretary");
  });
});
