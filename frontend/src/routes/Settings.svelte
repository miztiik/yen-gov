<script lang="ts">
  // Settings route — citizen-facing provenance explainer.
  //
  // PR-SYM-6i-pre2 retired the user-override colour-picker UI in favour
  // of a read-only "How party colours are chosen" explainer. Rationale
  // (Jony reductionism + Hans honesty): user overrides had no schema
  // home (no `override_colour` column in dim_parties or any canonical
  // store), persisted only in this browser's localStorage (violates the
  // static-first / no-server-state contract), and would have required a
  // 4th `source: "user-override"` provenance tier that doesn't
  // generalise across devices or sessions.
  //
  // What this page now shows: the 3-tier resolver contract from
  // `lib/colors/resolver.ts`, demonstrated live with one worked example
  // per tier. The swatch + chip on each row are computed by calling
  // `getPartyColor` directly, so the explainer can never drift from the
  // resolver.
  //
  // See: docs/concepts/party-colour-resolution.md
  import {
    getPartyColor,
    type PartyRowForResolver,
  } from "../lib/colors/resolver";
  import { chipFor } from "../lib/colors/chip";
  import TopicIcon from "../lib/TopicIcon.svelte";

  // Three worked examples, one per resolver tier. The party_id + row
  // shape are the same inputs any chart consumer would pass; the
  // resolver decides the tier and returns the hex.
  const examples: ReadonlyArray<{
    party_id: string;
    party_short: string;
    party_full: string;
    row: PartyRowForResolver | null;
    note: string;
  }> = [
    {
      party_id: "parties.IN.AAP",
      party_short: "AAP",
      party_full: "Aam Aadmi Party",
      row: {
        party_id: "parties.IN.AAP",
        brand_colour: { hex: "#0072B0", confidence: "high" },
      },
      note: "Wikipedia-sourced editorial colour. Carried on every party row from dim_parties.",
    },
    {
      party_id: "parties.IN.DMK",
      party_short: "DMK",
      party_full: "Dravida Munnetra Kazhagam",
      row: null,
      note: "Hand-curated iconic colour. Used for parties whose colour the average voter recognises without thinking.",
    },
    {
      party_id: "parties.IN.SP",
      party_short: "SP",
      party_full: "Samajwadi Party (illustrative; fallback example)",
      row: null,
      note: "Deterministic hash of party_id. Decoration only; the label carries the meaning.",
    },
  ];

  const resolved = $derived(
    examples.map((e) => ({
      ...e,
      colour: getPartyColor(e.party_id, e.row),
    })),
  );
</script>

<main class="max-w-3xl mx-auto p-6 space-y-6">
  <header class="space-y-1">
    <h1 class="text-2xl font-bold flex items-center gap-2">
      <TopicIcon name="settings" cls="w-6 h-6 text-slate-500 shrink-0" />
      <span>Settings</span>
    </h1>
    <p class="text-sm text-slate-500">
      How yen-gov chooses the colour for each party on every chart.
    </p>
  </header>

  <section class="bg-white rounded-lg shadow-sm p-5 space-y-4">
    <h2 class="text-sm font-semibold uppercase text-slate-500">
      How party colours are chosen
    </h2>

    <p class="text-sm text-slate-700">
      Every party shown on a chart is coloured by the same three-tier
      resolver. The first tier that has a colour wins; later tiers never
      override an earlier one. The chip next to the swatch tells you which
      tier produced the colour.
    </p>

    <ul class="divide-y border-t border-b border-slate-100">
      {#each resolved as ex (ex.party_id)}
        {@const chip = chipFor(ex.colour.source)}
        <li class="flex items-start gap-3 py-3">
          <span
            class="mt-0.5 inline-block h-8 w-8 rounded border border-slate-200 shrink-0"
            style="background-color: {ex.colour.hex};"
            aria-hidden="true"
          ></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-medium text-sm">{ex.party_short}</span>
              <span
                class="text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded {chip.className}"
                title={chip.tooltip}>{chip.label}</span
              >
              <code class="text-xs font-mono text-slate-500"
                >{ex.colour.hex}</code
              >
            </div>
            <div class="text-xs text-slate-500 mt-0.5">{ex.party_full}</div>
            <div class="text-xs text-slate-600 mt-1">{ex.note}</div>
          </div>
        </li>
      {/each}
    </ul>

    <p class="text-xs text-slate-500">
      Colours are not editable. They reflect editorial sources
      (Wikipedia-curated brand colours, hand-curated anchors for
      high-recognition parties) and a deterministic fallback for the long
      tail. A per-browser override would not survive across devices and
      would muddy the provenance signal the chip is meant to carry.
    </p>
  </section>
</main>
