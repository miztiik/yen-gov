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
          SELECT c.eci_no, c.name,
                 w.party_eci_code AS winner_party_eci_code,
                 w.party_short    AS winner_party_short,
                 100.0 * (w.votes - r2.votes) / NULLIF(c.votes_polled, 0) AS margin_pct
          FROM constituencies c
          JOIN candidates w  ON w.constituency_eci_no  = c.eci_no AND w.is_winner = 1
          JOIN candidates r2 ON r2.constituency_eci_no = c.eci_no AND r2.rank = 2 AND r2.is_nota = 0
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
  const buckets = $derived.by(() => {
    const out = Array.from({ length: BUCKETS }, () => ({
      acs: [] as Row[],
      by_party: new Map<string, number>(),
    }));
    for (const r of rows ?? []) {
      const i = Math.min(BUCKETS - 1, Math.floor(r.margin_pct / 5));
      out[i].acs.push(r);
      const k = r.winner_party_eci_code ?? r.winner_party_short;
      out[i].by_party.set(k, (out[i].by_party.get(k) ?? 0) + 1);
    }
    return out;
  });

  function bucket_label(i: number): string {
    return i === BUCKETS - 1 ? "50%+" : `${i * 5}–${(i + 1) * 5}%`;
  }

  // Stack segments per bucket, party-colored.
  function segments(b: typeof buckets[number]): { color: string; n: number; party: string }[] {
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

  const max_count = $derived(Math.max(1, ...buckets.map(b => b.acs.length)));
  const total_acs = $derived((rows ?? []).length);

  // Layout
  const W = 640, H = 220, PAD_L = 32, PAD_R = 8, PAD_T = 8, PAD_B = 36;
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
    <svg viewBox="0 0 {W} {H}" class="w-full h-auto" role="img" aria-label="Margin of victory histogram">
      <!-- y-axis grid + ticks (0, 25%, 50%, 75%, 100% of max) -->
      {#each [0, 0.25, 0.5, 0.75, 1.0] as f}
        {@const y = PAD_T + inner_h - f * inner_h}
        {@const v = Math.round(f * max_count)}
        <line x1={PAD_L} x2={W - PAD_R} y1={y} y2={y} stroke="#e2e8f0" stroke-width="1" />
        <text x={PAD_L - 4} y={y + 3} text-anchor="end" class="fill-slate-400" style="font-size:10px">{v}</text>
      {/each}

      <!-- bars: stacked by party within each bucket -->
      {#each buckets as b, i}
        {@const x = PAD_L + i * bar_w}
        {@const segs = segments(b)}
        {#if b.acs.length > 0}
          {@const total_h = (b.acs.length / max_count) * inner_h}
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

    <p class="text-xs text-slate-500">
      {total_acs} constituencies · stacked by winning party
    </p>
  {/if}
</div>
