<script lang="ts">
  /**
   * PageContainer - the ONE shared page-shell primitive used by every
   * citizen-facing route. Replaces the 6-distinct-cap drift documented in
   * [TODO/20260615-party-page-citizen-fixes-plan.md](../../../../TODO/20260615-party-page-citizen-fixes-plan.md)
   * D7: bake one wide cap + one narrow opt-in + one no-cap escape hatch.
   *
   * Width mapping (verbatim from plan-doc Default verdict, baked by
   * Jony + Gregor):
   *   - "narrow" -> max-w-3xl  (~768px) for prose / settings / 404 / doc
   *     surfaces (About / Disclaimer / CountingMethodDoc / Settings /
   *     NotFound / IndicatorDoc / StateSubRouter dispatch surfaces).
   *   - "wide"   -> max-w-screen-2xl (~1536px) for every data-dense
   *     citizen page (Home, StateOverview, Explore, Party,
   *     TopicLanding / TopicIndex / StateTopic, NationalElection /
   *     StateElection / AssemblyElections / GeneralElections,
   *     Psephlab, CompareElections / CompareIndicator,
   *     DataCompleteness, PartiesIndex, Constituency, District,
   *     DevChartsSandbox, Yenask).
   *   - "full"   -> no cap (reserved for surfaces that genuinely want
   *     the viewport width; rare).
   *
   * Every variant ALWAYS applies the shared shell `mx-auto p-4 sm:p-6
   * space-y-6`. Per-route extras (text colour, prose line-height, flex
   * layout for chat-style children, etc.) flow in via the `class` prop
   * and are appended after the shell so they win on Tailwind specificity
   * ties. Arbitrary attributes (data-testid / data-route / id / role / ...)
   * flow through the rest-prop spread and land on the underlying
   * <main> element so existing test selectors keep working.
   *
   * Contract: the rendered tag is always <main>. The route author no
   * longer hand-types caps; a cap-policy change lands here.
   */
  import type { Snippet } from "svelte";

  type Width = "narrow" | "wide" | "full";

  interface Props {
    width?: Width;
    class?: string;
    children?: Snippet;
    [key: string]: unknown;
  }

  let {
    width = "wide",
    class: extraClass = "",
    children,
    ...rest
  }: Props = $props();

  // Cap policy lives here so route migrations never hand-type values.
  const CAP_BY_WIDTH: Record<Width, string> = {
    narrow: "max-w-3xl",
    wide: "max-w-screen-2xl",
    full: "",
  };

  const cls = $derived(
    [CAP_BY_WIDTH[width], "mx-auto p-4 sm:p-6 space-y-6", extraClass]
      .filter((s) => s.length > 0)
      .join(" "),
  );
</script>

<main class={cls} {...rest}>
  {@render children?.()}
</main>
