<script lang="ts">
  // Races-by-competitiveness board. NYT's "All Senate races" panel is the
  // direct inspiration: instead of one giant ranked table or a single
  // histogram, group every contest into a small number of named columns
  // ("Democrats expected to win easily" / ... / "Republicans expected to
  // win easily"). Reading the relative *heights* of the columns tells you
  // the headline at a glance ("BJP swept the easy races, INC dominated
  // the close ones").
  //
  // For an Indian state with N parties (rather than 2), we compress to:
  //   - One column per *top-3* winning party, for the seats they won
  //     comfortably (margin >= 10 pp). Headed `<P> won easily`.
  //   - Then the next column for the same top-3 parties combined where
  //     the margin was narrow (< 10 pp). Headed `Top-3 narrow wins`.
  //   - A final column for *any* party not in top-3, regardless of
  //     margin. Headed `Smaller parties won`.
  //   - A separate "most competitive" column listing the tightest 5 races
  //     across all parties (margin < 5 pp) — these are the ones to watch
  //     on counting day, regardless of who won.
  //
  // Each row in a column shows: AC name (link), winner party chip, margin.
  // Click a row → opens the AC drill-down page (same target as the map).

  import { colors } from "./colors/store.svelte";
  import { url } from "./url";
  import type { AcWinner } from "./view-models/state-overview";

  // PR-J (Phase 1.5): RacesBoard is now a pure presentational component.
  // The parent (StateOverview) loads `ac_winners[]` via `loadStateOverview`
  // and passes them in here; MarginHistogram does the same. No `getDb`,
  // no SQL, no fetch — failure / loading arms live on the parent's
  // `LoaderResult`.
  let { rows: input_rows, state: state_code }: { rows: AcWinner[] | null; state: string } = $props();

  interface Row {
    eci_no: number;
    name: string;
    winner_party_eci_code: string | null;
    winner_party_short: string;
    margin_pct: number;
  }

  const rows = $derived<Row[] | null>(
    input_rows == null
      ? null
      : input_rows.map((w) => ({
          eci_no: w.ac_eci_no,
          name: w.ac_name,
          winner_party_eci_code: w.party_eci_code,
          winner_party_short: w.party_short,
          margin_pct: w.margin_pct,
        })),
  );

  // Top-3 parties by total seats won. Computed off the rows themselves so
  // the panel is self-contained — no need to thread `summary` from the
  // parent. Tie-break by AC count then party_short alphabetically so the
  // result is stable across re-fetches.
  const top3 = $derived.by(() => {
    if (!rows) return [];
    const tally = new Map<string, { key: string; eci_code: string | null; short: string; seats: number }>();
    for (const r of rows) {
      const key = r.winner_party_eci_code ?? r.winner_party_short;
      const e = tally.get(key);
      if (e) e.seats++;
      else tally.set(key, {
        key,
        eci_code: r.winner_party_eci_code,
        short: r.winner_party_short,
        seats: 1,
      });
    }
    return [...tally.values()]
      .sort((a, b) => b.seats - a.seats || a.short.localeCompare(b.short))
      .slice(0, 3);
  });

  // Threshold: margin >= COMFORTABLE_PP is an easy win, < TIGHT_PP is a
  // nail-biter, in-between is "narrow". These are the same bands used by
  // the choropleth map legend on State Overview, so the mental model
  // carries across charts.
  const COMFORTABLE_PP = 10;
  const TIGHT_PP = 5;

  interface Column {
    title: string;
    /** Optional party_short name driving the column color. */
    party_short?: string;
    /** Optional ECI code for the column's color stripe. */
    party_eci_code?: string | null;
    /** Subtitle below the column header (e.g. seat count). */
    subtitle: string;
    rows: Row[];
  }

  const columns = $derived.by<Column[]>(() => {
    if (!rows || top3.length === 0) return [];
    const top_keys = new Set(top3.map(p => p.key));

    // For each top-3 party: their easy wins (margin >= COMFORTABLE_PP),
    // sorted by margin descending (most decisive first).
    const easy_cols: Column[] = top3.map(p => {
      const list = rows!.filter(r => {
        const k = r.winner_party_eci_code ?? r.winner_party_short;
        return k === p.key && (r.margin_pct ?? 0) >= COMFORTABLE_PP;
      }).sort((a, b) => (b.margin_pct ?? 0) - (a.margin_pct ?? 0));
      return {
        title: `${p.short} won easily`,
        party_short: p.short,
        party_eci_code: p.eci_code,
        subtitle: `${list.length} seat${list.length === 1 ? "" : "s"} · margin ≥ ${COMFORTABLE_PP} pp`,
        rows: list,
      };
    });

    // Top-3 narrow wins: any seat won by a top-3 party with margin between
    // TIGHT and COMFORTABLE. Tells the "had to fight for it" story
    // separately from the easy wins.
    const narrow = rows!.filter(r => {
      const k = r.winner_party_eci_code ?? r.winner_party_short;
      const m = r.margin_pct ?? 0;
      return top_keys.has(k) && m >= TIGHT_PP && m < COMFORTABLE_PP;
    }).sort((a, b) => (a.margin_pct ?? 0) - (b.margin_pct ?? 0));

    // Smaller parties: every seat NOT won by a top-3 party. These are the
    // "wild cards" — independent winners, regional fronts, etc.
    const smaller = rows!.filter(r => {
      const k = r.winner_party_eci_code ?? r.winner_party_short;
      return !top_keys.has(k);
    }).sort((a, b) => (b.margin_pct ?? 0) - (a.margin_pct ?? 0));

    // Most competitive: tightest 12 races across all parties (margin <
    // TIGHT). These are the races that could have flipped on a few
    // hundred votes.
    const tight = rows!.filter(r => (r.margin_pct ?? 0) < TIGHT_PP)
      .sort((a, b) => (a.margin_pct ?? 0) - (b.margin_pct ?? 0))
      .slice(0, 12);

    const out: Column[] = [...easy_cols];
    if (narrow.length > 0) {
      out.push({
        title: "Narrow wins (top 3)",
        subtitle: `${narrow.length} seat${narrow.length === 1 ? "" : "s"} · ${TIGHT_PP}–${COMFORTABLE_PP} pp`,
        rows: narrow,
      });
    }
    if (smaller.length > 0) {
      out.push({
        title: "Smaller parties won",
        subtitle: `${smaller.length} seat${smaller.length === 1 ? "" : "s"} · outside top 3`,
        rows: smaller,
      });
    }
    if (tight.length > 0) {
      out.push({
        title: "Most competitive",
        subtitle: `Tightest ${tight.length} · margin < ${TIGHT_PP} pp`,
        rows: tight,
      });
    }
    return out;
  });

  // Color helpers — read from the shared palette store so any custom party
  // color overrides apply here too. The chip color matches the chip the
  // same party gets in the donut, bar chart, and histogram.
  //
  // colors.forSet allocates a stable batch palette across every winning
  // party in this state's results — keeps unanchored regional parties
  // visually separated within the chart.
  const palette = $derived.by(() => {
    void colors.overrides;
    const keys = (rows ?? []).map(r => r.winner_party_eci_code ?? r.winner_party_short);
    return colors.forSet(keys);
  });
  function chipBg(eci_code: string | null, short: string): string {
    const k = eci_code ?? short;
    return palette.get(k)?.fill ?? colors.fill(eci_code, short);
  }
  // Margin band color: same RdYlBu trio used by the map legend so the
  // mental model "red = nail-biter, blue = comfortable" is consistent.
  function marginColor(m: number): string {
    if (m < TIGHT_PP) return "#d7191c";       // RdYlBu[0]
    if (m < COMFORTABLE_PP) return "#fdae61"; // RdYlBu[1]
    return "#2c7bb6";                         // RdYlBu[3]
  }
