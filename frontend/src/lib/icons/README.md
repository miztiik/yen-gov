# Icon registry — strict-allowlist folder

Drop a Lucide-style SVG into this folder as `<kebab-case-id>.svg` and the
build-time Vite plugin (`iconRegistryPlugin` in
[`frontend/vite.config.ts`](../../../vite.config.ts)) will parse it, REJECT
the build if it contains anything disallowed, and expose it through the
virtual module `virtual:icon-registry` as a typed [`Icon`](./types.ts)
structure.

The runtime consumer ([`IndicatorIcon.svelte`](../IndicatorIcon.svelte) and
future icon renderers) imports `iconRegistry` from that virtual module and
renders the structured shape — never a raw SVG string. Two layers of
defence: forbidden bytes are rejected at build, AND the runtime has no
slot to emit `<script>` even if the parser ever regressed.

## Add an icon

1. Take a 24×24 viewBox SVG from [Lucide](https://lucide.dev/) (ISC
   licence). Other sources are allowed only if the licence permits
   redistribution AND a `notes` field in [`./LICENCES.md`](#third-party-icons)
   records the source URL + author + attribution.
2. Drop the file at `frontend/src/lib/icons/<kebab-case-id>.svg`.
   - Filename regex: `^[a-z0-9]+(-[a-z0-9]+)*$` (no spaces, no
     underscores, no uppercase, no leading digit blocks).
   - The icon id used by `topic.icon` and `indicator.icon` is the filename
     without the `.svg` extension.
3. Run `bun run test -- icons/parse` to verify it passes the allowlist.
   The vitest suite walks every shipped SVG and asserts each one parses
   cleanly — a new icon that fails the allowlist fails this test BEFORE
   the build runs.
4. Run `bun run build` to verify the Vite plugin accepts it.

## What the allowlist rejects

The single source of truth is [`./allowlist.ts`](./allowlist.ts). The
plugin and the parser tests both import from it. There is no second copy.

Hard rejections (build fails with `<file>:<line>:<col>  <reason>`):

- **Forbidden elements**: `<script>`, `<style>`, `<foreignObject>`,
  `<image>`, `<use>`, `<a>`, `<iframe>`, `<object>`, `<embed>`, `<audio>`,
  `<video>`, `<animate*>`, `<set>`.
- **Forbidden attributes**: anything matching `^on…` (event handlers),
  `xlink:*` (remote sprite refs), `href` (remote refs), `style` (legacy
  expression vector).
- **Disallowed but not actively malicious elements**: anything outside
  `<g>`, `<path>`, `<circle>`, `<rect>`, `<line>`, `<polyline>`,
  `<polygon>` — silent stripping would launder a contributor's intent;
  the rejection is deliberate.
- **Disallowed root attributes**: only `viewBox` (required), and a small
  tolerated set (`width`, `height`, `xmlns`, …) are accepted. `width` and
  `height` are dropped — the consumer's CSS class controls size.
- **Boolean attributes** (`<path d />`): rejected; every attribute must
  carry a quoted value.
- **Text content** inside the SVG (other than whitespace): rejected.
  Icons are drawings, not labels.

## Third-party icons

When icons land from non-Lucide sources, record provenance in a
sibling `LICENCES.md` (created when the first such icon ships). Fields
required by the chart plan §1.3 iconography policy:

- icon id (filename),
- source URL,
- author,
- licence id (`ISC`, `MIT`, `CC0-1.0`, `CC-BY-4.0` with attribution text),
- modification note.

Avoid unclear, non-commercial, no-derivatives, or account-gated licences
in the public bundle.
