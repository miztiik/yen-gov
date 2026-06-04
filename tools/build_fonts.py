"""Subset the three upstream variable fonts into self-hosted woff2 files.

Operator-only one-time runner (CLAUDE.md repo topology section 3 - tools/
is allowed to hit the network for an operator-driven build artefact).
Production code paths under backend/ and frontend/ NEVER fetch at
runtime - the woff2 outputs of this script are committed to
frontend/public/fonts/ and ship in the static bundle.

Recipe per plan section 21.7 + 23.5 + the U1.2 row of
TODO/20260604-u1-tokens-fonts-subplan.md:

- Inter (SIL OFL 1.1) - the variable-axis Latin subset for UI + body +
  data text. unicode-range covers Basic Latin, Latin-1 Supplement,
  Latin Extended-A, Latin Extended Additional (the diacritic block we
  hit for Indian English place-name transliterations), General
  Punctuation, Currency Symbols, and Superscripts and Subscripts.
- Noto Sans Devanagari (SIL OFL 1.1) - script subset for Hindi /
  Marathi rendering. unicode-range covers U+0900-097F (Devanagari
  block), U+200C-200D (ZWNJ/ZWJ - required to author conjuncts
  manually), U+25CC (dotted circle - the fallback the script engine
  draws over an orphan combining mark, so it must ship to render
  errors cleanly).
- Outfit (SIL OFL 1.1) - the wordmark-only subset, Basic Latin only.

All three pass --layout-features='*' so GSUB / GPOS shaping tables
ship intact. A codepoint-only prune would silently break conjuncts
(plan section 23.5 hard rule); this script enforces the recipe so the
next operator does not regress.

The script is idempotent: re-running re-downloads the upstream .ttf
files into a fresh temp dir, re-runs the same subset commands, and
writes the same bytes (fonttools subset is deterministic for a fixed
input + invocation).

Usage:
    python tools/build_fonts.py

Writes:
    frontend/public/fonts/inter-latin.woff2
    frontend/public/fonts/noto-sans-devanagari.woff2
    frontend/public/fonts/outfit-latin.woff2
"""

from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import NamedTuple

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "frontend" / "public" / "fonts"


class FontJob(NamedTuple):
    name: str
    out_filename: str
    unicodes: str
    # Either a direct .ttf URL, or a (zip_url, member_path_in_zip) tuple
    # for upstreams that only release built fonts via release zips.
    source_url: str
    zip_member: str | None  # path inside zip when source_url is a zip


JOBS: list[FontJob] = [
    FontJob(
        name="Inter (Latin variable)",
        out_filename="inter-latin.woff2",
        unicodes=(
            "U+0000-024F,"  # Basic Latin + Latin-1 + Latin Extended-A/B
            "U+1E00-1EFF,"  # Latin Extended Additional (diacritics)
            "U+2000-206F,"  # General Punctuation
            "U+20A0-20CF,"  # Currency Symbols (Indian Rupee U+20B9)
            "U+2070-209F"  # Superscripts and Subscripts
        ),
        source_url=(
            "https://github.com/rsms/inter/raw/v4.1/docs/font-files/"
            "InterVariable.ttf"
        ),
        zip_member=None,
    ),
    FontJob(
        name="Noto Sans Devanagari (variable, shaped)",
        out_filename="noto-sans-devanagari.woff2",
        unicodes=(
            "U+0900-097F,"  # Devanagari block
            "U+200C-200D,"  # ZWNJ / ZWJ (manual conjunct control)
            "U+25CC"  # dotted circle (script-engine fallback for orphans)
        ),
        source_url=(
            "https://github.com/notofonts/devanagari/releases/download/"
            "NotoSansDevanagari-v2.006/NotoSansDevanagari-v2.006.zip"
        ),
        zip_member=(
            "NotoSansDevanagari/googlefonts/variable-ttf/"
            "NotoSansDevanagari[wdth,wght].ttf"
        ),
    ),
    FontJob(
        name="Outfit (Latin, wordmark only)",
        out_filename="outfit-latin.woff2",
        unicodes="U+0020-007E",  # Basic Latin printable range
        source_url=(
            "https://github.com/Outfitio/Outfit-Fonts/raw/main/fonts/"
            "variable/Outfit%5Bwght%5D.ttf"
        ),
        zip_member=None,
    ),
]


def _download(url: str, dest: Path) -> None:
    print(f"  downloading: {url}")
    with urllib.request.urlopen(url) as resp:
        dest.write_bytes(resp.read())
    print(f"  -> {dest} ({dest.stat().st_size:,} bytes)")


def _extract_member(zip_path: Path, member: str, dest: Path) -> None:
    print(f"  extracting: {member}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Some zips use forward slashes verbatim; resolve via the
        # namelist to be tolerant of case / separator drift.
        members = zf.namelist()
        if member not in members:
            # Try fallback: case-insensitive match.
            for m in members:
                if m.lower() == member.lower():
                    member = m
                    break
            else:
                raise FileNotFoundError(
                    f"member {member!r} not found in {zip_path}; "
                    f"available: {members[:10]}..."
                )
        dest.write_bytes(zf.read(member))
    print(f"  -> {dest} ({dest.stat().st_size:,} bytes)")


def _subset(ttf_path: Path, out_path: Path, unicodes: str) -> None:
    cmd = [
        sys.executable,
        "-m",
        "fontTools.subset",
        str(ttf_path),
        f"--output-file={out_path}",
        "--flavor=woff2",
        "--layout-features=*",  # KEEP all GSUB / GPOS shaping tables
        "--name-IDs=*",
        "--glyph-names",
        "--symbol-cmap",
        "--legacy-cmap",
        "--notdef-glyph",
        "--notdef-outline",
        "--recommended-glyphs",
        f"--unicodes={unicodes}",
    ]
    print("  subset:", " ".join(cmd[2:]))
    subprocess.run(cmd, check=True)
    print(f"  -> {out_path} ({out_path.stat().st_size:,} bytes)")


def run() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for job in JOBS:
            print(f"\n[{job.name}]")
            ttf_path = tmp_dir / f"{job.out_filename}.ttf"
            if job.zip_member is None:
                _download(job.source_url, ttf_path)
            else:
                zip_path = tmp_dir / f"{job.out_filename}.zip"
                _download(job.source_url, zip_path)
                _extract_member(zip_path, job.zip_member, ttf_path)
            out_path = OUT_DIR / job.out_filename
            _subset(ttf_path, out_path, job.unicodes)
    print("\nAll three subsets written under:", OUT_DIR.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
