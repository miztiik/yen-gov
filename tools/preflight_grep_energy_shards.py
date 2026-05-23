"""Pre-flight grep report: cross-references to the 41 legacy energy shards.

Plan-doc `TODO/20260522-phase-2-p1-energy-pivot.md` §4 P.1.A pre-flight
checklist item: *"Pre-stage grep for the 41 legacy filenames across
backend/, frontend/, tools/, admin/, docs/ — quoted file references in
frontend loaders ARE production consumers (lesson 2026-05-21 G.1.c)."*

This script walks the 5 designated trees and reports every file containing
each shard's stem (the .json suffix-stripped filename). The output is the
authoritative input for the P.1.A author: every hit is a deletion-time
breakage risk that needs an entry in the same fused-atomic PR (either as
a writer-stop, a reader-rewrite, or a doc/test update).

Run from the repo root:

    python tools/preflight_grep_energy_shards.py

Writes report to `TODO/20260523-p1a-preflight-grep-report.md`.
"""

from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENERGY_DIR = ROOT / "datasets" / "indicators" / "in" / "energy"
SEARCH_TREES = ["backend", "frontend", "tools", "admin", "docs"]
SKIP_DIRS = {
    "node_modules",
    "test-results",
    "playwright-report",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".venv",
    "yen_gov.egg-info",
}
# Specific filenames to skip even when found in scanned trees. These are
# build/test artifacts checked into the tree but whose content is regenerated.
SKIP_FILENAMES = {
    ".vitest-report.json",
    "tsconfig.tsbuildinfo",
}
TEXT_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".svelte", ".md", ".json",
    ".yaml", ".yml", ".toml", ".html", ".css", ".sh", ".txt",
}
OUT_PATH = ROOT / "TODO" / "20260523-p1a-preflight-grep-report.md"


def iter_text_files(tree: Path):
    for dirpath, dirnames, filenames in os.walk(tree):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname in SKIP_FILENAMES:
                continue
            ext = Path(fname).suffix.lower()
            if ext not in TEXT_EXTS:
                continue
            yield Path(dirpath) / fname


def find_hits(shards: list[str], trees: list[Path]) -> dict[str, list[tuple[str, int, str]]]:
    """Map shard_stem -> list of (rel_path, lineno, line_text)."""
    # Compile one big alternation regex for one-pass scanning.
    # Use word-ish boundaries — match the bare stem with optional .json suffix.
    pattern = re.compile(
        r"(?<![A-Za-z0-9_-])(" + "|".join(re.escape(s) for s in shards) + r")(?![A-Za-z0-9_-])"
    )
    by_shard: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for tree in trees:
        for fpath in iter_text_files(tree):
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not pattern.search(text):
                continue
            rel = fpath.relative_to(ROOT).as_posix()
            for lineno, line in enumerate(text.splitlines(), start=1):
                for m in pattern.finditer(line):
                    by_shard[m.group(1)].append((rel, lineno, line.strip()[:200]))
    return by_shard


def classify(rel_path: str) -> str:
    """Bucket each hit into one of: writer / reader / test / doc / config / other.

    Heuristic: filename + dirpath cues. Conservative defaults to 'other'.
    """
    p = rel_path.lower()
    if "/test" in p or p.startswith("test") or "_test." in p or ".test." in p:
        return "test"
    if "/docs/" in p or p.endswith(".md"):
        return "doc"
    if "/composers/" in p:
        return "writer (composer)"
    if "/sources/" in p:
        return "writer (ingest source)"
    if "/canonical/adapters/" in p:
        return "reader (lift adapter)"
    if "/tools/" in p:
        return "tool"
    if p.startswith("frontend/") and (
        "/lib/" in p or "/routes/" in p or "/components/" in p
    ):
        return "reader (frontend runtime)"
    if "/cli.py" in p or "/admin/" in p:
        return "control-plane"
    return "other"


