# PR-SYM-4a.i pilot batch: 4 national-party election symbols

Date: 2026-06-01. Closes pilot half of PR-SYM-4a in `TODO/20260527-party-symbol-assets-plan.md`.

## What ships

Four hand-authored monochrome SVGs under `frontend/public/party-symbols/`:

| Party | Symbol | File | SHA-256 (asset_sha256) | Bytes |
|---|---|---|---|---|
| BJP | Lotus (Kamal) | `bjp-lotus.svg` | `7a85710b4443dcf80a1ca1061dd85db9f72a29c867cf17a6a9b36be15145bf13` | 613 |
| INC | Hand (right palm) | `inc-hand.svg` | `56a07a08d71e6f85f2708d998a2e047f760daa0e457bb92473c687741fdffbde` | 451 |
| BSP | Elephant | `bsp-elephant.svg` | `3bba649e88598e7e0f6cb3607d6f260f203e846d94a9f0b160c140d93300b8a4` | 549 |
| AAP | Broom (Jhadu) | `aap-broom.svg` | `5bd3c9e037104e9b9a1eb052c51e1d4f7910254a2581daa2fee3e4ffc9bbe9e3` | 531 |

All four:
- pass `sanitizeAndHash` (shared icon-registry allowlist, PR #528);
- use only `path`/`circle` primitives + `currentColor` for the renderer's CSS-driven theming;
- ship as `asset_source_kind: "generated_from_eci"`, `license_label: "project-editorial"`, `symbol_status: "verified"` (shape is the ECI-frozen symbol; bytes are yen-gov-authored).

## Why hand-authored, not Commons-direct

Structural probe of 4 Commons originals (`Logo_of_the_Bharatiya_Janata_Party.svg`,
`Indian_National_Congress_hand_logo.svg`, `Elephant_electoral_symbol.svg`,
`Aam_Aadmi_Party_logo.svg`) showed 3 of 4 use allowlist-forbidden constructs:

- `aap-broom`: inline `style` attr (forbidden);
- `bjp-lotus`: `<style>` element + `class` attr (forbidden);
- `bsp-elephant`: `<defs>` + `<metadata>` + Inkscape namespace + 30+ inkscape:* attrs (forbidden);
- `inc-hand`: only `circle`/`path` + allowlisted attrs (would have passed).

Hand-authoring all four wins on three axes that mattered more than 1/4 Commons-direct salvage:

1. **Uniform visual weight** across the roster (citizen experience — Jony / Citizen verdict).
2. **No per-file Commons licence chasing** (we'd still need a `sources.parquet` row per producer per Commons file).
3. **Scales to ~40 parties** in PR-SYM-4a-full without per-file allowlist-failure spelunking.

## Not in this PR

- `parties.json` population (recognition + election_symbol object) — PR-SYM-4b.
- `dim_parties.parquet` recompile — PR-SYM-4b.
- Renderer + chart wiring — PR-SYM-5.
- Remaining ~36 Tier 0 parties — PR-SYM-4a-rest (next pilot continuation).

The SHA-256 column above was computed pre-commit on the LF-normalised bytes.
**PR-SYM-4b must re-verify each `asset_sha256` from the committed bytes** (e.g.
`Get-FileHash frontend/public/party-symbols/<file>.svg -Algorithm SHA256`) before
writing into `parties.json`. Git's LF normalisation may shift the bytes between
the worktree-at-author-time and the checked-out repo.
