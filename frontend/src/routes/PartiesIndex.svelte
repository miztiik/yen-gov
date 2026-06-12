<script lang="ts">
  // Parties index (`/parties`) — PR-0 STUB.
  //
  // ADR-0053 (PR-0 of TODO/20260612-party-rendering-and-party-pages-plan.md,
  // rip-and-replace) ships the route + URL grammar + reservation;
  // PR-3 of the same plan builds the body (alphabetical list +
  // recognition-scope filter chips + search box, sourced from
  // `loadAllParties()` against `datasets/data/entities/parties.csv`).
  // Until PR-3 lands the page renders a stub: H1 + "Coming soon" —
  // citizen-honest about the work in flight, no fake content.
</script>

<main class="max-w-3xl mx-auto p-6 space-y-6" data-testid="parties-index-stub">
  <header>
    <h1 class="text-2xl font-bold text-slate-900">Parties</h1>
    <p class="mt-1 text-sm text-slate-500">
      Every party that has contested an election in the canonical store.
    </p>
  </header>

  <section
    class="rounded border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-600"
  >
    <p class="mb-2 font-medium">Parties index coming soon.</p>
    <p>
      The alphabetical list with search, recognition-scope filters, and
      per-party deep links lands in PR-3 of the party-rendering plan.
    </p>
  </section>
</main>
