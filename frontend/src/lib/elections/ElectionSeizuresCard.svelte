<script lang="ts">
  // ElectionSeizuresCard - Row D of TODO/20260614-three-ephemeral-
  // ingests-plan.md. ONE card surfacing the MCC-period enforcement
  // seizures press-note series (Row A canonical ingest, source CSV
  // at `datasets/elections/parliament/election=<year>/mcc_seizures.csv`).
  //
  // Surfaces:
  //   1. Headline: "Total seizures on <date>: <value> <unit>"
  //   2. State choropleth (d3-geo SVG via GeoChoropleth) coloured by
  //      the picker-selected (category, unit, date) tuple. National
  //      view fills 36 states/UTs; state-filter view highlights one.
  //   3. Date slider over the publisher's reporting window (10 days
  //      for the 2019 vintage). Default = latest date.
  //   4. Category picker (6 facets per the parent plan):
  //        Total ₹ | Cash | Liquor | Drugs | Precious metals | Freebies
  //      Unit toggle (Value ₹ vs Quantity) appears INLINE next to
  //      the picker when the active category has a physical quantity
  //      facet (liquor / drugs / metals).
  //   5. Sparkline strip (10 dots, plain SVG) showing the same
  //      (category, unit) facet's daily series, national-summed
  //      when state_slug is unset, single-state when set.
  //
  // Loader / projection seam: DuckDB-WASM read is in
  // `election-seizures-loader.ts`; pure projection helpers (date
  // listing, value extraction, choropleth + sparkline shaping) live in
  // `election-seizures-model.ts` and are covered by vitest.
  //
  // Citizen-honesty rules (per parent plan §0.3 D3 + §5.D):
  //   - Publisher's `total_seizure_inr_crore` is used verbatim; no
  //     component-sum re-derivation.
  //   - Publisher-blank cells render as no-data hatch on the map; the
  //     sparkline zero-fills only the filtered-state path (where blank
  //     means "no row for that state on that date").
  //   - "Other" surfaces as "Freebies" per the citizen-honesty
  //     framing in the model module.

  import { onMount } from "svelte";
  import GeoChoropleth from "../charts/GeoChoropleth.svelte";
  import { loadStates, type StateRow } from "../view-models/states";
  import { loadSeizures } from "./election-seizures-loader";
  import {
    SEIZURES_CATEGORIES,
    categoryHasQuantity,
    categoryLabel,
    categoryUnitLabel,
    headlineValue,
    latestDate,
    listDates,
    projectChoropleth,
    projectSparkline,
    type SeizuresCategory,
    type SeizuresRow,
    type SeizuresUnit,
  } from "./election-seizures-model";

  interface Props {
    /** Election event id, e.g. `general-2019`. Determines the source
     *  CSV path via the loader. */
    event_id: string;
    /** Optional LGD state slug ("maharashtra", "tamil-nadu") to scope
     *  the headline + sparkline to one state. When omitted, the card
     *  surfaces the national rollup. The choropleth always renders
     *  all 36 states (citizen sees the national context); the
     *  state-filter only narrows the rollup numbers. Named
     *  `state_slug` (not `state`) to avoid shadowing Svelte 5's
     *  `$state()` rune in the destructured props. */
    state_slug?: string;
  }

  let { event_id, state_slug }: Props = $props();

  // -------------------------------------------------------------
  // Async data: seizures rows + state-spine (for slug -> LGD join).
  // -------------------------------------------------------------
  let rows = $state<readonly SeizuresRow[] | null>(null);
  let states = $state<readonly StateRow[] | null>(null);
  let load_error = $state<string | null>(null);

  onMount(() => {
    let cancelled = false;
    Promise.all([loadSeizures(event_id), loadStates()])
      .then(([sr, st]) => {
        if (cancelled) return;
        rows = sr;
        states = st;
      })
      .catch((e) => {
        if (cancelled) return;
        load_error = String(e);
      });
    return () => {
      cancelled = true;
    };
  });

  // -------------------------------------------------------------
  // Picker state.
  // -------------------------------------------------------------
  let category = $state<SeizuresCategory>("total");
  let unit = $state<SeizuresUnit>("value");
  // Date slider position: an index into the dates list. We track an
  // index (not the date string) so the slider element binds cleanly
  // to a numeric range input. The string date is derived.
  let date_index = $state<number | null>(null);

  // -------------------------------------------------------------
  // Deriveds.
  // -------------------------------------------------------------
  const dates = $derived<readonly string[]>(rows ? listDates(rows) : []);
  const default_date = $derived(rows ? latestDate(rows) : null);

  // Slug -> LGD map. Built once after states load.
  const slug_to_lgd = $derived.by<(slug: string) => string | null>(() => {
    if (!states) return () => null;
    const m = new Map<string, string>();
    for (const s of states) {
      // The state spine uses the canonical (current-period) slug
      // derived from the display name. Publisher's seizures CSV
      // uses LGD-current slugs for current-spine states; the few
      // pre-2020-merger UT slugs (dadra-and-nagar-haveli, daman-
      // and-diu) are intentionally absent from the spine and their
      // rows fall to the no-data hatch path.
      m.set(slugify(s.display_name), s.boundary_join_key);
    }
    return (slug: string) => m.get(slug) ?? null;
  });

  // Initialise the slider to the latest date once data lands.
  $effect(() => {
    if (date_index === null && dates.length > 0) {
      date_index = dates.length - 1;
    }
  });

  // Coerce the date_index back to a date string (or default).
  const selected_date = $derived<string | null>(
    date_index !== null && dates.length > 0
      ? (dates[Math.min(Math.max(date_index, 0), dates.length - 1)] ?? null)
      : default_date,
  );

  // If the user picks a value-only category while unit=quantity, snap
  // back to value so the choropleth doesn't fall to all-null.
  $effect(() => {
    if (unit === "quantity" && !categoryHasQuantity(category)) {
      unit = "value";
    }
  });

  // Choropleth + sparkline rows + headline.
  const map_rows = $derived(
    rows && selected_date
      ? projectChoropleth(
          rows,
          category,
          unit,
          selected_date,
          slug_to_lgd,
          state_slug ?? null,
        )
      : [],
  );
  const sparkline_points = $derived(
    rows ? projectSparkline(rows, category, unit, state_slug ?? null) : [],
  );
  const headline = $derived(
    rows ? headlineValue(rows, category, unit, state_slug ?? null) : null,
  );
  const unit_label = $derived(categoryUnitLabel(category, unit));

  // -------------------------------------------------------------
  // Formatters.
  // -------------------------------------------------------------
  function fmtValue(v: number): string {
    if (!Number.isFinite(v)) return "-";
    if (Math.abs(v) >= 100)
      return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (Math.abs(v) >= 10)
      return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
    return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function fmtHeadline(v: number | null): string {
    if (v === null) return "-";
    return `${fmtValue(v)} ${unit_label}`;
  }

  function fmtDateLabel(d: string | null): string {
    if (!d) return "";
    // d is YYYY-MM-DD; render as "29 Mar" / "07 Apr". Browser-native
    // Date parse is safe here because the string is ISO-8601.
    const dt = new Date(d + "T00:00:00Z");
    const m = dt.toLocaleString("en-IN", { month: "short", timeZone: "UTC" });
    const day = String(dt.getUTCDate()).padStart(2, "0");
    return `${day} ${m}`;
  }

  // Sparkline geometry. Plain SVG; no d3 dep beyond what the chart
  // primitives already pull in. 240x44 viewbox; one circle per date.
  const SPARK_W = 240;
  const SPARK_H = 44;
  const SPARK_PAD_X = 8;
  const SPARK_PAD_Y = 6;
  const spark_geometry = $derived.by(() => {
    const pts = sparkline_points;
    if (pts.length === 0) return null;
    const max = Math.max(1e-9, ...pts.map((p) => p.value));
    const innerW = SPARK_W - 2 * SPARK_PAD_X;
    const innerH = SPARK_H - 2 * SPARK_PAD_Y;
    const dx = pts.length > 1 ? innerW / (pts.length - 1) : 0;
    return pts.map((p, i) => {
      const x = SPARK_PAD_X + dx * i;
      const y =
        SPARK_PAD_Y + innerH - (max > 0 ? (p.value / max) * innerH : 0);
      return { x, y, value: p.value, date: p.date };
    });
  });

  const spark_path = $derived.by<string>(() => {
    const g = spark_geometry;
    if (!g || g.length === 0) return "";
    return g.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(2)} ${p.y.toFixed(2)}`).join(" ");
  });

  // -------------------------------------------------------------
  // Helpers (slugify reused from canonical helper - inline to avoid
  // a cross-package import cycle; matches the deterministic slug
  // derivation used elsewhere).
  // -------------------------------------------------------------
  function slugify(name: string): string {
    return name
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  // -------------------------------------------------------------
  // Citizen-readable title + chrome.
  // -------------------------------------------------------------
  const year = $derived.by<string>(() => {
    const m = event_id.match(/-(\d{4})$/);
    return m ? m[1] : event_id;
  });
  const card_title = $derived(`Election-period seizures (${year})`);
  // Title-case the slug with English-connector lowercasing per
  // user-memory PR #1027 forward rule (so "jammu-and-kashmir" reads
  // as "Jammu and Kashmir" not "Jammu And Kashmir").
  const CONNECTORS = new Set(["and", "of", "the", "in"]);
  function titleCaseSlug(slug: string): string {
    return slug
      .split("-")
      .map((w, idx) => {
        if (idx > 0 && CONNECTORS.has(w)) return w;
        return w.charAt(0).toUpperCase() + w.slice(1);
      })
      .join(" ");
  }
  const scope_label = $derived(
    state_slug ? `${titleCaseSlug(state_slug)} only` : "all India",
  );

  function selectCategory(c: SeizuresCategory): void {
    category = c;
  }
  function toggleUnit(u: SeizuresUnit): void {
    unit = u;
  }
</script>

<section
  class="rounded border border-slate-200 bg-white p-4"
  data-testid="election-seizures-card"
  data-event-id={event_id}
  data-state-slug={state_slug ?? ""}
>
  <header class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
    <h2 class="text-base font-semibold text-slate-800">{card_title}</h2>
    <p class="text-xs text-slate-500">Source: ECI MCC press notes · {scope_label}</p>
  </header>

  {#if load_error}
    <p class="text-sm text-rose-600" data-testid="election-seizures-error">
      Data couldn't load: {load_error}
    </p>
  {:else if rows === null || states === null}
    <p class="text-sm text-slate-500" data-testid="election-seizures-loading">
      Loading seizures data…
    </p>
  {:else if rows.length === 0}
    <p class="text-sm text-slate-500" data-testid="election-seizures-empty">
      No seizures rows published for this event.
    </p>
  {:else}
    <!-- Picker chrome. -->
    <div
      class="mb-3 flex flex-wrap items-center gap-1.5"
      data-testid="election-seizures-picker"
      role="group"
      aria-label="Seizure category picker"
    >
      {#each SEIZURES_CATEGORIES as c (c)}
        <button
          type="button"
          class="rounded border px-2 py-0.5 text-xs transition {category === c
            ? 'border-sky-600 bg-sky-50 text-sky-900'
            : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}"
          data-testid="election-seizures-picker-option"
          data-category={c}
          aria-pressed={category === c}
          onclick={() => selectCategory(c)}
        >
          {categoryLabel(c)}
        </button>
      {/each}
      {#if categoryHasQuantity(category)}
        <span class="mx-1 text-xs text-slate-400">·</span>
        <div
          class="inline-flex overflow-hidden rounded border border-slate-300 text-xs"
          data-testid="election-seizures-unit-toggle"
          role="group"
          aria-label="Value or quantity"
        >
          <button
            type="button"
            class="px-2 py-0.5 {unit === 'value'
              ? 'bg-sky-50 text-sky-900'
              : 'bg-white text-slate-700 hover:bg-slate-50'}"
            data-unit="value"
            aria-pressed={unit === "value"}
            onclick={() => toggleUnit("value")}
          >
            Value ₹
          </button>
          <button
            type="button"
            class="border-l border-slate-300 px-2 py-0.5 {unit === 'quantity'
              ? 'bg-sky-50 text-sky-900'
              : 'bg-white text-slate-700 hover:bg-slate-50'}"
            data-unit="quantity"
            aria-pressed={unit === "quantity"}
            onclick={() => toggleUnit("quantity")}
          >
            Quantity
          </button>
        </div>
      {/if}
    </div>

    <!-- Headline. -->
    <p
      class="mb-2 text-sm text-slate-700"
      data-testid="election-seizures-headline"
    >
      <span class="font-semibold text-slate-900">{categoryLabel(category)}</span>
      on
      <span class="tabular-nums">{fmtDateLabel(selected_date)}</span>:
      <span class="tabular-nums font-semibold text-slate-900"
        >{fmtHeadline(headline)}</span
      >
    </p>

    <!-- Map. -->
    <div data-testid="election-seizures-map">
      <GeoChoropleth
        topojson_path="/boundaries/in/states/all.topojson"
        feature_key="State_LGD"
        rows={map_rows}
        direction="lower_is_better"
        format_tick=".2s"
        format_value={(v) => fmtValue(v)}
        title=""
        source_owner="Election Commission of India (MCC press notes)"
        source_vintage={`${year} general election, ${dates[0] ?? ""} to ${dates[dates.length - 1] ?? ""}`}
        width={520}
        height={420}
        unit_label={unit_label}
      />
    </div>

    <!-- Date slider. -->
    {#if dates.length > 1}
      <div
        class="mt-3 flex items-center gap-2"
        data-testid="election-seizures-date-slider"
      >
        <span class="w-12 shrink-0 text-right text-xs tabular-nums text-slate-500"
          >{fmtDateLabel(dates[0])}</span
        >
        <input
          type="range"
          min={0}
          max={dates.length - 1}
          step={1}
          bind:value={date_index}
          class="flex-1 accent-sky-600"
          aria-label="Date slider"
        />
        <span class="w-12 shrink-0 text-xs tabular-nums text-slate-500"
          >{fmtDateLabel(dates[dates.length - 1])}</span
        >
      </div>
    {/if}

    <!-- Sparkline (10 dots). -->
    {#if spark_geometry && spark_geometry.length > 1}
      <div
        class="mt-3 flex items-center gap-2"
        data-testid="election-seizures-sparkline"
      >
        <span class="text-xs text-slate-500">{scope_label} daily</span>
        <svg
          viewBox={`0 0 ${SPARK_W} ${SPARK_H}`}
          class="h-10 w-full max-w-[240px] overflow-visible"
          aria-hidden="true"
        >
          <path
            d={spark_path}
            fill="none"
            stroke="rgb(14 116 144)"
            stroke-width="1.5"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          {#each spark_geometry as p, i (i)}
            <circle
              cx={p.x}
              cy={p.y}
              r={i === date_index ? 3.5 : 2}
              fill={i === date_index ? "rgb(14 116 144)" : "white"}
              stroke="rgb(14 116 144)"
              stroke-width="1.2"
              data-spark-date={p.date}
            />
          {/each}
        </svg>
      </div>
    {/if}
  {/if}
</section>
