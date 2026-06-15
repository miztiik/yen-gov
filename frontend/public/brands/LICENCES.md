# Brand-asset licences

**Last Updated**: 2026-06-15

Provenance ledger for every third-party brand SVG shipped under
`frontend/public/brands/`. This directory is intentionally separate from
[`../icons/`](../icons/): files here are reproduced trademark / branded
artwork served as static `<img src>` assets at the citizen layer; files
under `icons/` are minted Lucide-shaped glyphs parsed and re-emitted by
the [build-time icon registry](../../src/lib/icons/) and constrained to
the closed allowlist in
[`frontend/src/lib/icons/allowlist.ts`](../../src/lib/icons/allowlist.ts).
Brand artwork (gradients, raster traces, complex paths) would fail that
allowlist by construction — hence the separate home.

An asset under `brands/` without a row here MUST NOT be merged. CLAUDE.md
section 12 (provenance is mandatory) applies to brand artwork the same way
it applies to data rows.

## Required fields per row

| Field | Rule |
| --- | --- |
| `Asset` | filename stem (with `.svg`) |
| `Owner` | trademark / brand owner |
| `Source URL` | the canonical upstream page for that file (commit-pinned if upstream supports it) |
| `Licence` | SPDX id: `CC-BY-SA-4.0`, `CC0-1.0`, ... |
| `Attribution` | required text for any licence that needs visible credit |
| `Modifications` | "none" or a one-line note (e.g. "viewBox cropped", "colours quantised") |

## Inventory

| Asset | Owner | Source URL | Licence | Attribution | Modifications |
| --- | --- | --- | --- | --- | --- |
| wikipedia.svg | Wikimedia Foundation | https://upload.wikimedia.org/wikipedia/en/8/80/Wikipedia-logo-v2.svg | CC-BY-SA-4.0 | "Wikipedia logo by Wikimedia Foundation, CC BY-SA 4.0 via Wikimedia Commons" (in-bundle attribution carried by the immediate `<a href="...wikipedia.org/...">Wikipedia</a>` adjacent to the `<img>` tag at the citizen surface) | none |

## How a new brand asset lands here

1. Confirm the asset's licence is one of the open redistributable shapes
   (CC-BY-*, CC0-*, public-domain). Anything else fails CLAUDE.md
   section 10 "open source first" and the plan section 20.12 hard rule.
2. Save the SVG at `frontend/public/brands/<kebab-case-id>.svg`. The
   directory has no allowlist / parser — files are served unmodified.
3. Add one row to the inventory table above. All six fields are required.
4. Reference the asset via `<img src="/brands/<id>.svg" alt="" ...>` in
   the consuming Svelte file. The `alt` MAY be empty (decorative) when an
   adjacent visible text label carries the meaning; otherwise the `alt`
   carries the citizen-readable label.

## Why this is not under `icons/`

The build-time icon registry at
[`frontend/vite.config.ts`](../../vite.config.ts) (`iconRegistryPlugin`)
walks `frontend/public/icons/*.svg` and rejects any file containing
elements outside the closed set
`{g, path, circle, rect, line, polyline, polygon}` or attributes outside
the small drawing-shape allowlist. Brand artwork (gradients, raster
traces, complex paths) fails that allowlist by construction. The cleanest
boundary is the directory: glyphs that fit the allowlist live in
`icons/`; brand artwork lives in `brands/`. There is no plan to widen
the icon allowlist for branded artwork — the closed set is doctrine
(plan section 21.10).
