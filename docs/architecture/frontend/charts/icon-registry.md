# Icon registry (Phase 1.3)

**Last Updated**: 2026-05-25

Build-time SVG icon pipeline that replaces the legacy `IndicatorIcon.svelte`. Strict allowlist parser plus Vite plugin = full OWASP SVG attack surface covered at parse time with no runtime parsing cost.

## What it is

- [`frontend/src/lib/icons/types.ts`](../../../../frontend/src/lib/icons/types.ts), [`allowlist.ts`](../../../../frontend/src/lib/icons/allowlist.ts), [`parse.ts`](../../../../frontend/src/lib/icons/parse.ts), [`index.ts`](../../../../frontend/src/lib/icons/index.ts) — zero-dependency tokenizer + recursive-descent parser. Throws `IconParseError` with `file:line:col` reporting on any allowlist violation.
- Allowlist (closed sets):
  - `ALLOWED_ELEMENTS` (7): `g`, `path`, `circle`, `rect`, `line`, `polyline`, `polygon`, `svg` (root).
  - `ALLOWED_ATTRS` (22): `viewBox`, `xmlns`, `fill`, `stroke`, `stroke-width`, `stroke-linecap`, `stroke-linejoin`, `d`, `cx`, `cy`, `r`, `x`, `y`, `width`, `height`, `x1`, `y1`, `x2`, `y2`, `points`, `transform`, `class`.
  - `FORBIDDEN_ELEMENTS` (15): `script`, `style`, `foreignObject`, `embed`, `iframe`, `image`, `animate`, `animateMotion`, `animateTransform`, `set`, `use`, `mpath`, `mask`, `pattern`, `clipPath`.
  - `FORBIDDEN_ATTR_PATTERNS` (regex): `/^on/i` (event handlers), `/^xlink:/i`, `/^href$/i`, `/^style$/i`.
- [`frontend/vite.config.ts`](../../../../frontend/vite.config.ts) - `iconRegistryPlugin()` exposes virtual id `virtual:icon-registry`, watches `frontend/public/icons/*.svg` for add/change/unlink with HMR. (Plan section 21.10: SVG bytes live under `public/`, the allowlist + parser are code and stay under `src/lib/icons/`; the party-symbols registry follows the same pattern.) Provenance ledger lives next to the SVGs at [`frontend/public/icons/LICENCES.md`](../../../../frontend/public/icons/LICENCES.md).
- Initial set: 4 Lucide ISC-licensed SVGs (`vote`, `cloud`, `car`, `heart-pulse`) plus 8 test fixtures.

## Doctrinal rules

- **Build-time only.** No runtime SVG parsing. Vite emits a frozen `{[slug]: rendered_svg}` map; consumers receive sanitised strings.
- **Strict allowlist.** Elements and attributes are closed. Adding a new element or attr requires: (a) edit `allowlist.ts`, (b) add a fixture that exercises it, (c) confirm `parse.test.ts` self-consistency walk passes. Vite build fails otherwise.
- **Kebab-case slug only.** `ICON_FILENAME_REGEX = /^[a-z0-9]+(-[a-z0-9]+)*$/`. No PascalCase, no underscores.
- **No `style` inline attribute.** Inline styles are forbidden because they can carry CSS expression payloads and re-enable URL-fetching properties.
- **No `href` / `xlink:href` / `use`.** External resource references are forbidden; the registry is closed-set by design.
- **No event handlers (`on*`).** Catches `onload`, `onclick`, `onmouseover`, etc. — covers the entire OWASP SVG XSS class.
- **Registry is frozen** (`Object.freeze` at module init). Runtime mutation is structurally impossible.

## Test surface

- [`frontend/src/lib/icons/parse.test.ts`](../../../../frontend/src/lib/icons/parse.test.ts) — 12 vitest cases: accept valid nested shapes, reject forbidden elements/attrs, structural validation, allowlist self-consistency walk over every shipped `.svg`.

## Sister registry: party symbols

The party-symbol asset registry under `frontend/public/party-symbols/*.svg` reuses the SAME allowlist module, not a copy. Two registries, one allowlist:

- [`frontend/src/lib/party-symbols/sanitizer.ts`](../../../../frontend/src/lib/party-symbols/sanitizer.ts) imports `parseIcon` from this icon registry and wraps it with a SHA-256 hash (`node:crypto`) for the `election_symbol.asset_sha256` field on `datasets/taxonomy/parties.json` per [taxonomy-parties.schema.json v2.2](../../../../datasets/schemas/taxonomy-parties.schema.json).
- Walks `frontend/public/party-symbols/*.svg` in vitest ([`sanitizer.test.ts`](../../../../frontend/src/lib/party-symbols/sanitizer.test.ts), 18 cases) and rejects the same 15 forbidden elements + 4 forbidden attribute patterns this doc enumerates above.
- Lives under `frontend/public/`, not `datasets/`, as a deliberate exception: SVG bytes are static public media served from `/party-symbols/<slug>.svg`. Metadata (symbol_name, source_id FK to `sources.parquet` per [ADR-0032](../../decisions/0032-sources-citation-ledger.md), license_label) stays party-data on `taxonomy/parties.json`.

If a future asset class needs the same shape (any closed-set SVG registry), import `parseIcon` rather than copy the allowlist. Two divergent allowlists is the failure mode this whole module exists to prevent.

## See also

- [`overview.md`](../overview.md) — visualization catalog.

## Historical citations

Distils `.commit-msg-20.txt`–`.commit-msg-25.txt` and `.pr-body-3.md`, `.pr-body-20.md`–`.pr-body-25.md` (deleted on distillation). PR-3 = foundation; PRs-20–24 = five rollout sub-phases (topic cards, topic landings, indicator cards, chart headers, state-hub chips); PR-25 = legacy `IndicatorIcon` deletion. PR #528 (2026-06-01) added the sister party-symbol registry per the section above.