</script>

<div class="space-y-3">
  {#if !rows}
    <p class="text-sm text-slate-500">Loading races…</p>
  {:else if columns.length === 0}
    <p class="text-sm text-slate-500">No races to show.</p>
  {:else}
    <p class="text-xs text-slate-500">
      Every constituency, grouped by who won and by how comfortably. Numbers
      are the winner’s margin in percentage points. Click a row to open
      the constituency drill-down.
      <span class="text-slate-400 ml-1">
        Bands: comfortable ≥ {COMFORTABLE_PP} pp · narrow {TIGHT_PP}–{COMFORTABLE_PP} pp · nail-biter &lt; {TIGHT_PP} pp.
      </span>
    </p>

    <!-- Each column scrolls independently if it overflows. Heights vary
         dramatically (e.g. one party may have 80 easy wins while the
         narrow-win column has 4) — the visual cue *is* the height. We
         cap the visible height with max-h so the page doesn’t become
         a 4000-px scroll, but every row stays reachable via the per-column
         scrollbar. -->
    <div class="grid gap-3" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));">
      {#each columns as col}
        {@const stripe = col.party_eci_code !== undefined
          ? chipBg(col.party_eci_code ?? null, col.party_short ?? "")
          : "#94a3b8" /* slate-400 for non-party columns */}
        <section class="bg-slate-50 border border-slate-200 rounded-lg overflow-hidden flex flex-col">
          <header class="px-3 pt-2.5 pb-2 border-b border-slate-200 bg-white" style:border-top="3px solid {stripe}">
            <div class="text-sm font-semibold text-slate-800 leading-tight">{col.title}</div>
            <div class="text-[10px] uppercase tracking-[0.1em] text-slate-500 mt-0.5">{col.subtitle}</div>
          </header>
          <ul class="overflow-y-auto max-h-[420px] divide-y divide-slate-200 text-xs">
            {#each col.rows as r}
              {@const fill = chipBg(r.winner_party_eci_code, r.winner_party_short)}
              {@const mc = marginColor(r.margin_pct ?? 0)}
              <li>
                <a
                  href={url.acByNo(state_code, r.eci_no)}
                  class="flex items-center gap-2 px-3 py-1.5 hover:bg-white transition-colors"
                  title="{r.name} (#{r.eci_no}) — {r.winner_party_short} won by {r.margin_pct?.toFixed(2) ?? '—'} pp"
                >
                  <span class="inline-block w-1.5 h-1.5 rounded-full flex-shrink-0" style:background-color={fill} aria-hidden="true"></span>
                  <span class="truncate text-slate-700 flex-1">{r.name}</span>
                  <span class="text-[10px] tabular-nums font-semibold" style:color={mc}>
                    {r.margin_pct?.toFixed(1) ?? "—"}
                  </span>
                </a>
              </li>
            {/each}
          </ul>
        </section>
      {/each}
    </div>
  {/if}
</div>
