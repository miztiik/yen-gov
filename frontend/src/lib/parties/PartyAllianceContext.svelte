<script lang="ts" module>
  /**
   * `PartyAllianceContext` - "Who they ride with" strip for the
   * per-party detail page (PR-8 of TODO/20260614-party-page-
   * reimagination-plan.md).
   *
   * Surfaces a "what alliance does this party ride with right now?"
   * strip directly UNDER the `PartyCurrentStrength` strip on
   * `/parties/<slug>`. Mirrors the visual tokens of the Current
   * Strength strip (slate-200 border, white background, slate-500
   * 12px uppercase tracking-wide section heading) for visual
   * continuity in the head-of-page strip stack.
   *
   * Layout:
   *
   *   <landmark> Parliament 2024: led NDA with JD(U), TDP (+5 others).
   *   <flag> State Assembly alliances:
   *           - Maharashtra (2024): led Mahayuti with SHS (+1 other).
   *           - Bihar (2020): junior in NDA with BJP.
   *           - Kerala (2021): contested alone.
   *   <slate-400 italic caveat>
   *
   * Suppression contracts:
   *   - `is_sentinel`: defence-in-depth short-circuit. NOTA / UNK
   *     hides the strip even if a stale view-model from cache leaks
   *     a populated value.
   *   - `alliance_context === null`: hides the strip entirely (the
   *     view-model returns null for sentinels, IND, parties with no
   *     alliance rows on file).
   *   - Both sections null/empty: hides the strip (redundant defence
   *     since the view-model would have returned null).
   *
   * Per-row suppression:
   *   - Parliament section is rendered only when `parliament` is
   *     non-null (the view-model already drops Parliament rows with
   *     empty alliance string - "contested alone in Parliament" is
   *     intentionally silent).
   *   - State Assembly section is rendered only when
   *     `state_assemblies.length > 0`.
   *
   * Per-row role copy:
   *   - "led":    "led <alliance> with <partners>"
   *   - "junior": "junior in <alliance> with <partners>"
   *   - "alone" (with alliance):  "<alliance> alliance, partner data pending"
   *   - "alone" (no alliance):    "contested alone"
   *
   * The alone-with-alliance branch surfaces the alliance name with
   * an honest "partner data pending" tail per the user-memory note
   * (2026-06-14, alliance rows ship without candidacies CSV) - the
   * citizen sees that we KNOW the alliance existed but we cannot
   * yet show who else was in it.
   *
   * Partner truncation: when `partner_count > partner_names_top.
   * length`, the renderer appends a "(+N others)" suffix flagging
   * the truncation.
   */
  import type {
    PartyAllianceContext,
    PartyAllianceContextParliament,
    PartyAllianceContextStateAssembly,
  } from "../view-models/party-alliance-context";

  /** Pure: render the partner list as a comma-separated string with
   *  the truncation tail. Empty list returns "". Exported for vitest. */
  export function formatPartnerList(
    partner_names_top: string[],
    partner_count: number,
  ): string {
    if (partner_names_top.length === 0) return "";
    const head = partner_names_top.join(", ");
    const extra = partner_count - partner_names_top.length;
    if (extra <= 0) return head;
    return `${head} (+${extra} other${extra === 1 ? "" : "s"})`;
  }

  /** Pure: render one row's role + alliance + partners as a single
   *  citizen-readable line. Exported for vitest. */
  export function formatAllianceLine(
    role: "led" | "junior" | "alone",
    alliance: string | null,
    partner_names_top: string[],
    partner_count: number,
  ): string {
    if (alliance === null) return "contested alone";
    if (role === "alone") {
      return `${alliance} alliance, partner data pending`;
    }
    const partners = formatPartnerList(partner_names_top, partner_count);
    const verb = role === "led" ? "led" : "junior in";
    if (partners.length === 0) return `${verb} ${alliance}`;
    return `${verb} ${alliance} with ${partners}`;
  }

  export type {
    PartyAllianceContext,
    PartyAllianceContextParliament,
    PartyAllianceContextStateAssembly,
  };
</script>

<script lang="ts">
  interface Props {
    alliance_context: PartyAllianceContext | null;
    /** Sentinel short-circuit: NOTA / UNK suppress the strip even
     *  if the view-model accidentally arrived populated. The IND
     *  short-circuit is handled upstream by the loader. */
    is_sentinel: boolean;
  }

  const { alliance_context, is_sentinel }: Props = $props();

  const visible = $derived(
    !is_sentinel &&
      alliance_context !== null &&
      (alliance_context.parliament !== null ||
        alliance_context.state_assemblies.length > 0),
  );
  const parliament = $derived(alliance_context?.parliament ?? null);
  const stateAssemblies = $derived(alliance_context?.state_assemblies ?? []);
</script>

{#if visible}
  <section
    data-testid="party-alliance-context"
    class="mt-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:mt-4 md:p-5"
    aria-label="Who this party rides with"
  >
    <h2
      class="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500"
    >
      Who they ride with
    </h2>
    {#if parliament}
      <p
        data-testid="party-alliance-context-parliament"
        class="flex items-start text-base text-slate-800"
      >
        <img
          src="/icons/landmark.svg"
          alt=""
          aria-hidden="true"
          width="16"
          height="16"
          class="mr-2 mt-1 inline-block flex-none"
        />
        <span>
          {parliament.event_label}:
          <span class="font-semibold"
            >{formatAllianceLine(
              parliament.role,
              parliament.alliance,
              parliament.partner_names_top,
              parliament.partner_count,
            )}</span
          >.
        </span>
      </p>
    {/if}
    {#if stateAssemblies.length > 0}
      <div
        data-testid="party-alliance-context-assemblies"
        class="mt-2 flex items-start text-sm text-slate-700"
      >
        <img
          src="/icons/flag.svg"
          alt=""
          aria-hidden="true"
          width="16"
          height="16"
          class="mr-2 mt-0.5 inline-block flex-none"
        />
        <div>
          <p class="mb-1">State Assembly alliances:</p>
          <ul class="ml-4 list-disc space-y-0.5">
            {#each stateAssemblies as row (row.state)}
              <li data-testid="party-alliance-context-assembly-row">
                {row.event_label}:
                <span class="font-semibold"
                  >{formatAllianceLine(
                    row.role,
                    row.alliance,
                    row.partner_names_top,
                    row.partner_count,
                  )}</span
                >.
              </li>
            {/each}
          </ul>
        </div>
      </div>
    {/if}
    <p
      data-testid="party-alliance-context-caveat"
      class="mt-3 text-xs italic text-slate-400"
    >
      Alliance ties recorded only for the cycles already ingested;
      older arrangements may exist in publisher records not yet on file.
    </p>
  </section>
{/if}
