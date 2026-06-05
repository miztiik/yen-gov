<script lang="ts">
  // C5 SourceLine (parent plan section 14.3) - one-line
  // `Source: <owner> (as of <vintage>)` chip. The seam every F2b
  // renderer drops into ChartShell's footer or subtitle slot.
  //
  // Doctrine ties:
  //   - Citizen-readable; no truncation.
  //   - When `url` is supplied, renders the line as a link with
  //     `target="_blank"` + `rel="noopener noreferrer"` (the same
  //     pattern the existing SourceList.svelte uses).
  //   - Reads from the 4-field source row shape `{owner, title,
  //     vintage, url}` per parent plan section 7 + the U5
  //     IndicatorDoc precedent.
  //   - Pure presentation leaf: no fetches, no data shaping.
  //   - CLAUDE.md section 0: no aria/role.

  interface Props {
    /** The publisher name (e.g. "Reserve Bank of India").
     *  Mandatory: a source line without a publisher is meaningless. */
    owner: string;
    /** The vintage label (e.g. "2024-25", "March 2024", "as published
     *  2024-11-04"). Citizen-readable. */
    vintage: string;
    /** Optional URL to the publisher's data page. When supplied, the
     *  whole line becomes a link. */
    url?: string | null;
    /** Optional secondary line: the source TITLE (e.g. "Handbook of
     *  Statistics on Indian Economy 2023-24"). Renders on a second
     *  line below the headline source line, in muted ink. */
    title?: string | null;
  }

  const {
    owner,
    vintage,
    url = null,
    title = null,
  }: Props = $props();

  // The headline line: "Source: <owner> (as of <vintage>)". Composed
  // here rather than slot-rendered so the layout collapses cleanly
  // when `url` is null (link) vs supplied (span).
  const headline = $derived(`Source: ${owner} (as of ${vintage})`);
</script>

<div class="source-line" data-component="source-line">
  {#if url}
    <a
      class="source-line__link"
      href={url}
      target="_blank"
      rel="noopener noreferrer"
    >
      {headline}
    </a>
  {:else}
    <span class="source-line__text">{headline}</span>
  {/if}
  {#if title}
    <div class="source-line__title" data-slot="title">{title}</div>
  {/if}
</div>

<style>
  .source-line {
    font-family: var(--font-sans);
    font-size: 11px;
    color: var(--ink-muted);
    line-height: 1.35;
  }
  .source-line__link,
  .source-line__text {
    color: var(--ink-muted);
  }
  .source-line__link {
    text-decoration: underline;
    text-decoration-color: var(--line);
    text-underline-offset: 2px;
  }
  .source-line__link:hover {
    text-decoration-color: var(--ink-muted);
  }
  .source-line__title {
    color: var(--ink-muted);
    margin-top: 1px;
  }
</style>
