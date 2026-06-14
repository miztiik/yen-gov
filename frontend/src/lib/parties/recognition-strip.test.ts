// Vitest for recognition-strip.ts pure helpers.
//
// Pins the 5 verbatim citizen-tested strip texts (plan-doc PR-2). The
// `toBe` assertions are byte-for-byte by design: if a future agent
// edits the strip copy, this test goes red and forces the citizen-test
// rerun (Citizen 2a-2d sign-off) before the change ships.

import { describe, expect, it } from "vitest";

import {
  parseInlineLinks,
  recognitionStripFor,
  type RecognitionStripContent,
} from "./recognition-strip";

describe("recognitionStripFor - 5 citizen-tested verbatim strips", () => {
  it("AAP - recognition-flip strip", () => {
    const got = recognitionStripFor("parties.IN.AAP");
    expect(got).not.toBeNull();
    const strip = got as RecognitionStripContent;
    expect(strip.kind).toBe("recognition-flip");
    expect(strip.party_id).toBe("parties.IN.AAP");
    expect(strip.body_md).toBe(
      "AAP became an ECI-recognised national party in 2024. From that " +
        "point onwards they could use the broom symbol on every Indian " +
        "ballot, got free Doordarshan time during national elections, " +
        "and could spend more per campaign. The numbers below count " +
        "both before-2024 and after-2024 elections.",
    );
  });

  it("SS_UBT - split-child strip with cross-link to /parties/shs", () => {
    const got = recognitionStripFor("parties.IN.SS_UBT");
    expect(got).not.toBeNull();
    const strip = got as RecognitionStripContent;
    expect(strip.kind).toBe("split-child");
    expect(strip.party_id).toBe("parties.IN.SS_UBT");
    expect(strip.body_md).toBe(
      "This is Shiv Sena (UBT) led by Uddhav Thackeray, created in " +
        "2023 when the Election Commission ruled on the 2022 split of " +
        "the original Shiv Sena. The numbers below count only " +
        "post-split elections. For the pre-split history, see " +
        "[Shiv Sena](/parties/shs).",
    );
  });

  it("NCP_SP - split-child strip with cross-link to /parties/ncp", () => {
    const got = recognitionStripFor("parties.IN.NCP_SP");
    expect(got).not.toBeNull();
    const strip = got as RecognitionStripContent;
    expect(strip.kind).toBe("split-child");
    expect(strip.party_id).toBe("parties.IN.NCP_SP");
    expect(strip.body_md).toBe(
      "This is NCP (Sharadchandra Pawar) led by Sharad Pawar, " +
        "created in 2024 when the Election Commission ruled on the " +
        "2023 split of the original NCP. The numbers below count only " +
        "post-split elections. For the pre-split history, see " +
        "[Nationalist Congress Party](/parties/ncp).",
    );
  });

  it("SHS - rump strip with cross-link to /parties/ss-ubt", () => {
    const got = recognitionStripFor("parties.IN.SHS");
    expect(got).not.toBeNull();
    const strip = got as RecognitionStripContent;
    expect(strip.kind).toBe("rump");
    expect(strip.party_id).toBe("parties.IN.SHS");
    expect(strip.body_md).toBe(
      "In 2022 a faction split off from Shiv Sena and was later " +
        "granted the name and symbol by the Election Commission in " +
        "2023. The sharp drop in the bar chart from 2024 onwards is " +
        "because the breakaway faction ([Shiv Sena (UBT)](/parties/ss-ubt), " +
        "led by Uddhav Thackeray) took many older voters with it.",
    );
  });

  it("NCP - rump strip with cross-link to /parties/ncp-sp", () => {
    const got = recognitionStripFor("parties.IN.NCP");
    expect(got).not.toBeNull();
    const strip = got as RecognitionStripContent;
    expect(strip.kind).toBe("rump");
    expect(strip.party_id).toBe("parties.IN.NCP");
    expect(strip.body_md).toBe(
      "In 2023 a faction split off from NCP and was later granted " +
        "the name and clock symbol by the Election Commission in 2024. " +
        "The bar chart from 2024 onwards counts only the post-split " +
        "entity. For the breakaway faction (with Sharad Pawar), see " +
        "[NCP (Sharadchandra Pawar)](/parties/ncp-sp).",
    );
  });

  it("BJP - lineage strip with 2 cross-links (BJS + JNP) per Hans 3b verdict", () => {
    // PR-10 of TODO/20260613-party-deferred-followups-plan.md.
    // Verbatim Hans 3b verdict text: do NOT paraphrase. The /parties/jnp
    // link is forward-looking (the parties.IN.JNP row is minted by the
    // historical-parties seed PR per umbrella plan section 11); the
    // /parties/bjs link resolves today.
    const got = recognitionStripFor("parties.IN.BJP");
    expect(got).not.toBeNull();
    const strip = got as RecognitionStripContent;
    expect(strip.kind).toBe("lineage");
    expect(strip.party_id).toBe("parties.IN.BJP");
    expect(strip.body_md).toBe(
      "BJP was founded in April 1980 after the dissolution of the " +
        "Janata Party. Its institutional lineage runs " +
        "[Bharatiya Jana Sangh](/parties/bjs) (1951-1977) -> " +
        "[Janata Party](/parties/jnp) (1977-1980) -> BJP " +
        "(1980-present). The chart shows BJP only from its first " +
        "contested cycle in 1984; for 1952-1977 see Bharatiya Jana " +
        "Sangh, for the 1977 LS see Janata Party.",
    );
  });
});

