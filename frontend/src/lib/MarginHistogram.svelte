<script lang="ts">
  // Histogram of winning margins (% of votes polled) across every AC in a state.
  //
  // Buckets are fixed at 5-percentage-point steps from 0% to 50%+. The "50+"
  // bucket is open-ended so landslides don't compress the readable range. Each
  // bar is colored by the winning party (or grey when multiple parties share
  // a bucket — see `dominant_party` below).
  //
  // Source: results.sqlite via lib/sql.svelte.ts. Computes margin from rank-1
  // and rank-2 candidate rows (NOTA excluded; matches what `result.summary`
  // would call the winner's margin).
  import { getDb } from "./sql";
  import { colors } from "./colors/store.svelte";

  interface Row {
    eci_no: number;
    name: string;
    winner_party_eci_code: string | null;
    winner_party_short: string;
    margin_pct: number;
  }

  let { event, state: state_code }: { event: string; state: string } = $props();

  let rows: Row[] | null = $state(null);
  let error: string | null = $state(null);

  $effect(() => {
    rows = null; error = null;
    const ev = event, st = state_code;
    (async () => {
      try {
        const db = await getDb(ev, st);
        // votes_polled denominator matches result.summary's margin_pct convention.
        const sql = `
          SELECT c.ac_eci_no AS eci_no, c.name,
                 w.party_eci_code AS winner_party_eci_code,
                 w.party_short    AS winner_party_short,
                 100.0 * (w.votes - r2.votes) / NULLIF(c.votes_polled, 0) AS margin_pct
          FROM constituencies c
          JOIN candidates w  ON w.ac_eci_no  = c.ac_eci_no AND w.is_winner = 1
          JOIN candidates r2 ON r2.ac_eci_no = c.ac_eci_no AND r2.rank = 2 AND r2.is_nota = 0
          ORDER BY margin_pct ASC;
        `;
        const res = db.exec(sql);
        if (!res[0]) { rows = []; return; }
        const cols = res[0].columns;
        rows = res[0].values.map(v => {
          const r: Record<string, unknown> = {};
          cols.forEach((c, i) => (r[c] = v[i]));
          return r as unknown as Row;
        });
      } catch (e) {
        error = String(e);
      }
    })();
  });

  // Bucket edges: [0,5), [5,10), ..., [45,50), [50,∞)
  const BUCKETS = 11;

  function bucket_label(i: number): string {
    return i === BUCKETS - 1 ? "50%+" : `${i * 5}–${(i + 1) * 5}%`;
  }

  // Stack segments per bucket, party-colored.
  function segments(b: { acs: Row[]; by_party: Map<string, number> }): { color: string; n: number; party: string }[] {
    const entries = [...b.by_party.entries()].sort((a, b) => b[1] - a[1]);
    return entries.map(([k, n]) => {
      // k is either an ECI code or a short name; colors.fill handles both.
      const sample = b.acs.find(a => (a.winner_party_eci_code ?? a.winner_party_short) === k);
      return {
        n,
        party: sample?.winner_party_short ?? k,
        color: colors.fill(sample?.winner_party_eci_code ?? null, sample?.winner_party_short),
      };
    });
  }

  const total_acs = $derived((rows ?? []).length);

  // ---- party-chip filter ----
  // Chips list one entry per *winning* party (parties that won zero seats
  // never appear in this chart anyway, since each row IS a winner). Click
  // a chip to mute that party's contribution; the bars re-stack to show
  // only the visible parties. The bucket count label updates accordingly.
  let muted_parties = $state<Set<string>>(new Set());
  $effect(() => { void state_code; muted_parties = new Set(); });

  function party_key(r: Row): string {
    return r.winner_party_eci_code ?? r.winner_party_short;
  }
  function toggle_mute(k: string): void {
    const next = new Set(muted_parties);
    if (next.has(k)) next.delete(k); else next.add(k);
    muted_parties = next;
  }

  interface PartyChip {
    key: string;
    party_eci_code: string | null;
    short: string;
    color: string;
    seats: number;
  }
  const winner_chips = $derived.by<PartyChip[]>(() => {
    const by_key = new Map<string, PartyChip>();
    for (const r of rows ?? []) {
      const k = party_key(r);
      const c = by_key.get(k);
      if (c) c.seats += 1;
      else by_key.set(k, {
        key: k,
        party_eci_code: r.winner_party_eci_code,
        short: r.winner_party_short,
        color: colors.fill(r.winner_party_eci_code, r.winner_party_short),
        seats: 1,
      });
    }
    return [...by_key.values()].sort((a, b) => b.seats - a.seats || a.short.localeCompare(b.short));
  });

  // Visible rows = rows whose winning party isn't muted. We recompute
  // buckets/max from `visible_rows` rather than the full `rows` so the
  // chart honestly reflects the active filter.
  const visible_rows = $derived<Row[]>(
    (rows ?? []).filter(r => !muted_parties.has(party_key(r))),
  );
  const visible_buckets = $derived.by(() => {
    const out: { acs: Row[]; by_party: Map<string, number> }[] =
      Array.from({ length: BUCKETS }, () => ({
        acs: [],
        by_party: new Map<string, number>(),
      }));
    for (const r of visible_rows) {
      const i = Math.min(BUCKETS - 1, Math.floor(r.margin_pct / 5));
      out[i].acs.push(r);
      const k = party_key(r);
      out[i].by_party.set(k, (out[i].by_party.get(k) ?? 0) + 1);
    }
    return out;
  });
  const visible_max = $derived(Math.max(1, ...visible_buckets.map(b => b.acs.length)));

  // ---- insight strip ----
  // For each winning party, compute median margin and # seats won by < 5
  // points (i.e. landed in bucket 0). Pick the headline by sorting on
  // close-call count desc, with median margin asc as tiebreak. Generated
  // sentences are deliberately conservative -- one comparative claim, one
  // descriptive claim per party row.
  function median(xs: number[]): number {
    if (xs.length === 0) return 0;
    const s = [...xs].sort((a, b) => a - b);
    const m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }
  interface PartyStats {
    short: string;
    seats: number;
    median_margin: number;
    close_calls: number; // seats won by < 5 points
    landslides: number;  // seats won by >= 25 points
    avg_margin: number;
  }
  const party_stats = $derived.by<PartyStats[]>(() => {
    const by: Record<string, Row[]> = {};
    for (const r of rows ?? []) (by[r.winner_party_short] ??= []).push(r);
    return Object.entries(by).map(([short, rs]) => ({
      short,
      seats: rs.length,
      median_margin: median(rs.map(r => r.margin_pct)),
      avg_margin: rs.reduce((s, r) => s + r.margin_pct, 0) / rs.length,
      close_calls: rs.filter(r => r.margin_pct < 5).length,
      landslides: rs.filter(r => r.margin_pct >= 25).length,
    })).sort((a, b) => b.seats - a.seats);
  });

  // Tightest race in the dataset — surfaces a concrete "X by Y points" hook
  // alongside the per-party aggregates so the panel always has a story.
  const tightest = $derived.by<Row | null>(() => {
    const rs = rows ?? [];
    if (rs.length === 0) return null;
    return rs.slice().sort((a, b) => (a.margin_pct ?? 0) - (b.margin_pct ?? 0))[0];
  });

  type IconName = "trophy" | "scales" | "bolt" | "target";
  interface Insight { icon: IconName; text: string; }

  const insights = $derived.by<Insight[]>(() => {
    const ps = party_stats;
    if (ps.length === 0) return [];
    const out: Insight[] = [];
    const top = ps[0];
    out.push({
      icon: "trophy",
      text: `${top.short} won ${top.seats} seat${top.seats === 1 ? "" : "s"}, ` +
            `with a median winning margin of ${top.median_margin.toFixed(1)} points.`,
    });
    const closest = [...ps].filter(p => p.seats >= 3)
      .sort((a, b) => (b.close_calls / b.seats) - (a.close_calls / a.seats))[0];
    if (closest && closest.close_calls > 0) {
      out.push({
        icon: "scales",
        text: `${closest.short} ran the closest book: ${closest.close_calls} of its ` +
              `${closest.seats} wins came by under 5 points.`,
      });
    }
    const landslider = [...ps].filter(p => p.seats >= 3)
      .sort((a, b) => (b.landslides / b.seats) - (a.landslides / a.seats))[0];
    if (landslider && landslider.landslides > 0 && landslider.short !== closest?.short) {
      out.push({
        icon: "bolt",
        text: `${landslider.short} had the most landslides: ` +
              `${landslider.landslides} win${landslider.landslides === 1 ? "" : "s"} by 25+ points.`,
      });
    }
    if (tightest && Number.isFinite(tightest.margin_pct)) {
      out.push({
        icon: "target",
        text: `Tightest race: ${tightest.name} (#${tightest.eci_no}) — ` +
              `${tightest.winner_party_short} held on by just ${tightest.margin_pct.toFixed(2)} points.`,
      });
    }
    return out;
  });

  // Layout
  // PAD_T = 20 (not 8) so the count label that sits 4px above the tallest
  // bar still has clearance from the SVG top edge. Earlier value clipped
  // labels for any bucket that happened to equal max_count.
  const W = 640, H = 232, PAD_L = 32, PAD_R = 8, PAD_T = 20, PAD_B = 36;
  const inner_w = W - PAD_L - PAD_R;
  const inner_h = H - PAD_T - PAD_B;
  const bar_w = inner_w / BUCKETS;
