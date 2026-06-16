<!--
  RecognitionStrip - citizen-framing annotation strip rendered above the
  LS chart section on /parties/<slug>.

  Plan-doc: TODO/20260613-party-deferred-followups-plan.md PR-2.
              TODO/20260615-party-page-citizen-fixes-plan.md  PR-5 D2
              (adds optional `symbol_url` prop to render the ECI
              party-symbol image inline before the recognition text;
              falls back to the existing TopicIcon info-glyph when
              null).
  Helper:   ./recognition-strip.ts (pure; vitest pins the 5 verbatim
            strip texts).

  Visual treatment (Citizen 2d OVERRIDES Jony 1b):
    Plain italic paragraph with a small Info icon prefix. NOT a
    slate-50 callout box - citizen test showed the box read as a
    "warning" or "ad" rather than the soft footnote the editor
    intended. The italic text + understated icon registers as
    background context, which is exactly what a recognition-flip
    annotation should feel like.

  Leading glyph (PR-5 D2):
    When `symbol_url` is non-null, render the ECI party-symbol bitmap
    (e.g. lotus / broom / hand) as a small `<img>` before the text.
    These are real bitmaps on transparent (NOT Lucide-style
    `currentColor` SVGs), so the D3 empty-square trap does not apply.
    When `symbol_url` is null (NCP and other special parties without a
    symbol_asset; sentinel-style fallbacks), fall back to the existing
    TopicIcon info-glyph. Render-nothing on the outer `{#if strip}`
    block survives unchanged so non-special parties stay clean.

  Icon: TopicIcon name="info" (registered in frontend/public/icons/
    info.svg; existing consumers AboutThisData.svelte + About.svelte).
    `lucide-svelte` is NOT in package.json - the project's icon
    surface is the TopicIcon registry per ADR + plan §21.10.

  Inline links: body_md carries `[label](/parties/<slug>)` markdown
    tokens; parseInlineLinks (pure helper in recognition-strip.ts)
    splits into text + link segments which the template walks. Per
    Jony 1e: NO pre-rendered <a> elements in the helper - keeps the
    v2 CSV migration shape clean (one `recognition_strip_md` column,
    no HTML escaping).

  Render-nothing contract: when recognitionStripFor(party_id) returns
    null (any non-special party, or any sentinel), the component
    renders an empty `{#if}` block - no `<p>`, no whitespace, nothing.
    Party.svelte ALSO gates on `!meta.is_sentinel` so the strip never
    even mounts on sentinel pages; the helper-level null is
    defence-in-depth.
-->
<script lang="ts">
  import TopicIcon from "../TopicIcon.svelte";
  import {
    parseInlineLinks,
    recognitionStripFor,
  } from "./recognition-strip";

  interface Props {
    party_id: string;
    /** Resolved ECI party-symbol image URL (output of
     *  `glyphUrlFor(symbol_asset)`). When non-null, rendered as a
     *  small `<img>` before the recognition text; when null, falls
     *  back to the TopicIcon info-glyph. Defaults to null so existing
     *  callers (none today after PR-5 D2 wires Party.svelte) keep the
     *  pre-PR-5 visual exactly. */
    symbol_url?: string | null;
  }
  let { party_id, symbol_url = null }: Props = $props();

  const strip = $derived(recognitionStripFor(party_id));
  const segments = $derived(strip ? parseInlineLinks(strip.body_md) : []);
</script>

{#if strip}
  <p
    class="text-[13px] text-slate-600 italic mb-3 flex items-start gap-1.5"
    data-testid="party-recognition-strip"
    data-kind={strip.kind}
  >
    {#if symbol_url}
      <img
        src={symbol_url}
        alt=""
        class="w-4 h-4 inline-block mr-1.5 align-middle flex-shrink-0"
        data-testid="party-recognition-symbol-img"
        loading="lazy"
      />
    {:else}
      <TopicIcon
        name="info"
        cls="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-slate-400"
      />
    {/if}
    <span>
      {#each segments as seg, i (i)}
        {#if seg.type === "link"}
          <a href={seg.href} class="text-sky-600 hover:underline">{seg.value}</a>
        {:else}{seg.value}{/if}
      {/each}
    </span>
  </p>
{/if}
