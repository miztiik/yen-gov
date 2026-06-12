<script lang="ts">
  // Per-party page (`/parties/<slug>`) — PR-0 STUB.
  //
  // ADR-0053 (PR-0 of TODO/20260612-party-rendering-and-party-pages-plan.md,
  // rip-and-replace) ships the new route + URL grammar + reservation;
  // PR-4 of the same plan rebuilds this body indiavotes-style with
  // header card, KPI strip, dual-axis LS + VS bar+line charts,
  // strongholds, and a metadata footer. Until PR-4 lands the page
  // renders a stub: H1 + party_id chip + "Coming soon" — citizen-
  // honest about the work in flight, no fake content.
  //
  // Slug -> party_id resolution: `partyIdFromSlug` is the round-trip
  // inverse of the slug derivation rule in `slug.ts`. The STUB does
  // NOT load parties.csv (no view-model wired yet); the H1 just
  // title-cases the slug. PR-1 ships `loadPartyMeta(party_id)` and
  // PR-4 wires the H1 to the real `short` / `full` fields.

  import { partyIdFromSlug } from "../lib/slug";

  interface Props { slug: string }
  let { slug }: Props = $props();

  const party_id = $derived(partyIdFromSlug(slug));
  // Title-case the slug for the H1 fallback (`inc` -> `Inc`, `cpi-m`
  // -> `Cpi-m`). Citizen-acceptable for the brief stub window; PR-4
  // replaces this with the parties.csv `short` / `full`.
  const display = $derived(
    slug.split("-").map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(" "),
  );
</script>

<main class="max-w-3xl mx-auto p-6 space-y-6" data-testid="party-page-stub">
  <header class="space-y-2">
    <h1 class="text-2xl font-bold text-slate-900">{display}</h1>
    <p class="text-sm text-slate-500 font-mono">{party_id}</p>
  </header>

  <section
    class="rounded border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-600"
  >
    <p class="mb-2 font-medium">Per-party page coming soon.</p>
    <p>
      The detail body (seats-over-time, vote-share trend, strongholds, party
      metadata) lands in PR-4 of the party-rendering plan.
    </p>
  </section>
</main>