</script>

<div class="space-y-3">
  {#if error}
    <p class="text-sm text-rose-700">Could not load margins: <code>{error}</code></p>
  {:else if !rows}
    <p class="text-sm text-slate-500">Loading margins…</p>
  {:else if total_acs === 0}
    <p class="text-sm text-slate-500">No margin data available.</p>
  {:else}
    <!-- Winner-party chip filter. Each chip toggles its party on/off in the chart. -->
    <div class="flex flex-wrap items-center gap-1.5">
      {#each winner_chips as chip}
        {@const muted = muted_parties.has(chip.key)}
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs transition-opacity"
          class:opacity-40={muted}
          style:border-color={chip.color}
          title={muted ? `Click to show ${chip.short}` : `Click to hide ${chip.short}`}
          onclick={() => toggle_mute(chip.key)}
        >
          <span class="inline-block w-2 h-2 rounded-sm" style:background-color={chip.color}></span>
          <span class="font-medium text-slate-700">{chip.short}</span>
          <span class="text-slate-400">{chip.seats}</span>
        </button>
      {/each}
      {#if muted_parties.size > 0}
        <button
          type="button"
          class="text-xs text-blue-600 hover:underline ml-1"
          onclick={() => (muted_parties = new Set())}
        >Reset</button>
      {/if}
    </div>

    <svg viewBox="0 0 {W} {H}" class="w-full h-auto" role="img" aria-label="Margin of victory histogram" aria-describedby="margin-histogram-caption">
      <!-- y-axis grid + ticks (0, 25%, 50%, 75%, 100% of visible_max) -->
      {#each [0, 0.25, 0.5, 0.75, 1.0] as f}
        {@const y = PAD_T + inner_h - f * inner_h}
        {@const v = Math.round(f * visible_max)}
        <line x1={PAD_L} x2={W - PAD_R} y1={y} y2={y} stroke="#e2e8f0" stroke-width="1" />
        <text x={PAD_L - 4} y={y + 3} text-anchor="end" class="fill-slate-400" style="font-size:10px">{v}</text>
      {/each}

      <!-- bars: stacked by party within each bucket -->
      {#each visible_buckets as b, i}
        {@const x = PAD_L + i * bar_w}
        {@const segs = segments(b)}
        {#if b.acs.length > 0}
          {@const total_h = (b.acs.length / visible_max) * inner_h}
          {#each segs as seg, si}
            {@const prev = segs.slice(0, si).reduce((a, s) => a + s.n, 0)}
            {@const seg_h = (seg.n / b.acs.length) * total_h}
            {@const y = PAD_T + inner_h - total_h + (prev / b.acs.length) * total_h}
            <rect
              x={x + 1.5}
              y={y}
              width={bar_w - 3}
              height={seg_h}
              fill={seg.color}
              opacity="0.9"
            >
              <title>{bucket_label(i)} · {seg.party} · {seg.n} AC{seg.n === 1 ? "" : "s"}</title>
            </rect>
          {/each}
          <!-- count label above bar -->
          <text
            x={x + bar_w / 2}
            y={PAD_T + inner_h - total_h - 4}
            text-anchor="middle"
            class="fill-slate-600"
            style="font-size:10px"
          >{b.acs.length}</text>
        {/if}
        <!-- x-axis label -->
        <text
          x={x + bar_w / 2}
          y={H - PAD_B + 14}
          text-anchor="middle"
          class="fill-slate-500"
          style="font-size:10px"
        >{bucket_label(i)}</text>
      {/each}

      <!-- axis labels -->
      <text x={W / 2} y={H - 4} text-anchor="middle" class="fill-slate-600" style="font-size:11px">
        Winner's margin (% of votes polled)
      </text>
    </svg>

    <p id="margin-histogram-caption" class="text-xs text-slate-500 leading-relaxed">
      How decisively winners won — each bar is the count of seats whose winner
      beat the runner-up by that margin range. Bars on the left = close races;
      bars on the right = landslides.
      <span class="text-slate-400">
        {visible_rows.length}{visible_rows.length === total_acs ? "" : ` / ${total_acs}`}
        constituencies shown, stacked by winning party.
      </span>
    </p>

    {#if insights.length > 0}
      <div class="text-xs bg-slate-50 border border-slate-200 rounded px-3 py-2.5 leading-relaxed">
        <div class="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-slate-500 font-semibold mb-2">
          <svg viewBox="0 0 16 16" class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
            <path d="M8 1.5a3.5 3.5 0 0 0-2 6.36V10h4V7.86A3.5 3.5 0 0 0 8 1.5Z" />
            <path d="M6 11.5h4M6.5 13.5h3" stroke-linecap="round" />
          </svg>
          Insights
        </div>
        <ul class="space-y-1.5">
          {#each insights as ins}
            <li class="flex items-start gap-2 text-slate-700">
              <svg viewBox="0 0 16 16" class="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-slate-500" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                {#if ins.icon === "trophy"}
                  <path d="M4.5 2.5h7v3a3.5 3.5 0 0 1-7 0v-3Z" />
                  <path d="M4.5 3.5H2.5v1a2 2 0 0 0 2 2M11.5 3.5h2v1a2 2 0 0 1-2 2" />
                  <path d="M6.5 13.5h3M5.5 13.5h5M8 9v4.5" />
                {:else if ins.icon === "scales"}
                  <path d="M8 2v12M3.5 14h9" />
                  <path d="M3 5h10M3 5l-2 4a2 2 0 0 0 4 0L3 5ZM13 5l-2 4a2 2 0 0 0 4 0L13 5Z" />
                {:else if ins.icon === "bolt"}
                  <path d="M9 1.5 3.5 9h3.5l-1 5.5L13 7H9.5l1-5.5Z" />
                {:else if ins.icon === "target"}
                  <circle cx="8" cy="8" r="6" />
                  <circle cx="8" cy="8" r="3" />
                  <circle cx="8" cy="8" r="0.7" fill="currentColor" stroke="none" />
                {/if}
              </svg>
              <span>{ins.text}</span>
            </li>
          {/each}
        </ul>
        <p class="mt-2 pt-2 border-t border-slate-200 text-[10px] text-slate-500">
          A <strong>percentage point</strong> is the absolute gap in vote share —
          e.g. 25 points means the winner polled 25% more of all votes cast than
          the runner-up. Use it instead of “% bigger”, which compares ratios.
        </p>
      </div>
    {/if}
  {/if}
</div>
