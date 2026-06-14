// Pure helper: per-party recognition-flip / split-child / rump annotation
// strip content for the per-party detail page (/parties/<slug>).
//
// Plan-doc: TODO/20260613-party-deferred-followups-plan.md PR-2.
// Synthesis: Hans 2a-2d + Jony 1a-1e + Citizen 2a-2d.
//   - Citizen 2d overrides Jony 1b on visual treatment: plain italic + small
//     Info icon, NOT a slate-50 callout box.
//   - Jony 1e (v2 CSV migration shape): the body carries inline
//     `[label](/parties/<slug>)` markdown link tokens, NOT pre-rendered <a>
//     elements. Pre-shaped for the future per-party-row CSV with a single
//     `recognition_strip_md` column.
//
// The 5 strip texts are citizen-tested verbatim copy (plan-doc section 4).
// DO NOT paraphrase. The vitest test pins each body_md byte-for-byte.

/** Four citizen-recognised flavours of recognition / lineage annotation.
 *
 *  `lineage` = founded-from-a-now-dissolved-parent shape (e.g. BJP
 *  founded 1980 after Janata Party dissolved). Cited as a sibling of
 *  `split-child` (whose parent is still live but split) and `rump`
 *  (whose own pre-split identity is what continues). PR-10 of
 *  TODO/20260613-party-deferred-followups-plan.md (Hans 3b).
 */
export type RecognitionKind =
  | "rump"
  | "split-child"
  | "recognition-flip"
  | "lineage";

/** Renderable content for ONE party's annotation strip. The component
 *  walks `body_md` for inline `[label](/parties/<slug>)` tokens via
 *  `parseInlineLinks`; no other markdown is supported. */
export interface RecognitionStripContent {
  /** Citizen-framing flavour. Drives the `data-kind` attribute so
   *  Tier-A / Playwright tests can assert the right shape lit up. */
  kind: RecognitionKind;
  /** Verbatim citizen-tested body copy. Carries inline
   *  `[label](/parties/<slug>)` markdown links (see `parseInlineLinks`). */
  body_md: string;
  /** Echoed back for caller convenience (Svelte template doesn't need
   *  to also stash `party_id` in a local). */
  party_id: string;
}

/**
 * Returns the recognition-strip content for the 6 special party_ids
 * (AAP / SS_UBT / NCP_SP / SHS / NCP / BJP); returns `null` for
 * everyone else so the component renders nothing.
 *
 * Slug shape per `slug.ts::partyIdToSlug`: lowercased tail with `_`
 * -> `-`. Hand-verified against the worktree's parties.csv:
 *   - parties.IN.AAP    -> /parties/aap
 *   - parties.IN.SS_UBT -> /parties/ss-ubt
 *   - parties.IN.NCP_SP -> /parties/ncp-sp
 *   - parties.IN.SHS    -> /parties/shs
 *   - parties.IN.NCP    -> /parties/ncp
 *   - parties.IN.BJP    -> /parties/bjp (lineage strip; cross-links to
 *                                         parties.IN.BJS and the future
 *                                         parties.IN.JNP per Hans 3b)
 *
 * BJP body_md cross-link targets:
 *   - /parties/bjs RESOLVES today (parties.IN.BJS exists in
 *     parties.csv).
 *   - /parties/jnp is forward-looking; the parties.IN.JNP entity row
 *     is minted by the historical-parties seed PR (umbrella plan-doc
 *     TODO/20260613 section 11). The link is shipped now per Hans 3b
 *     verbatim so the strip lights up automatically when JNP lands
 *     without re-editing this helper.
 */
