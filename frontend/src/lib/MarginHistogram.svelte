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
  import * as d3 from "d3";
  import { onMount } from "svelte";
  import { tweened } from "svelte/motion";
  import { cubicOut } from "svelte/easing";
  import ChartTooltip, { type TooltipState } from "./ChartTooltip.svelte";

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

  // Stack segments per bucket, party-colored. We compute a darker shade
  // here too — the bar stack uses a vertical gradient (light at the top of
  // each segment, base at the bottom) so the histogram matches the visual
  // language of SeatDonut + PartyBar.
  function segments(b: { acs: Row[]; by_party: Map<string, number> }): { color: string; color_dark: string; n: number; party: string; eci_code: string | null }[] {
    const entries = [...b.by_party.entries()].sort((a, b) => b[1] - a[1]);
    return entries.map(([k, n]) => {
      // k is either an ECI code or a short name; colors.fill handles both.
      const sample = b.acs.find(a => (a.winner_party_eci_code ?? a.winner_party_short) === k);
      const fill = colors.fill(sample?.winner_party_eci_code ?? null, sample?.winner_party_short);
      return {
        n,
        party: sample?.winner_party_short ?? k,
        eci_code: sample?.winner_party_eci_code ?? null,
        color: fill,
        color_dark: d3.color(fill)?.darker(0.45)?.formatHex() ?? fill,
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

  // Sweep-up entrance — bars grow from the baseline. Mirrors the SeatDonut
  // motion language so all three hero charts on State Overview animate
  // alike. ~700 ms keeps the chart from feeling sluggish on slow loads.
  const grow = tweened(0, { duration: 700, easing: cubicOut });
  onMount(() => { grow.set(1); });

  // Custom tooltip (replaces the native <title>). Hovering a stacked
  // segment pops a styled card with the party + bucket + count + share of
  // bucket; the card is party-colored to mirror the segment.
  let tooltip = $state<TooltipState | null>(null);
  function showSegTip(
    e: MouseEvent,
    bucket_i: number,
    seg: { color: string; party: string; n: number; eci_code: string | null },
    bucket_total: number,
  ): void {
    tooltip = {
      x: e.clientX,
      y: e.clientY,
      color: seg.color,
      title: seg.party,
      subtitle: `Margin ${bucket_label(bucket_i)}`,
      lines: [
        { label: "Seats in band", value: String(seg.n) },
        { label: "Share of band", value: `${((seg.n / bucket_total) * 100).toFixed(0)}%` },
      ],
    };
  }
  function moveTip(e: MouseEvent): void {
    if (tooltip) tooltip = { ...tooltip, x: e.clientX, y: e.clientY };
  }
  function hideTip(): void { tooltip = null; }
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
      <defs>
        <!-- Soft drop shadow used by every segment. Same params as the
             donut so the visual language matches across charts. -->
        <filter id="margin-hist-shadow" x="-10%" y="-10%" width="120%" height="120%">
          <feGaussianBlur in="SourceAlpha" stdDeviation="0.9" />
          <feOffset dx="0" dy="0.8" result="offsetblur" />
          <feComponentTransfer><feFuncA type="linear" slope="0.22" /></feComponentTransfer>
          <feMerge><feMergeNode /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
        <!-- Per-segment vertical gradient: darker at the bottom of the
             segment, base color at the top. Done once per (bucket, party)
             via id; ~13 buckets × ~6 winning parties = ~78 gradients max,
             cheap. -->
        {#each visible_buckets as b, i}
          {#each segments(b) as seg, si}
            <linearGradient id="mh-grad-{i}-{si}" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stop-color={seg.color} />
              <stop offset="100%" stop-color={seg.color_dark} />
            </linearGradient>
          {/each}
        {/each}
      </defs>

      <!-- y-axis grid + ticks (0, 25%, 50%, 75%, 100% of visible_max) -->
      {#each [0, 0.25, 0.5, 0.75, 1.0] as f}
        {@const y = PAD_T + inner_h - f * inner_h}
        {@const v = Math.round(f * visible_max)}
        <line x1={PAD_L} x2={W - PAD_R} y1={y} y2={y} stroke="#e2e8f0" stroke-width="1" />
        <text x={PAD_L - 4} y={y + 3} text-anchor="end" class="fill-slate-400" style="font-size:10px">{v}</text>
      {/each}

      <!-- bars: stacked by party within each bucket. We multiply heights
           by `$grow` so the entire stack rises from the baseline; we keep
           the y origin at the *baseline* and shrink upward, otherwise the
           segments would float during the entrance. -->
      {#each visible_buckets as b, i}
        {@const x = PAD_L + i * bar_w}
        {@const segs = segments(b)}
        {#if b.acs.length > 0}
          {@const total_h_full = (b.acs.length / visible_max) * inner_h}
          {@const total_h = total_h_full * $grow}
          {#each segs as seg, si}
            {@const prev = segs.slice(0, si).reduce((a, s) => a + s.n, 0)}
            {@const seg_h = (seg.n / b.acs.length) * total_h}
            {@const y = PAD_T + inner_h - total_h + (prev / b.acs.length) * total_h}
            <rect
              x={x + 1.5}
              y={y}
              width={bar_w - 3}
              height={seg_h}
              rx="2"
              fill="url(#mh-grad-{i}-{si})"
              filter="url(#margin-hist-shadow)"
              class="cursor-default"
              onmouseenter={(e) => showSegTip(e, i, seg, b.acs.length)}
              onmousemove={moveTip}
              onmouseleave={hideTip}
            ></rect>
          {/each}
          <!-- count label above bar -->
          <text
            x={x + bar_w / 2}
            y={PAD_T + inner_h - total_h - 4}
            text-anchor="middle"
            class="fill-slate-700 font-semibold"
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
      <div class="text-xs bg-gradient-to-br from-slate-50 to-white border border-slate-200 rounded-lg px-3 py-3 leading-relaxed shadow-sm">
        <div class="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.12em] text-slate-500 font-semibold mb-2.5">
          <svg viewBox="0 0 16 16" class="w-3.5 h-3.5 text-amber-500" fill="currentColor" aria-hidden="true">
            <path d="M8 1a3.5 3.5 0 0 0-2 6.36V10h4V7.86A3.5 3.5 0 0 0 8 1Z" />
            <path d="M6 11h4v1H6zM6.5 13h3v1h-3z" />
          </svg>
          Insights
        </div>
        <ul class="space-y-2">
          {#each insights as ins}
            {@const tone = ins.icon === "trophy" ? { bg: "bg-amber-100", text: "text-amber-700" }
                         : ins.icon === "scales" ? { bg: "bg-rose-100", text: "text-rose-700" }
                         : ins.icon === "bolt"   ? { bg: "bg-violet-100", text: "text-violet-700" }
                         :                         { bg: "bg-sky-100", text: "text-sky-700" }}
            <li class="flex items-start gap-2.5 text-slate-700">
              <!-- Filled badge icon. Coloured background + white inner glyph
                   reads as a chip rather than a thin line drawing. Tone
                   is keyed off the insight type so each row has its own
                   visual identity (gold trophy, rose scales for close
                   races, violet bolt for landslides, sky target for the
                   tightest race). -->
              <span class="inline-flex items-center justify-center w-5 h-5 rounded-md flex-shrink-0 {tone.bg} {tone.text}">
                <svg viewBox="0 0 16 16" class="w-3 h-3" fill="currentColor" aria-hidden="true">
                  {#if ins.icon === "trophy"}
                    <path d="M5 2h6v3a3 3 0 0 1-6 0V2Z" />
                    <path d="M5 3H3v1a2 2 0 0 0 2 2M11 3h2v1a2 2 0 0 1-2 2" stroke="currentColor" stroke-width="1" fill="none" />
                    <rect x="6" y="11" width="4" height="1" />
                    <rect x="5.5" y="13" width="5" height="1" rx="0.5" />
                    <rect x="7.5" y="9" width="1" height="3" />
                  {:else if ins.icon === "scales"}
                    <rect x="7.5" y="2" width="1" height="12" />
                    <rect x="3.5" y="13.5" width="9" height="1" rx="0.5" />
                    <path d="M3 5h10l-2 4a2 2 0 0 1-4 0Zm0 0-2 4a2 2 0 0 0 4 0Zm10 0 2 4a2 2 0 0 1-4 0Z" stroke="currentColor" stroke-width="0.8" fill="currentColor" fill-opacity="0.85" />
                  {:else if ins.icon === "bolt"}
                    <path d="M9 1 3 9h3.5L5 15l7-8H8.5L9 1Z" />
                  {:else if ins.icon === "target"}
                    <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.5" />
                    <circle cx="8" cy="8" r="3" fill="none" stroke="currentColor" stroke-width="1.5" />
                    <circle cx="8" cy="8" r="1.2" />
                  {/if}
                </svg>
              </span>
              <span>{ins.text}</span>
            </li>
          {/each}
        </ul>
        <p class="mt-2.5 pt-2 border-t border-slate-200 text-[10px] text-slate-500">
          A <strong>percentage point</strong> is the absolute gap in vote share —
          e.g. 25 points means the winner polled 25% more of all votes cast than
          the runner-up. Use it instead of “% bigger”, which compares ratios.
        </p>
      </div>
    {/if}
  {/if}
</div>

<ChartTooltip tip={tooltip} />
