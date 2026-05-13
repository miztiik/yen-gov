<script lang="ts">
  // Peer-set selector for cross-state surfaces.
  //
  // Controlled component: the parent owns the `value` and reacts to
  // `onChange`. Options are the non-empty tiers from state-tiers.json
  // plus the `"all"` sentinel (the no-filter option, always available).
  //
  // Tiers with empty membership (e.g. fc_horizontal_devolution_share_quintile
  // pending recon) are intentionally hidden from the picker — the filter
  // would always show zero rows and the citizen has no recourse. The
  // resolver `nonEmptyTierIds()` does the filtering; this component just
  // renders what it's given.
  //
  // Doctrine: we render the human label, not the tier id. The `id` is for
  // wires and persistence; the label is for the citizen.

  import type { PeerSet } from "./catalogue";
  import type { StateTiersFile } from "./state-tiers";
  import { nonEmptyTierIds } from "./state-tiers";

  interface Props {
    /** Currently selected peer-set id (or `"all"`). */
    value: PeerSet;
    /** Loaded state-tiers file; null while loading or on error. */
    tiers: StateTiersFile | null;
    /** Called with the new selection. Parent is responsible for state. */
    onChange: (next: PeerSet) => void;
    /** Optional id prefix to keep <label for> unique on a page with many filters. */
    id_prefix?: string;
  }

  let { value, tiers, onChange, id_prefix = "peerset" }: Props = $props();

  // Build label map from the loaded tiers; unknown ids fall back to the
  // raw id (catches dev-time vocabulary drift loud and early).
  const labels = $derived.by(() => {
    const out: Record<string, string> = { all: "All states" };
    if (tiers) {
      for (const t of tiers.tiers) out[t.id] = t.label;
    }
    return out;
  });

  const options = $derived.by(() => {
    const ids = ["all", ...nonEmptyTierIds(tiers)];
    return ids.map(id => ({ id, label: labels[id] ?? id }));
  });

  const select_id = $derived(`${id_prefix}-select`);
</script>

<span class="inline-flex items-center gap-1 text-xs">
  <label for={select_id} class="text-slate-500">Compare across</label>
  <select
    id={select_id}
    class="rounded border border-slate-300 bg-white px-1 py-0.5 text-xs"
    value={value}
    onchange={(e) => onChange((e.currentTarget as HTMLSelectElement).value as PeerSet)}
  >
    {#each options as opt (opt.id)}
      <option value={opt.id}>{opt.label}</option>
    {/each}
  </select>
</span>
