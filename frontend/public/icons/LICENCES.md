# Icon licences

**Last Updated**: 2026-06-05

Provenance ledger for every glyph SVG shipped under `frontend/public/icons/`.
This file is the only acceptable record of where each icon came from and
what its licence permits. An icon without a row here MUST NOT be merged.

The plan section 21.10 freezes ONE open icon family for the citizen
bundle: **Lucide (ISC)** as the primary; Phosphor or Tabler (both MIT) as
the fallback for any glyph the primary family does not ship. Any other
source needs an explicit, repo-redistributable open licence (CC0-1.0 or
CC-BY-4.0 with attribution text on the row), called out in review.

Forbidden in the public bundle (per plan section 20.12 hard rule):
account-gated, no-derivatives, non-commercial, "all rights reserved", or
unclear-licence icon art. This includes scraped India Data Portal icons -
their UI art is proprietary even though their data is reusable. Stay
inside the open families above.

## Required fields per row

| Field | Rule |
| --- | --- |
| `Icon` | filename stem (kebab-case, no `.svg` extension; matches `ICON_FILENAME_REGEX` per [`frontend/src/lib/icons/allowlist.ts`](../../src/lib/icons/allowlist.ts)) |
| `Family` | one of `Lucide`, `Phosphor`, `Tabler`, or the open family name |
| `Source URL` | the canonical upstream page for that glyph (commit-pinned if upstream supports it) |
| `Licence` | SPDX id: `ISC`, `MIT`, `CC0-1.0`, `CC-BY-4.0`, ... |
| `Attribution` | required text for CC-BY-4.0 / any licence that needs visible credit; blank otherwise |
| `Modifications` | "none" or a one-line note (e.g. "stroke-width normalised", "viewBox cropped to 24x24") |

## Inventory

The 21 glyphs listed below are the file set this directory carried at the
U3 migration (plan chunk U3, 2026-06-05). The set is unchanged from the
prior `frontend/src/lib/icons/` location - only the on-disk home moved
(plan section 21.10; party-symbols precedent).

| Icon | Family | Source URL | Licence | Attribution | Modifications |
| --- | --- | --- | --- | --- | --- |
| activity | Lucide | https://lucide.dev/icons/activity | ISC | | none |
| bar-chart | Lucide | https://lucide.dev/icons/bar-chart-3 | ISC | | none |
| car | Lucide | https://lucide.dev/icons/car | ISC | | none |
| check | Lucide | https://lucide.dev/icons/check | ISC | | none |
| cloud | Lucide | https://lucide.dev/icons/cloud | ISC | | none |
| compass | Lucide | https://lucide.dev/icons/compass | ISC | | none |
| flag | Lucide | https://lucide.dev/icons/flag | ISC | | none |
| flame | Lucide | https://lucide.dev/icons/flame | ISC | | none |
| flask | Lucide | https://lucide.dev/icons/flask-conical | ISC | | none |
| heart-pulse | Lucide | https://lucide.dev/icons/heart-pulse | ISC | | none |
| info | Lucide | https://lucide.dev/icons/info | ISC | | none |
| landmark | Lucide | https://lucide.dev/icons/landmark | ISC | | none |
| settings | Lucide | https://lucide.dev/icons/settings | ISC | | none |
| shield | Lucide | https://lucide.dev/icons/shield | ISC | | none |
| sun | Lucide | https://lucide.dev/icons/sun | ISC | | none |
| trending-down | Lucide | https://lucide.dev/icons/trending-down | ISC | | none |
| trending-up | Lucide | https://lucide.dev/icons/trending-up | ISC | | none |
| users | Lucide | https://lucide.dev/icons/users | ISC | | none |
| vote | Lucide | https://lucide.dev/icons/vote | ISC | | none |
| wind | Lucide | https://lucide.dev/icons/wind | ISC | | none |
| zap | Lucide | https://lucide.dev/icons/zap | ISC | | none |

Lucide's ISC licence text is reproduced upstream at
https://github.com/lucide-icons/lucide/blob/main/LICENSE.

## How a new icon lands here

1. Pick the glyph from Lucide. Fall back to Phosphor or Tabler (both MIT)
   ONLY if Lucide does not ship a suitable equivalent.
2. Save the SVG at `frontend/public/icons/<kebab-case-id>.svg`. The
   filename stem is the icon id; it MUST match `ICON_FILENAME_REGEX`
   (kebab-case, no leading digit-only group).
3. Add one row to the inventory table above. All six fields are required;
   leave `Attribution` and `Modifications` blank only when the licence
   does not need them and the file is byte-identical to upstream.
4. Run `bun run test` from `frontend/`. The allowlist parser walks
   `frontend/public/icons/*.svg` and rejects any disallowed byte
   ([`frontend/src/lib/icons/parse.test.ts`](../../src/lib/icons/parse.test.ts)).
5. Run `bun run build` to confirm the Vite `iconRegistryPlugin` accepts
   the new file.

## See also

- [`frontend/src/lib/icons/README.md`](../../src/lib/icons/README.md) -
  contributor-facing icon-registry contract (the allowlist + parser stay
  in `src/lib/icons/` because they are code, not assets).
- [`docs/architecture/frontend/charts/icon-registry.md`](../../../docs/architecture/frontend/charts/icon-registry.md) -
  registry doctrine + sister registry (party-symbols under
  `frontend/public/party-symbols/`) using the same allowlist.
- [`TODO/20260603-data-and-charting-platform-reset-plan.md`](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) -
  plan section 21.10 frozen the icons-in-public layout; chunk U3 lands it.
