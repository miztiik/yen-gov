"""Where ephemeral runtime state lives (``.runtime/``), with an operator override.

The ingest pipeline writes two kinds of ephemera under a single runtime base
directory: the stage-tagged log stream (``core.logging`` -> ``.runtime/logs/``)
and the raw-bytes fetch cache (``canonical.ingest.fetch`` ->
``.runtime/cache/ingest/``). Both are gitignored, regenerated on the next run,
and NEVER a contract surface (CLAUDE.md section 2: state that outlives a run
belongs in ``datasets/`` / ``config/`` / ``docs/``, not ``.runtime/``).

``resolve_runtime_dir`` is the single seam that answers "where is the runtime
base?". By default it is ``<repo_root>/.runtime``; an operator may relocate it
wholesale (e.g. onto a roomy scratch volume) via the ``YEN_GOV_RUNTIME_DIR``
env var. Centralising it here keeps logging (which WRITES ephemera) and
``ingest clean`` (which SWEEPS it) pointed at the same base, so a relocated
runtime dir stays coherent across write and cleanup.

Pure stdlib leaf: imports only ``os`` + ``pathlib`` and depends on nothing in
``yen_gov``, so ``core.logging`` can use it without a layering inversion.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["RUNTIME_DIR_ENV", "resolve_runtime_dir"]

#: Env var an operator sets to relocate the ephemeral runtime base directory
#: wholesale. Unset (or empty) -> the default ``<repo_root>/.runtime``.
RUNTIME_DIR_ENV = "YEN_GOV_RUNTIME_DIR"


def resolve_runtime_dir(runtime_root: Path | str) -> Path:
    """Return the runtime base directory ephemera live under.

    Args:
        runtime_root: the parent the default ``.runtime/`` hangs off (the repo
            root in normal use).

    Returns:
        ``$YEN_GOV_RUNTIME_DIR`` when that env var is set and non-empty;
        otherwise ``<runtime_root>/.runtime``. The result is the directory that
        directly contains ``logs/`` and ``cache/ingest/``.
    """
    override = os.environ.get(RUNTIME_DIR_ENV)
    if override:
        return Path(override)
    return Path(runtime_root) / ".runtime"
