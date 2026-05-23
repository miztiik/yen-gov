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
- [`frontend/vite.config.ts`](../../../../frontend/vite.config.ts) — `iconRegistryPlugin()` exposes virtual id `virtual:icon-registry`, watches `frontend/src/assets/icons/*.svg` for add/change/unlink with HMR.
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

## See also

- [`overview.md`](../overview.md) — visualization catalog.
- [Phase 1.3 plan section](../../../../docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md) — rollout sequence 1.3a (foundation) through 1.3g (legacy `IndicatorIcon.svelte` deletion).

## Historical citations

Distils `.commit-msg-20.txt`–`.commit-msg-25.txt` and `.pr-body-3.md`, `.pr-body-20.md`–`.pr-body-25.md` (deleted on distillation). PR-3 = foundation; PRs-20–24 = five rollout sub-phases (topic cards, topic landings, indicator cards, chart headers, state-hub chips); PR-25 = legacy `IndicatorIcon` deletion.
