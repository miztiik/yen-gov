<!--
  RecognitionStrip - citizen-framing annotation strip rendered above the
  LS chart section on /parties/<slug>.

  Plan-doc: TODO/20260613-party-deferred-followups-plan.md PR-2.
  Helper:   ./recognition-strip.ts (pure; vitest pins the 5 verbatim
            strip texts).

  Visual treatment (Citizen 2d OVERRIDES Jony 1b):
    Plain italic paragraph with a small Info icon prefix. NOT a
    slate-50 callout box - citizen test showed the box read as a
    "warning" or "ad" rather than the soft footnote the editor
    intended. The italic text + understated icon registers as
    background context, which is exactly what a recognition-flip
    annotation should feel like.

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
  }
  let { party_id }: Props = $props();

  const strip = $derived(recognitionStripFor(party_id));
  const segments = $derived(strip ? parseInlineLinks(strip.body_md) : []);
</script>

{#if strip}
  <p
    class="text-[13px] text-slate-600 italic mb-3 flex items-start gap-1.5"
    data-testid="party-recognition-strip"
    data-kind={strip.kind}
  >
    <TopicIcon
      name="info"
      cls="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-slate-400"
    />
    <span>
      {#each segments as seg, i (i)}
        {#if seg.type === "link"}
          <a href={seg.href} class="text-sky-600 hover:underline">{seg.value}</a>
        {:else}{seg.value}{/if}
      {/each}
    </span>
  </p>
{/if}