def main() -> int:
    shards = sorted(
        f.stem for f in ENERGY_DIR.glob("*.json") if not f.name.startswith(".")
    )
    if not shards:
        print(f"no shards found under {ENERGY_DIR}", file=sys.stderr)
        return 1
    trees = [ROOT / t for t in SEARCH_TREES if (ROOT / t).is_dir()]
    by_shard = find_hits(shards, trees)

    # Per-shard summary by classification.
    summary: dict[str, dict[str, int]] = {s: defaultdict(int) for s in shards}
    file_set_per_shard: dict[str, set[str]] = {s: set() for s in shards}
    for shard, hits in by_shard.items():
        for rel, _ln, _line in hits:
            cls = classify(rel)
            summary[shard][cls] += 1
            file_set_per_shard[shard].add(rel)

    # Compose markdown report.
    out: list[str] = []
    out.append("# P.1.A pre-flight grep report — 41 legacy energy shards")
    out.append("")
    out.append("**Last Updated**: 2026-05-23")
    out.append(
        "**Doc class**: TODO/audit per "
        "[ADR-0034](../docs/architecture/decisions/0034-documentation-routing-contract.md). "
        "Generated by [`tools/preflight_grep_energy_shards.py`](../tools/preflight_grep_energy_shards.py). "
        "Re-run before P.1.A is opened to catch any newly-added cross-references."
    )
    out.append(
        "**Cites**: [`TODO/20260522-phase-2-p1-energy-pivot.md`](20260522-phase-2-p1-energy-pivot.md) §4 P.1.A pre-flight checklist item 6 (*\"Pre-stage grep for the 41 legacy filenames across backend/, frontend/, tools/, admin/, docs/\"*)."
    )
    out.append("")
    out.append("## Why this exists")
    out.append("")
    out.append(
        "The P.1.A fused-atomic PR retires legacy `datasets/indicators/in/energy/*.json` "
        "shards as it lifts them onto the canonical Parquet store. Per CLAUDE.md §15 "
        "(fused-atomic with paired tests) and lesson 2026-05-21 G.1.c (frontend reader "
        "audit before any `git rm` under `datasets/`), every cross-reference must be "
        "accounted for in the SAME COMMIT as the deletion — otherwise a quoted path in "
        "a frontend loader, a reader in a composer, or a test fixture turns a green CI "
        "into a runtime 404 the moment someone visits an affected route."
    )
    out.append("")
    out.append(
        "This file is the input ledger. Each of the 41 shards lists the on-disk "
        "references found by a fresh grep over `backend/`, `frontend/`, `tools/`, "
        "`admin/`, `docs/`. The classifier is heuristic (filename + dirpath) — when "
        "in doubt, read the linked line. Hits in `test-results/`, `node_modules/`, "
        "`__pycache__/`, and build outputs are excluded."
    )
    out.append("")
    out.append("## Reference categories")
    out.append("")
    out.append(
        "| Category | Deletion impact | Mitigation in P.1.A |\n"
        "| --- | --- | --- |\n"
        "| **writer (composer)** | Re-emits shard on next composer run after `git rm` | Disable or retire composer in same commit |\n"
        "| **writer (ingest source)** | Re-emits shard on next ingest run after `git rm` | Disable adapter or pin output OFF in same commit |\n"
        "| **reader (lift adapter)** | Lift adapter fails (`FileNotFoundError`) on next replay | Replace shard read with canonical-Parquet query OR keep shard for now and defer deletion |\n"
        "| **reader (frontend runtime)** | Citizen sees 404 on affected route | Wire dispatch to canonical-Parquet loader in same commit |\n"
        "| **test** | pytest / vitest fails on missing fixture | Update fixture or migrate test to canonical contract |\n"
        "| **doc** | Stale path in docs | Update prose in same commit |\n"
        "| **tool** | One-off script fails | Update path or retire script |\n"
        "| **control-plane** | CLI / admin route 404 | Update wiring in same commit |\n"
    )
    out.append("## Summary by shard")
    out.append("")
    out.append(
        "| Shard | Hits | Writers | Readers (frontend) | Readers (lift) | Tests | Docs | Tools | Other |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    for shard in shards:
        s = summary[shard]
        writers = s.get("writer (composer)", 0) + s.get("writer (ingest source)", 0)
        readers_fe = s.get("reader (frontend runtime)", 0)
        readers_lift = s.get("reader (lift adapter)", 0)
        tests = s.get("test", 0)
        docs = s.get("doc", 0)
        tools = s.get("tool", 0)
        other = s.get("other", 0) + s.get("control-plane", 0)
        total = sum(s.values())
        out.append(
            f"| `{shard}` | {total} | {writers} | {readers_fe} | {readers_lift} | "
            f"{tests} | {docs} | {tools} | {other} |"
        )
    out.append("")
    out.append("## Per-shard detail")
    out.append("")
    for shard in shards:
        out.append(f"### `{shard}`")
        out.append("")
        s = summary[shard]
        files_count = len(file_set_per_shard[shard])
        total_hits = sum(s.values())
        out.append(f"- **Files referencing**: {files_count}")
        out.append(f"- **Total hits**: {total_hits}")
        out.append("- **Classification counts**: " + (
            ", ".join(f"{k}: {v}" for k, v in sorted(s.items())) or "(no hits)"
        ))
        if total_hits == 0:
            out.append("")
            out.append("_No references found. Safe to `git rm` from a deletion perspective. "
                       "Still verify the ingest source / composer that originally produced the "
                       "shard is disabled so it does not regenerate._")
            out.append("")
            continue
        out.append("")
        # File-grouped listing (one entry per file, with first-line preview).
        by_file: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for rel, ln, line in by_shard[shard]:
            by_file[rel].append((ln, line))
        # Sort files by classification then path for stable diff.
        ordered_files = sorted(by_file.keys(), key=lambda r: (classify(r), r))
        out.append(
            "| File | Class | Hits | First line |\n"
            "| --- | --- | ---: | --- |"
        )
        for rel in ordered_files:
            entries = by_file[rel]
            cls = classify(rel)
            first_ln, first_line = entries[0]
            # Escape pipe in line preview
            preview = first_line.replace("|", "\\|").replace("`", "")[:120]
            out.append(
                f"| [{rel}#L{first_ln}]({rel.replace(' ', '%20')}#L{first_ln}) | "
                f"{cls} | {len(entries)} | `{preview}` |"
            )
        out.append("")
    out.append("## Generation metadata")
    out.append("")
    out.append(
        f"- Shards scanned: **{len(shards)}**\n"
        f"- Search trees: {', '.join(SEARCH_TREES)}\n"
        f"- Skipped directories: {', '.join(sorted(SKIP_DIRS))}\n"
        f"- Skipped filenames: {', '.join(sorted(SKIP_FILENAMES))}\n"
        f"- Text extensions: {', '.join(sorted(TEXT_EXTS))}\n"
    )
    OUT_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(ROOT).as_posix()} "
          f"({sum(len(v) for v in by_shard.values())} total hits across "
          f"{len(shards)} shards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
