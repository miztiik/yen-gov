"""Regenerate datasets/manifest.json by walking the existing canonical
Parquet tree.

Use case: a manifest-shape bump (e.g. v1.0 -> v1.1 adding table_name +
kind) needs to land in the on-disk control plane without re-running every
ingest. We call the writer's private ``_regenerate_manifest`` helper
directly against ``datasets/`` so the bytes on disk match the new schema.

Run from the repo root:

    python tools/regenerate_manifest.py

CLAUDE.md \u00a72 path discipline: argv is empty; the only path used is the
repo's own ``datasets/`` directory resolved from CWD.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.writer import _regenerate_manifest


def main() -> None:
    datasets_root = Path("datasets").resolve()
    if not datasets_root.is_dir():
        raise SystemExit(
            f"datasets/ not found at {datasets_root!s}; run from the repo root."
        )
    _regenerate_manifest(datasets_root)
    print(f"regenerated {datasets_root / 'manifest.json'}")


if __name__ == "__main__":
    main()
