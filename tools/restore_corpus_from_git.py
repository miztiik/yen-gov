"""Restore the per-AC JSON corpus from a git commit into a gitignored location.

Walks ``git ls-tree`` at ``--from-ref`` for paths under ``datasets/elections``
matching ``<event>/<state>/results/*.json`` (and per-event ``parties.json``),
then writes the byte-identical blob contents into ``--into`` rebased to
``<event>/<state>/...``.

Why: commit ``016c2352`` deleted the per-AC JSON corpus the canonical-backfill
driver reads. To re-run the backfill with the expanded taxonomy (32 -> 108)
+ the new ``party_short_raw`` column without re-fetching from ECI, we need
the corpus back on disk. Restoring under ``datasets/ephemeral/legacy-corpus/``
(gitignored via ``datasets/ephemeral/.gitignore = *``) keeps the canonical
tree clean. The backfill CLI's new ``--corpus-root`` flag points at this dir.

Usage:

    python tools/restore_corpus_from_git.py \\
        --from-ref 2267a971 \\
        --into datasets/ephemeral/legacy-corpus/elections

Idempotent: re-run overwrites existing files with the same blob bytes.
Skips anything under ``_`` prefixed paths (legacy sentinel dirs).
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
from pathlib import Path

# PowerShell + cp1252 stdout choke on non-ASCII; force UTF-8 with replace.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _git(*args: str) -> str:
    """Run a git command, return stdout text. Raises CalledProcessError on
    non-zero exit (matches the rest of the tools/ scripts in this repo)."""
    return subprocess.check_output(
        ("git", *args), text=True, encoding="utf-8", errors="replace",
    )


def _list_corpus_paths(ref: str, prefix: str) -> list[str]:
    """Return repo-relative paths at ``ref`` under ``prefix`` that look like
    per-AC results JSON or per-event parties JSON."""
    out = _git("ls-tree", "-r", "--name-only", ref, "--", prefix)
    paths: list[str] = []
    for line in out.splitlines():
        # Match <event>/<state>/results/<N>.json
        # or   <event>/<state>/parties.json
        # or   <event>/<state>/<anything>.json (be permissive — backfill ignores extras)
        if not line.endswith(".json"):
            continue
        # Filter out _-prefixed sentinel/legacy dirs (e.g. _inventory.json).
        # Keep them — backfill reads results/*.json so anything outside that
        # subtree is harmless on disk. Cheap to restore, simpler logic.
        paths.append(line)
    return paths


def _restore(ref: str, repo_path: str, dest: Path) -> int:
    """Write the blob at ``ref:repo_path`` to ``dest``. Returns bytes written."""
    raw = subprocess.check_output(
        ("git", "show", f"{ref}:{repo_path}"),
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return len(raw)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-ref", required=True, help="git ref to restore from (e.g. 2267a971)")
    ap.add_argument(
        "--into", required=True, type=Path,
        help="destination dir (repo-relative or absolute). Will be created.",
    )
    ap.add_argument(
        "--prefix", default="datasets/elections",
        help="repo-relative path prefix to walk (default: datasets/elections)",
    )
    args = ap.parse_args(argv)

    ref: str = args.from_ref
    dest_root: Path = args.into.resolve()
    prefix: str = args.prefix

    # Resolve ref to a concrete sha so error messages are unambiguous.
    sha = _git("rev-parse", ref).strip()
    print(f"resolved {ref} -> {sha}")

    paths = _list_corpus_paths(sha, prefix)
    if not paths:
        print(f"no JSON paths found under {prefix} at {sha}", file=sys.stderr)
        return 2
    print(f"found {len(paths)} JSON paths under {prefix}")

    # Re-base every path: drop the leading "datasets/elections/" so the dest
    # tree starts at <event>/<state>/...; backfill's corpus_root then points
    # straight at dest_root.
    rebase_prefix = prefix.rstrip("/") + "/"
    total_bytes = 0
    written = 0
    for i, p in enumerate(paths, 1):
        if not p.startswith(rebase_prefix):
            print(f"  [skip] unexpected path: {p}", file=sys.stderr)
            continue
        rel = p[len(rebase_prefix):]
        dest = dest_root / rel
        try:
            total_bytes += _restore(sha, p, dest)
            written += 1
        except subprocess.CalledProcessError as exc:
            print(f"  [FAIL] {p}: {exc}", file=sys.stderr)
            continue
        if i % 500 == 0:
            print(f"  ... {i}/{len(paths)} ({total_bytes / 1e6:.1f} MB)")

    print(f"done: wrote {written} files ({total_bytes / 1e6:.2f} MB) under {dest_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
