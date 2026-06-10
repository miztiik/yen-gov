<script lang="ts">
  // InlineCounterfactualSwing - PR-W3b inline ephemeral what-if panel.
  //
  // 2 dropdowns + a 0-30% slider + a "Seats under this swing" card.
  // Composes the existing `psephlab/mutations/statewideSwing.ts` (per-AC
  // proportional swing) + `psephlab/rules/fptp.ts` (winner-takes-the-seat)
  // via `psephlab/engine.run(actuals, scenario)`. Component-local state
  // ONLY - per the W3b plan-doc, "no URL persistence". Refresh = the
  // panel resets.
  //
  // The panel only runs for ASSEMBLY events today: the psephlab
  // canonical loader (`loadActuals`) is assembly-only. For parliament-
  // body events the caller passes `disabled=true` + the panel renders
  // a citizen-readable placeholder explaining why.
  //
  // Failure mode: if the canonical loader returns 0 ACs (event not
  // ingested, partition missing), the panel renders "no data" with no
  // crash. The seats card stays empty.

  import { loadActuals } from "../psephlab/canonical-loaders";
  import type { Tallies } from "../psephlab/types";
  import {
    deriveSwingSeats,
    listPartyChoices,
    type PartyChoice,
    type SwingSeatRow,
  } from "./inline-swing-model";

  interface Props {
    event: string;
    /** ECI state code (e.g. "S26"). */
    state_code: string;
    /** True when the event-body is parliament (no AC tallies on disk
     *  to swing against). Caller responsibility — derived from the
     *  event-slug prefix. */
    disabled?: boolean;
  }

  let { event, state_code, disabled = false }: Props = $props();

  let actuals = $state<Tallies | null>(null);
  let load_error = $state<string | null>(null);

  $effect(() => {
    if (disabled) {
      actuals = null;
      load_error = null;
      return;
    }
    const ev = event;
    const sc = state_code;
    actuals = null;
    load_error = null;
    loadActuals(ev, sc)
      .then((t) => {
        if (ev === event && sc === state_code) actuals = t;
      })
      .catch((e) => {
        if (ev === event && sc === state_code) load_error = String(e);
      });
  });

  const choices = $derived<PartyChoice[]>(
    actuals ? listPartyChoices(actuals) : [],
  );

  // Component-local state - reset on event/state change via the $effect
  // below; NO URL persistence (W3b binding constraint #8).
  let from_party = $state<string | null>(null);
  let to_party = $state<string | null>(null);
  let swing_pct = $state(0);

  $effect(() => {
    // Reset the swing inputs when scope changes so the citizen does
    // not see stale "BJP -> INC" choices for a different state.
    const _ev = event;
    const _sc = state_code;
    from_party = null;
    to_party = null;
    swing_pct = 0;
  });

  // Seed sensible defaults once `choices` are known. defaultConfig from
  // the statewideSwing mutation does the same picking under the hood,
  // but composing it here lets the dropdowns reflect the seed visibly.
  $effect(() => {
    if (!actuals) return;
    if (choices.length < 2) return;
    if (from_party === null) {
      // Third-most-popular party as the source by default (kingmaker
      // drain idiom). Falls back to the runner-up if only two parties.
      const from_idx = Math.min(2, choices.length - 1);
      from_party = choices[from_idx].party_eci_code;
    }
    if (to_party === null) {
      // Runner-up as the destination by default.
      to_party = choices[1].party_eci_code;
    }
  });

  const seats = $derived<SwingSeatRow[]>(
    actuals
      ? deriveSwingSeats(actuals, from_party, to_party, swing_pct)
      : [],
  );

  const ac_count = $derived(actuals?.acs.length ?? 0);
</script>

<section
  class="rounded border border-slate-200 bg-white p-4"
  data-testid="inline-counterfactual-swing"
>
  <h2 class="text-sm font-medium text-slate-700">
    Counterfactual swing (ephemeral)
  </h2>

  {#if disabled}
    <p
      class="mt-2 inline-block rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
      data-testid="inline-swing-disabled"
    >
      Inline swing is available for Assembly events. Parliament events use
      the per-state Lab surface.
    </p>
  {:else if load_error}
    <p
      class="mt-2 inline-block rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-800"
      data-testid="inline-swing-error"
    >
      Couldn't load constituency tallies: {load_error}
    </p>
  {:else if actuals === null}
    <p class="mt-2 text-xs text-slate-500">Loading tallies…</p>
  {:else if ac_count === 0 || choices.length < 2}
    <p
      class="mt-2 inline-block rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
      data-testid="inline-swing-empty"
    >
      No constituency tallies on file for this event yet.
    </p>
  {:else}
    <p class="mt-1 text-xs text-slate-500">
      Move {swing_pct}% of votes from one party to another, applied per
      constituency. Updates the seat tally below in real time. Page refresh
      resets - this scenario is not saved to the URL.
    </p>

    <div
      class="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3"
      data-testid="inline-swing-controls"
    >
      <label class="block">
        <span class="block text-xs text-slate-500">From party</span>
        <select
          class="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm"
          data-testid="inline-swing-from"
          bind:value={from_party}
        >
          {#each choices as c (c.party_eci_code)}
            <option value={c.party_eci_code}>{c.party_short}</option>
          {/each}
        </select>
      </label>
      <label class="block">
        <span class="block text-xs text-slate-500">To party</span>
        <select
          class="mt-1 w-full rounded border border-slate-300 bg-white px-2 py-1 text-sm"
          data-testid="inline-swing-to"
          bind:value={to_party}
        >
          {#each choices as c (c.party_eci_code)}
            <option value={c.party_eci_code}>{c.party_short}</option>
          {/each}
        </select>
      </label>
      <label class="block">
        <span class="block text-xs text-slate-500"
          >Swing {swing_pct}%</span
        >
        <input
          type="range"
          min="0"
          max="30"
          step="1"
          class="mt-1 w-full"
          data-testid="inline-swing-slider"
          bind:value={swing_pct}
        />
      </label>
    </div>

    <div
      class="mt-4 rounded border border-slate-200 bg-slate-50 p-3"
      data-testid="inline-swing-seats-card"
    >
      <div class="text-xs uppercase tracking-wide text-slate-500">
        Seats under this swing
      </div>
      <ul class="mt-2 space-y-1 text-sm">
        {#each seats as r (r.party_eci_code)}
          <li
            class="flex justify-between gap-3"
            data-testid="inline-swing-seats-row"
          >
            <span class="truncate font-medium">{r.party_short}</span>
            <span class="flex items-baseline gap-2 tabular-nums">
              <span class="text-slate-900">{r.swung_seats}</span>
              <span
                class={r.delta === 0
                  ? "text-xs text-slate-400"
                  : r.delta > 0
                    ? "text-xs text-emerald-700"
                    : "text-xs text-rose-700"}
                data-testid="inline-swing-seats-delta"
              >
                {r.delta > 0
                  ? `+${r.delta}`
                  : r.delta === 0
                    ? "+0"
                    : String(r.delta)}
              </span>
            </span>
          </li>
        {/each}
      </ul>
    </div>
  {/if}
</section>
