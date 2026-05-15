<script lang="ts">
  /**
   * SnapshotBadge — small inline badge that warns the citizen when an
   * indicator is a single-point snapshot rather than a time series, OR
   * when its values are in current (nominal) prices and therefore not
   * directly comparable over time. (Phase 2 of the viz-layer plan.)
   *
   * Two driving cases from the 2026-05-15 audit:
   *
   *   1. HDI: only one observation year exists per state. Plotting it
   *      as a line is dishonest. The badge says "Single-year snapshot"
   *      so the chart can render it as a card or an entity ranking
   *      instead of a timeseries.
   *
   *   2. Current-prices NSDP: the values rise year-on-year mostly
   *      because of inflation. Without disclosure the citizen reads
   *      "+10% growth" as real growth. The badge says "Current
   *      (nominal) prices — not inflation-adjusted" so the user knows
   *      to compare against a constant-prices view.
   *
   * The badge is intentionally bland (slate, small, no exclamation
   * mark) — it is informational, not alarmist.
   */

  type Variant = "snapshot" | "nominal_prices" | "urban_only" | "rural_only" | "absolute_currency";

  interface Props {
    variant: Variant;
    /** Optional override label; defaults to a per-variant string. */
    label?: string;
  }

  const { variant, label }: Props = $props();

  const text = $derived(label ?? defaultLabel(variant));

  function defaultLabel(v: Variant): string {
    switch (v) {
      case "snapshot":           return "Single-year snapshot";
      case "nominal_prices":     return "Current (nominal) prices — not inflation-adjusted";
      case "urban_only":         return "Urban areas only";
      case "rural_only":         return "Rural areas only";
      case "absolute_currency":  return "Absolute ₹ — not per-capita";
    }
  }
</script>

<span
  class="snapshot-badge inline-flex items-center gap-1 rounded
         border border-slate-300 bg-slate-100 px-2 py-0.5
         text-[11px] font-medium text-slate-600"
  data-variant={variant}
>
  {text}
</span>
