<script lang="ts" module>
  // Inline-SVG icon registry for indicator categories.
  //
  // Inline SVGs (vs lucide-svelte) chosen because the icon set is small,
  // stable, and inline lets us tint via `currentColor` without per-icon
  // wrapper props. Path data is from Lucide (ISC-licensed):
  // https://github.com/lucide-icons/lucide
  //
  // Add a new icon by copying the path attributes from a Lucide icon page.
  // Names match Lucide's hyphenated names. Unknown icons render FALLBACK
  // (a generic circle) so layout never breaks for new indicator categories.

  type IconPath = { d: string };
  type Icon = { paths: IconPath[]; viewBox?: string };

  const FALLBACK: Icon = {
    paths: [{ d: "M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2Zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8Z" }],
  };

  export const REGISTRY: Record<string, Icon> = {
    zap: { paths: [{ d: "M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" }] },
    heart: { paths: [{ d: "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.29 1.51 4.04 3 5.5l7 7Z" }] },
    "graduation-cap": { paths: [{ d: "M21.42 10.922a1 1 0 0 0-.019-1.838L12.83 5.18a2 2 0 0 0-1.66 0L2.6 9.08a1 1 0 0 0 0 1.832l8.57 3.908a2 2 0 0 0 1.66 0z" }, { d: "M22 10v6" }, { d: "M6 12.5V16a6 3 0 0 0 12 0v-3.5" }] },
    coins: { paths: [{ d: "M12 6v12" }, { d: "M16 10c0-1.105-1.79-2-4-2s-4 .895-4 2 1.79 2 4 2 4 .895 4 2-1.79 2-4 2-4-.895-4-2" }, { d: "M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Z" }] },
    "trending-up": { paths: [{ d: "M22 7L13.5 15.5L8.5 10.5L2 17" }, { d: "M16 7h6v6" }] },
    users: { paths: [{ d: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" }, { d: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" }, { d: "M22 21v-2a4 4 0 0 0-3-3.87" }, { d: "M16 3.13a4 4 0 0 1 0 7.75" }] },
    droplets: { paths: [{ d: "M7 16.3c2.2 0 4-1.83 4-4.05 0-1.16-.57-2.26-1.71-3.19S7.29 6.75 7 5.3c-.29 1.45-1.14 2.84-2.29 3.76S3 11.1 3 12.25c0 2.22 1.8 4.05 4 4.05Z" }, { d: "M12.56 6.6A10.97 10.97 0 0 0 14 3.02c.5 2.5 2 4.9 4 6.5s3 3.5 3 5.5a6.98 6.98 0 0 1-11.91 4.97" }] },
    stethoscope: { paths: [{ d: "M11 2v2" }, { d: "M5 2v2" }, { d: "M5 3H4a2 2 0 0 0-2 2v4a6 6 0 0 0 12 0V5a2 2 0 0 0-2-2h-1" }, { d: "M8 15a6 6 0 0 0 12 0v-3" }, { d: "M20 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z" }] },
    landmark: { paths: [{ d: "M3 22h18" }, { d: "M6 18v-7" }, { d: "M10 18v-7" }, { d: "M14 18v-7" }, { d: "M18 18v-7" }, { d: "M3 11h18" }, { d: "M12 2L3 8h18z" }] },
    scale: { paths: [{ d: "m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" }, { d: "m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" }, { d: "M7 21h10" }, { d: "M12 3v18" }, { d: "M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" }] },
    factory: { paths: [{ d: "M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z" }, { d: "M17 18h1" }, { d: "M12 18h1" }, { d: "M7 18h1" }] },
  };

  export function hasIcon(name: string): boolean {
    return name in REGISTRY;
  }

  export function iconFor(name: string | null | undefined): Icon {
    if (!name) return FALLBACK;
    return REGISTRY[name] ?? FALLBACK;
  }
</script>

<script lang="ts">
  // Per-instance: renders one icon by name. Caller controls size + colour
  // via Tailwind utility classes on `cls`.
  interface Props {
    name: string;
    title?: string;
    cls?: string;
  }
  let { name, title, cls = "w-4 h-4 text-slate-500" }: Props = $props();

  const icon = $derived(iconFor(name));
</script>

<svg
  class={cls}
  viewBox={icon.viewBox ?? "0 0 24 24"}
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden={title ? undefined : "true"}
  role={title ? "img" : undefined}
>
  {#if title}<title>{title}</title>{/if}
  {#each icon.paths as p}
    <path d={p.d} />
  {/each}
</svg>
