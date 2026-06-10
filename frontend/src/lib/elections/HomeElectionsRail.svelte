<!--
  Home elections rail (PR-W4d, 2026-06-10).
  3-card horizontal strip mounted on Home.svelte's elections experience.
  Pure-presentation; takes the composed payload as props. See
  ../view-models/home-elections-rail.ts for the composer.

  Cards (per Jony Q4 verdict in
  TODO/20260609-election-experience-overhaul-plan.md):
    1. Anchor - most-recent finished event ("Parliament 2024 -> national results")
    2. Hook   - closest race in the anchor event ("2024's closest seat: ...")
    3. Door   - "All elections" -> /t/elections firehose
-->
<script lang="ts">
  import type {
    AnchorCard,
    HookCard,
    DoorCard,
  } from "../view-models/home-elections-rail";

  let { anchor, hook, door }: {
    anchor: AnchorCard;
    hook: HookCard;
    door: DoorCard;
  } = $props();
</script>

<section
  class="grid grid-cols-1 md:grid-cols-3 gap-3"
  data-testid="home-elections-rail"
  aria-label="Elections quick access"
>
  <a
    href={anchor.href}
    class="block p-4 bg-slate-100 rounded hover:bg-slate-200 transition-colors"
    data-testid="rail-anchor"
  >
    <div class="text-xs uppercase tracking-wide text-slate-500">Latest</div>
    <div class="text-lg font-semibold text-slate-900">{anchor.title}</div>
    <div class="text-sm text-slate-700">{anchor.subtitle}</div>
  </a>

  <a
    href={hook.href}
    class="block p-4 bg-amber-50 rounded hover:bg-amber-100 transition-colors"
    data-testid="rail-hook"
  >
    <div class="text-xs uppercase tracking-wide text-amber-700">Closest race</div>
    <div class="text-lg font-semibold text-slate-900">{hook.title}</div>
    <div class="text-sm text-slate-700">{hook.subtitle}</div>
  </a>

  <a
    href={door.href}
    class="block p-4 bg-slate-50 rounded hover:bg-slate-100 border border-slate-200 transition-colors flex items-center"
    data-testid="rail-door"
  >
    <div class="text-lg font-semibold text-slate-900">{door.title} -&gt;</div>
  </a>
</section>
