# frontend/src/lib/layout/

Shared layout primitives used by every citizen-facing route.

Today this folder owns ONE component:
[`PageContainer.svelte`](./PageContainer.svelte) - the cross-route page-shell
that replaces the 6-distinct-cap drift documented in
[TODO/20260615-party-page-citizen-fixes-plan.md](../../../../TODO/20260615-party-page-citizen-fixes-plan.md) D7.

## `<PageContainer>`

Always renders as `<main>`. Always applies the shared shell
`mx-auto p-4 sm:p-6 space-y-6`. The `width` prop picks the cap.

| `width`  | Cap class           | px (Tailwind) | Use for                                                                                                                                                                                                                                                                                       |
| -------- | ------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `narrow` | `max-w-3xl`         | ~768 px       | Prose / doc / settings / 404 surfaces: About, Disclaimer, CountingMethodDoc, Settings, NotFound, IndicatorDoc, StateSubRouter (the small dispatch / error / loading surfaces).                                                                                                                |
| `wide`   | `max-w-screen-2xl`  | ~1536 px      | Every data-dense citizen page: Home, StateOverview, Explore, Party, TopicLanding, TopicIndex, StateTopic, NationalElection, StateElection, AssemblyElections, GeneralElections, Psephlab, CompareElections, CompareIndicator, DataCompleteness, PartiesIndex, Constituency, District, DevChartsSandbox, Yenask. |
| `full`   | (none)              | viewport      | Reserved for surfaces that genuinely want viewport width (rare; no live consumer today).                                                                                                                                                                                                      |

`width` defaults to `"wide"`. Pick `"narrow"` only when the content is
prose-shaped or a single-column settings list.

### Props

- `width?: "narrow" | "wide" | "full"` - see table above. Default `"wide"`.
- `class?: string` - extra Tailwind classes appended after the shared
  shell. Used by routes that need `leading-relaxed text-slate-800`
  (prose), `text-slate-800` (DevChartsSandbox), or `flex flex-col gap-4`
  (Yenask chat thread). Every other route omits this.
- `children` - default snippet.
- Any other attribute (`data-testid`, `data-route`, `id`, ...) flows
  through to the underlying `<main>` element via rest-prop spread.

### Usage

```svelte
<script lang="ts">
  import PageContainer from "../lib/layout/PageContainer.svelte";
</script>

<!-- Data-dense default: -->
<PageContainer>
  <h1>Home</h1>
  <!-- ... -->
</PageContainer>

<!-- Prose / settings: -->
<PageContainer width="narrow">
  <h1>About</h1>
  <!-- ... -->
</PageContainer>

<!-- Route-scoped attributes pass through: -->
<PageContainer width="wide" data-testid="party-detail" data-party-id={party_id}>
  <!-- ... -->
</PageContainer>

<!-- Per-route extra classes (prose pages, chat-style children, ...): -->
<PageContainer width="narrow" class="leading-relaxed text-slate-800">
  <!-- About / Disclaimer prose surfaces -->
</PageContainer>
```

### Why this lives here

- One cap policy lands in one file. A future cap change does not need
  to hunt across ~27 route files.
- The contract test
  [`frontend/src/contracts/no-route-bare-width-cap.test.ts`](../../contracts/no-route-bare-width-cap.test.ts)
  pins the rule: no top-level `<main>` or `<section>` in
  `frontend/src/routes/*.svelte` may declare its own `max-w-*` cap; use
  `<PageContainer width="...">` instead. One documented allowlist exists
  (the inline 404 recovery surface inside StateOverview).
- The 5 routes that were previously left-aligned (TopicLanding,
  TopicIndex, StateTopic, IndicatorDoc, CompareIndicator - their
  top-level `<section>` had `max-w-Nxl` but no `mx-auto`) become
  centered as a side-effect citizen fix when they migrate.

### Allowlist

The contract test allows ONE exception:

- [`StateOverview.svelte`](../../routes/StateOverview.svelte): the
  inline 404 surface (`<main class="max-w-md mx-auto p-12 text-center
  space-y-4">`) MAY keep `max-w-md` because it mirrors `NotFound.svelte`'s
  recovery copy and the existing Playwright extended-routes contract
  asserts the 404 from a single locator scope. The page above this
  surface uses `<PageContainer width="wide">` normally.

### See also

- [TODO/20260615-party-page-citizen-fixes-plan.md](../../../../TODO/20260615-party-page-citizen-fixes-plan.md)
  PR-6 D7 - the plan that minted this primitive.
- [CLAUDE.md](../../../../CLAUDE.md) section 0a authority assignment -
  D7 is Jony + Gregor (cross-cutting layout discipline).
