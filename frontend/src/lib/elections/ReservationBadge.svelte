<!--
  ReservationBadge - the shared [SC] / [ST] reservation chip (Row 2 of
  TODO/20260622-election-constituency-grouping-plan.md).

  A small rose badge that renders ONLY for reserved constituencies; GEN
  (or null / undefined / "") renders NOTHING so a general seat carries no
  chrome. The category is normalised through `reservationKind`, so an
  upstream "sc" / " ST " still resolves. Shared so Row 6 (StateOverview)
  can drop its inline `[{reservation}]` span and reuse this exact badge.
-->
<script lang="ts">
  import { reservationKind } from "./constituency-list-tokens";

  interface Props {
    /** Raw reservation string ("GEN" / "SC" / "ST" / null). */
    reservation?: string | null;
    /** Extra utility classes (e.g. spacing) appended to the badge. */
    cls?: string;
  }

  const { reservation = null, cls = "" }: Props = $props();

  const kind = $derived(reservationKind(reservation));
</script>

{#if kind !== "GEN"}
  <span
    class={`inline-block rounded bg-rose-50 px-1 text-[10px] font-semibold leading-tight text-rose-600 ${cls}`}
    data-testid="constituency-reservation-badge"
    data-reservation={kind}
  >[{kind}]</span>
{/if}