export function recognitionStripFor(
  party_id: string,
): RecognitionStripContent | null {
  switch (party_id) {
    case "parties.IN.AAP":
      return {
        kind: "recognition-flip",
        party_id,
        body_md:
          "AAP became an ECI-recognised national party in 2024. From that " +
          "point onwards they could use the broom symbol on every Indian " +
          "ballot, got free Doordarshan time during national elections, " +
          "and could spend more per campaign. The numbers below count " +
          "both before-2024 and after-2024 elections.",
      };
    case "parties.IN.SS_UBT":
      return {
        kind: "split-child",
        party_id,
        body_md:
          "This is Shiv Sena (UBT) led by Uddhav Thackeray, created in " +
          "2023 when the Election Commission ruled on the 2022 split of " +
          "the original Shiv Sena. The numbers below count only " +
          "post-split elections. For the pre-split history, see " +
          "[Shiv Sena](/parties/shs).",
      };
    case "parties.IN.NCP_SP":
      return {
        kind: "split-child",
        party_id,
        body_md:
          "This is NCP (Sharadchandra Pawar) led by Sharad Pawar, " +
          "created in 2024 when the Election Commission ruled on the " +
          "2023 split of the original NCP. The numbers below count only " +
          "post-split elections. For the pre-split history, see " +
          "[Nationalist Congress Party](/parties/ncp).",
      };
    case "parties.IN.SHS":
      return {
        kind: "rump",
        party_id,
        body_md:
          "In 2022 a faction split off from Shiv Sena and was later " +
          "granted the name and symbol by the Election Commission in " +
          "2023. The sharp drop in the bar chart from 2024 onwards is " +
          "because the breakaway faction ([Shiv Sena (UBT)](/parties/ss-ubt), " +
          "led by Uddhav Thackeray) took many older voters with it.",
      };
    case "parties.IN.NCP":
      return {
        kind: "rump",
        party_id,
        body_md:
          "In 2023 a faction split off from NCP and was later granted " +
          "the name and clock symbol by the Election Commission in 2024. " +
          "The bar chart from 2024 onwards counts only the post-split " +
          "entity. For the breakaway faction (with Sharad Pawar), see " +
          "[NCP (Sharadchandra Pawar)](/parties/ncp-sp).",
      };
    case "parties.IN.BJP":
      return {
        kind: "lineage",
        party_id,
        body_md:
          "BJP was founded in April 1980 after the dissolution of the " +
          "Janata Party. Its institutional lineage runs " +
          "[Bharatiya Jana Sangh](/parties/bjs) (1951-1977) -> " +
          "[Janata Party](/parties/jnp) (1977-1980) -> BJP " +
          "(1980-present). The chart shows BJP only from its first " +
          "contested cycle in 1984; for 1952-1977 see Bharatiya Jana " +
          "Sangh, for the 1977 LS see Janata Party.",
      };
    default:
      return null;
  }
}

/** One segment of a body_md string after splitting on inline markdown
 *  links. `text` segments render as plain text inside the `<p>`; `link`
 *  segments render as `<a href={href}>{value}</a>`. */
export type InlineLinkSegment =
  | { type: "text"; value: string }
  | { type: "link"; value: string; href: string };

/**
 * Splits a `body_md` string into a sequence of text + link segments.
 * Supports ONLY the `[label](href)` inline-link grammar; everything
 * else passes through unchanged.
 *
 * Pure + deterministic + idempotent on link-free input:
 *   parseInlineLinks("plain")
 *     -> [{ type: "text", value: "plain" }]
 *   parseInlineLinks("see [X](/y) ok")
 *     -> [{ type: "text", value: "see " },
 *         { type: "link", value: "X", href: "/y" },
 *         { type: "text", value: " ok" }]
 *
 * Empty input returns an empty array (the component skips rendering).
 */
export function parseInlineLinks(md: string): InlineLinkSegment[] {
  if (md === "") return [];
  const segments: InlineLinkSegment[] = [];
  const re = /\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(md)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: "text", value: md.slice(lastIndex, match.index) });
    }
    segments.push({ type: "link", value: match[1]!, href: match[2]! });
    lastIndex = re.lastIndex;
  }
  if (lastIndex < md.length) {
    segments.push({ type: "text", value: md.slice(lastIndex) });
  }
  return segments;
}
