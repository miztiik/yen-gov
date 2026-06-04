# Icon registry — strict-allowlist code modules

This folder holds the **code** of the icon registry: the allowlist,
parser, types, and tests. The SVG **bytes** live under
[`frontend/public/icons/`](../../../public/icons/) (plan section 21.10,
party-symbols precedent: static SVG assets are `public/`, the allowlist
+ parser are code and stay here under `src/lib/icons/`).

Drop a Lucide-style SVG into `frontend/public/icons/` as
`<kebab-case-id>.svg` and the build-time Vite plugin
(`iconRegistryPlugin` in
[`frontend/vite.config.ts`](../../../vite.config.ts)) will parse it,
REJECT the build if it contains anything disallowed, and expose it
through the virtual module `virtual:icon-registry` as a typed
[`Icon`](./types.ts) structure.

The runtime consumer ([`TopicIcon.svelte`](../TopicIcon.svelte) and any
future icon renderer) imports `iconRegistry` from that virtual module and
renders the structured shape — never a raw SVG string. Two layers of
defence: forbidden bytes are rejected at build, AND the runtime has no
slot to emit `<script>` even if the parser ever regressed.

## Add an icon

1. Take a 24×24 viewBox SVG from [Lucide](https://lucide.dev/) (ISC
   licence). Other sources are allowed only if the licence permits
   redistribution AND a row in
   [`frontend/public/icons/LICENCES.md`](../../../public/icons/LICENCES.md)
   records the source URL + family + licence id + attribution.
2. Drop the file at `frontend/public/icons/<kebab-case-id>.svg`.
   - Filename regex: `^[a-z0-9]+(-[a-z0-9]+)*$` (no spaces, no
     underscores, no uppercase, no leading digit blocks).
   - The icon id used by `topic.icon` and `indicator.icon` is the filename
     without the `.svg` extension.
3. Add the provenance row in
   [`frontend/public/icons/LICENCES.md`](../../../public/icons/LICENCES.md).
   The ledger is the only acceptable record of where each icon came from.
4. Run `bun run test -- icons/parse` to verify it passes the allowlist.
   The vitest suite walks every shipped SVG and asserts each one parses
   cleanly — a new icon that fails the allowlist fails this test BEFORE
   the build runs.
5. Run `bun run build` to verify the Vite plugin accepts it.

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

Provenance lives in
[`frontend/public/icons/LICENCES.md`](../../../public/icons/LICENCES.md)
(the SVGs and their licence ledger sit together). Every shipped icon
MUST have a row there; an icon without a row will not pass review. The
row fields are: `Icon`, `Family`, `Source URL`, `Licence` (SPDX id),
`Attribution` (required for CC-BY-4.0 or any licence needing visible
credit), `Modifications` ("none" or a one-line note).

The plan section 21.10 freezes one open icon family per the citizen
bundle: **Lucide (ISC)** as primary; Phosphor or Tabler (both MIT) as
fallback. Other open licences (`CC0-1.0`, `CC-BY-4.0` with attribution)
are accepted on review. Account-gated, no-derivatives, non-commercial,
or unclear-licence icon art are forbidden in the public bundle.
