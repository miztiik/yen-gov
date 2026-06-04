# frontend/public/fonts/ - provenance ledger

**Last Updated**: 2026-06-04

This directory carries self-hosted variable-axis font subsets shipped
inside the static bundle per Holy Law #1 (static-first production) and
the U1.2 row of [TODO/20260604-u1-tokens-fonts-subplan.md](../../../TODO/20260604-u1-tokens-fonts-subplan.md).
Each binary below is licensed under the SIL Open Font License 1.1 and is
free to embed, modify, and redistribute under the OFL terms; this file
is the citation ledger required by Holy Law #9 and CLAUDE.md section 12.

The subsets are produced by running [tools/build_fonts.py](../../../tools/build_fonts.py)
which downloads each upstream `.ttf`, runs `fontTools.subset` with the
recipe below, and writes the woff2 here. Re-running is idempotent.

## Why subsets

The full upstream variable fonts ship over a megabyte combined; the
subsets here drop to under 380 KB total without touching the OpenType
layout tables. Subsetting honours the OFL "modified version" terms - we
distribute a derivative and we identify ourselves; we never re-name a
font without distinguishing it from the upstream.

## Common subset invariant - GSUB / GPOS shaping retained

All three subsets pass `--layout-features='*'` so the script-shaping
tables ship intact. A codepoint-only prune is forbidden by plan section
23.5 ("Devanagari subset MUST retain the script's GSUB/GPOS shaping
tables + conjunct glyphs ... never a codepoint-only prune which silently
breaks conjuncts"). The U1.3 Devanagari conjunct render smoke (a
Playwright spec) is the runtime gate that proves this; the subset
recipe below is the build-time discipline that keeps it true.

## Files

### inter-latin.woff2 - 176 KB

- **Family**: Inter
- **Version**: v4.1
- **Author**: Rasmus Andersson (rsms)
- **License**: SIL Open Font License 1.1
- **Upstream**: https://github.com/rsms/inter
- **Source TTF**: `docs/font-files/InterVariable.ttf` (879,708 bytes)
- **Subset recipe**:
  ```
  fonttools subset InterVariable.ttf \
      --output-file=inter-latin.woff2 \
      --flavor=woff2 \
      --layout-features='*' \
      --name-IDs='*' \
      --glyph-names \
      --symbol-cmap \
      --legacy-cmap \
      --notdef-glyph \
      --notdef-outline \
      --recommended-glyphs \
      --unicodes='U+0000-024F,U+1E00-1EFF,U+2000-206F,U+20A0-20CF,U+2070-209F'
  ```
- **unicode-range rationale**: Basic Latin + Latin-1 Supplement + Latin
  Extended-A and -B + Latin Extended Additional (Indian English
  transliterations carry diacritics in this block) + General
  Punctuation + Currency Symbols (Indian Rupee U+20B9) + Superscripts
  and Subscripts.
- **Subset date**: 2026-06-04

### noto-sans-devanagari.woff2 - 178 KB

- **Family**: Noto Sans Devanagari
- **Version**: v2.006
- **Author**: Google / The Noto Project Authors
- **License**: SIL Open Font License 1.1
- **Upstream**: https://github.com/notofonts/devanagari
- **Source TTF**: extracted from release zip
  `NotoSansDevanagari-v2.006.zip:NotoSansDevanagari/googlefonts/variable-ttf/NotoSansDevanagari[wdth,wght].ttf`
  (647,144 bytes)
- **Subset recipe**:
  ```
  fonttools subset 'NotoSansDevanagari[wdth,wght].ttf' \
      --output-file=noto-sans-devanagari.woff2 \
      --flavor=woff2 \
      --layout-features='*' \
      --name-IDs='*' \
      --glyph-names \
      --symbol-cmap \
      --legacy-cmap \
      --notdef-glyph \
      --notdef-outline \
      --recommended-glyphs \
      --unicodes='U+0900-097F,U+200C-200D,U+25CC'
  ```
- **unicode-range rationale**: Devanagari block + ZWNJ (U+200C) + ZWJ
  (U+200D) for manual conjunct authoring + dotted circle (U+25CC)
  which the script-shaping engine draws over an orphan combining mark
  (so it MUST ship to render errors cleanly).
- **Post-subset shaping audit**: 210 GSUB lookups + 21 GPOS lookups +
  632 glyphs + 131 cmap entries; all three kSha components (KA U+0915,
  VIRAMA U+094D, SSA U+0937) are mapped. Verified by reading the
  fontTools tables of the produced woff2 on the same commit that
  produced it (see PR body).
- **Subset date**: 2026-06-04

### outfit-latin.woff2 - 25 KB

- **Family**: Outfit
- **Version**: 2024 release (single-axis weight variable)
- **Author**: Outfitio
- **License**: SIL Open Font License 1.1
- **Upstream**: https://github.com/Outfitio/Outfit-Fonts
- **Source TTF**: `fonts/variable/Outfit[wght].ttf` (110,884 bytes)
- **Subset recipe**:
  ```
  fonttools subset 'Outfit[wght].ttf' \
      --output-file=outfit-latin.woff2 \
      --flavor=woff2 \
      --layout-features='*' \
      --name-IDs='*' \
      --glyph-names \
      --symbol-cmap \
      --legacy-cmap \
      --notdef-glyph \
      --notdef-outline \
      --recommended-glyphs \
      --unicodes='U+0020-007E'
  ```
- **unicode-range rationale**: wordmark-only (the LeftRail
  `.brand-wordmark` "Yen Gov" mark with the Ashoka Chakra between);
  Basic Latin printable range is more than enough.
- **Subset date**: 2026-06-04

## License text

The full SIL Open Font License 1.1 lives upstream with each project
(see the Upstream links above). The OFL grants embedding, modification,
and redistribution under terms summarised here:

- Each font remains under OFL 1.1; subsets are derivatives and remain
  under the same licence.
- The font name "Inter", "Noto Sans Devanagari", and "Outfit" remain
  the authors' marks; we ship subsets of those names verbatim and do
  not claim authorship.
- This LICENCES.md is the attribution the OFL "Acknowledgement"
  paragraph requires.

## See also

- [tools/build_fonts.py](../../../tools/build_fonts.py) - the
  reproducible subset script.
- [TODO/20260604-u1-tokens-fonts-subplan.md](../../../TODO/20260604-u1-tokens-fonts-subplan.md) -
  the sub-plan that commissions U1.2.
- [CLAUDE.md](../../../CLAUDE.md) Holy Law #9 (provenance) + section 12
  (citation ledger doctrine).
