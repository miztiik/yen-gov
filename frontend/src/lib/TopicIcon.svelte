<script lang="ts" module>
  // Topic-card / chart-header icon renderer (Phase 1.3b–f rollout).
  //
  // Consumes the structured `Icon` records emitted by `iconRegistryPlugin`
  // (frontend/vite.config.ts) via the virtual module `virtual:icon-registry`.
  // The contract is set by [the icon registry README](./icons/README.md):
  // the plugin walks `frontend/src/lib/icons/*.svg` at build/dev time and
  // freezes the result. The runtime in the citizen's browser sees only the
  // typed tree — never a raw SVG string, never a parser.
  //
  // Design decisions (Hans/Max read):
  //
  // - SILENT MISS. If `name` is undefined OR not in the registry, render
  //   NOTHING — no fallback glyph, no "missing" placeholder. Topic cards
  //   must not become broken when an icon ships unbuilt; the layout
  //   gracefully reflows to title-only. Surface is data-driven: if the
  //   taxonomy author references `topic.icon = "zap"` and someone deletes
  //   the SVG, the build fails LOUDLY (parser test walks every SVG), so
  //   silent runtime miss is the correct trade-off.
  //
  // - SHAPE-NAME OVERLOAD. Each `IconElement.name` is one of 7 element
  //   names (g/path/circle/rect/line/polyline/polygon — see
  //   `allowlist.ts`). The renderer dispatches on this enum literally so
  //   the bundle has no string-keyed SVG-element factory.
  //
  // - INHERITED COLOUR. `currentColor` flows through. The caller controls
  //   tint via the surrounding `text-*` class; the SVG uses
  //   `stroke="currentColor"` + `fill="none"` like every Lucide icon.
  //
  // - NO A11Y NOISE. CLAUDE.md §0 explicitly descopes accessibility; the
  //   icon is decorative (the topic title is the readable label), so we
  //   set `aria-hidden="true"` but omit any `role`/`<title>` plumbing.
  //
  // - PURE. No effects, no stores, no fetches. The registry import is
  //   build-time-frozen; tree-shaking strips unused icons since the
  //   plugin produces a single object literal.

  import { iconRegistry } from "virtual:icon-registry";
  import type { Icon, IconElement } from "./icons/types";

  /** Returns the Icon record for `name`, or `null` if the registry has
   *  no entry. Exported for unit tests; render code uses `$derived`. */
  export function lookupIcon(name: string | null | undefined): Icon | null {
    if (!name) return null;
    return iconRegistry[name] ?? null;
  }

  /** Returns the list of registered icon ids (sorted) — used by tests
   *  to assert the rollout-time guarantees about which icons exist. */
  export function registeredIconNames(): readonly string[] {
    return Object.freeze(Object.keys(iconRegistry).sort());
  }

  // Re-export the IconElement type so the recursive child block has
  // something to constrain its `el` prop against.
  export type { IconElement };
</script>

<script lang="ts">
  interface Props {
    /** Icon id (kebab-case filename without .svg). Silently no-op when missing. */
    name?: string | null;
    /** Tailwind size + colour utilities; default sits next to a card title. */
    cls?: string;
  }

  const { name = null, cls = "w-4 h-4 text-slate-500 shrink-0" }: Props = $props();

  const icon = $derived(lookupIcon(name));
</script>

{#snippet renderEl(el: IconElement)}
  {#if el.name === "g"}
    <g {...el.attrs}>
      {#each el.children as child}
        {@render renderEl(child)}
      {/each}
    </g>
  {:else if el.name === "path"}
    <path {...el.attrs} />
  {:else if el.name === "circle"}
    <circle {...el.attrs} />
  {:else if el.name === "rect"}
    <rect {...el.attrs} />
  {:else if el.name === "line"}
    <line {...el.attrs} />
  {:else if el.name === "polyline"}
    <polyline {...el.attrs} />
  {:else if el.name === "polygon"}
    <polygon {...el.attrs} />
  {/if}
{/snippet}

{#if icon}
  <svg
    class={cls}
    viewBox={icon.viewBox}
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    data-icon-name={icon.name}
  >
    {#each icon.children as el}
      {@render renderEl(el)}
    {/each}
  </svg>
{/if}