describe("recognitionStripFor - null for non-special parties", () => {
  it("returns null for INC (regression: most parties have no strip)", () => {
    expect(recognitionStripFor("parties.IN.INC")).toBeNull();
  });

  it("returns null for the IND sentinel", () => {
    // Sentinels get the sentinel-framing strip from Party.svelte's
    // `sentinelFraming()`, not this recognition-flip surface. The
    // Party.svelte `{#if !meta.is_sentinel}` guard ALSO blocks the
    // strip from rendering, but the helper returning null is a
    // defence-in-depth guarantee.
    expect(recognitionStripFor("parties.IN.IND")).toBeNull();
  });

  it("returns null for the NOTA sentinel", () => {
    expect(recognitionStripFor("parties.IN.NOTA")).toBeNull();
  });

  it("returns null for the UNK sentinel (no /parties page at all)", () => {
    expect(recognitionStripFor("parties.IN.UNK")).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(recognitionStripFor("")).toBeNull();
  });
});

describe("parseInlineLinks - inline markdown-link splitter", () => {
  it("returns empty array for empty input", () => {
    expect(parseInlineLinks("")).toEqual([]);
  });

  it("returns a single text segment for link-free input", () => {
    expect(parseInlineLinks("plain text only")).toEqual([
      { type: "text", value: "plain text only" },
    ]);
  });

  it("splits a single inline link mid-string into text + link + text", () => {
    expect(parseInlineLinks("see [Shiv Sena](/parties/shs) for more")).toEqual([
      { type: "text", value: "see " },
      { type: "link", value: "Shiv Sena", href: "/parties/shs" },
      { type: "text", value: " for more" },
    ]);
  });

  it("emits no trailing text segment when the link is at end-of-string", () => {
    expect(parseInlineLinks("end [X](/y)")).toEqual([
      { type: "text", value: "end " },
      { type: "link", value: "X", href: "/y" },
    ]);
  });

  it("emits no leading text segment when the link is at start-of-string", () => {
    expect(parseInlineLinks("[X](/y) start")).toEqual([
      { type: "link", value: "X", href: "/y" },
      { type: "text", value: " start" },
    ]);
  });

  it("handles the SHS rump body shape (inline link mid-parenthetical)", () => {
    const got = parseInlineLinks(
      "drop because the breakaway faction ([Shiv Sena (UBT)](/parties/ss-ubt), led by Uddhav) took many.",
    );
    expect(got).toEqual([
      { type: "text", value: "drop because the breakaway faction (" },
      {
        type: "link",
        value: "Shiv Sena (UBT)",
        href: "/parties/ss-ubt",
      },
      { type: "text", value: ", led by Uddhav) took many." },
    ]);
  });
});
