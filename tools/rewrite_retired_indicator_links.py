"""One-shot link rewriter for Phase #4a of TODO/20260517-coverage-temporal-range-plan.md.

The auto-generated per-indicator markdown tree at ``docs/reference/indicators/``
was retired 2026-05-17 (Phase #4a). Hand-authored topic docs at
``docs/reference/topics/*.md`` still contain ~150 markdown links into that tree.
This script rewrites each broken link to point at the artifact JSON under
``datasets/indicators/in/<topic>/<id>.json`` (github-browsable, deterministic,
the single source of truth).

Rules:
- ``](../indicators/<topic>/<id>.md)``  -> ``](../../../datasets/indicators/in/<topic>/<id>.json)``
- ``](../indicators/<topic>/)``         -> ``](../../../datasets/indicators/in/<topic>/)``
- Link text is preserved verbatim (still reads as ``fiscal/union_gross_fiscal_deficit``).

Idempotent: a second run after a clean run is a no-op.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
TOPICS_DIR = ROOT / "docs" / "reference" / "topics"

LEAF_RE = re.compile(r"\]\(\.\./indicators/([a-z0-9_]+)/([a-z0-9_]+)\.md\)")
INDEX_RE = re.compile(r"\]\(\.\./indicators/([a-z0-9_]+)/\)")


def rewrite(text: str) -> tuple[str, int]:
    n = 0

    def leaf_sub(m: re.Match[str]) -> str:
        nonlocal n
        n += 1
        topic, basename = m.group(1), m.group(2)
        return f"](../../../datasets/indicators/in/{topic}/{basename}.json)"

    def index_sub(m: re.Match[str]) -> str:
        nonlocal n
        n += 1
        topic = m.group(1)
        return f"](../../../datasets/indicators/in/{topic}/)"

    out = LEAF_RE.sub(leaf_sub, text)
    out = INDEX_RE.sub(index_sub, out)
    return out, n


def main() -> int:
    total = 0
    changed = 0
    for md in sorted(TOPICS_DIR.glob("*.md")):
        original = md.read_text(encoding="utf-8")
        new, n = rewrite(original)
        if new != original:
            md.write_text(new, encoding="utf-8")
            changed += 1
        total += n
        print(f"  {md.relative_to(ROOT).as_posix()}: {n} link(s)")
    print(f"\nRewrote {total} link(s) across {changed} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
