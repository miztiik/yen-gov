# PR-SYM-4a.ii pilot batch (REAL Commons SVGs): 4 national-party election symbols

Date: 2026-06-01. Closes pilot half of PR-SYM-4a in `TODO/20260527-party-symbol-assets-plan.md`.
**Supersedes PR #543** (which shipped hand-authored silhouettes; replaced with real Commons-derived bytes).

## What ships

Four SVGs derived from Wikimedia Commons originals, normalised through `svgo` to satisfy the icon-registry allowlist:

| Party | Symbol | File | SHA-256 | Raw → Norm bytes | Commons source |
|---|---|---|---|---|---|
| BJP | Lotus (Kamal) | `bjp-lotus.svg`    | `4fd6a651e5b3a3c5c31a61ee0e7df74280ee39cb4bab0ec864350b0fbbde3f3d` | 6239 → 5010 | [Logo_of_the_Bharatiya_Janata_Party.svg](https://commons.wikimedia.org/wiki/File:Logo_of_the_Bharatiya_Janata_Party.svg) |
| INC | Hand | `inc-hand.svg`     | `3a762114324e41729b3d6cf87860944caeb61e1f4f7db71814847d954234ec90` | 7680 → 7576 | [Indian_National_Congress_hand_logo.svg](https://commons.wikimedia.org/wiki/File:Indian_National_Congress_hand_logo.svg) |
| BSP | Elephant | `bsp-elephant.svg` | `f35519bcede457e4e040e38cb6346dc4581d97b8408ed6c0cf050e8d9bb8f026` | 39908 → 21579 | [Elephant_electoral_symbol.svg](https://commons.wikimedia.org/wiki/File:Elephant_electoral_symbol.svg) |
| AAP | Broom (Jhadu) | `aap-broom.svg`    | `b8d7bfb7703dde2a965d70ce2ee4f1d52fc86124a97267f549ef164ec5940012` | 2738 → 1639 | [Aam_Aadmi_Party_logo.svg](https://commons.wikimedia.org/wiki/File:Aam_Aadmi_Party_logo.svg) |

All four pass `sanitizeAndHash` (shared icon-registry allowlist, PR #528).

## Pipeline (svgo normaliser)

1. Resolve direct URL via Commons MediaWiki `action=query&prop=imageinfo` API.
2. Download bytes.
3. `svgo` normalise with: preset-default (`removeViewBox: false`) + `removeDimensions` + `removeStyleElement` + `removeScripts` + `removeAttrs` (class/style/id/inkscape/sodipodi/aria/data/href/xmlns:* extras/version/enable-background/xml:space) + custom plugin stripping `<defs>`/`<metadata>`/`<title>`/`<desc>`/`<text>`/`<image>`/`<foreignObject>`/`<use>`/`<symbol>`/`<marker>`/`<mask>`/`<pattern>`/`<filter>`/`<clipPath>`/`<switch>` elements.
4. Sanity-strip `xml:space` (svgo's `removeAttrs` mishandles colon-prefixed attrs).
5. Run through `sanitizeAndHash` to confirm icon-registry allowlist passes.

Driver: `frontend/.tmp_fetch_and_normalise.mjs` (throwaway; not committed). Reproducible for the remaining ~36 parties in PR-SYM-4a-rest.

## Metadata for PR-SYM-4b

When wiring into `parties.json`, use:
- `asset_source_kind: "commons"`
- `license_label`: per Commons file page (mostly CC-BY-SA-4.0 or PD-shape for ECI freezing-order symbols; verify per-file at PR-SYM-4b time)
- `source_id`: new `sources.parquet` row for `wikimedia_commons` producer (one row covers all parties)
- `symbol_status: "verified"`
- `asset_sha256`: re-verify from committed bytes via `Get-FileHash <file> -Algorithm SHA256` (LF normalisation may shift SHA between worktree and index)

## Not in this PR

- `parties.json` `election_symbol` population — PR-SYM-4b
- `dim_parties` recompile — PR-SYM-4b
- Renderer — PR-SYM-5
- Remaining ~36 Tier 0 parties — PR-SYM-4a-rest (run same pipeline)
