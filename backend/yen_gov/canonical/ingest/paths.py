"""The single path-emit seam for the ingest pipeline (CLAUDE.md section 2).

Any filesystem path that leaves the process - written into a JSON log line, an
emitted artifact, an error message, a checkpoint receipt - routes through
``to_repo_relative_posix`` first. The contract a path must satisfy the moment it
crosses the process boundary: relative to the repository root, POSIX-separated,
and carrying no drive letter. Enforced here once, fail-loud, so no caller has to
re-implement it (and none gets it subtly wrong on Windows).

The module imports nothing beyond the standard library; it is a pure leaf
utility, not infrastructure.
"""

from __future__ import annotations

from pathlib import Path, PureWindowsPath

__all__ = ["to_repo_relative_posix"]


def to_repo_relative_posix(p: Path | str, *, repo_root: Path | str) -> str:
    """Relativise ``p`` against ``repo_root`` and return a POSIX path string.

    Args:
        p: the path to relativise. An absolute path is made relative to
            ``repo_root``; a relative path is interpreted as already
            repo-root-relative and normalised.
        repo_root: the repository root every emitted path is relative to.

    Returns:
        A clean relative POSIX string, e.g. ``"datasets/data/x.csv"``.

    Raises:
        ValueError: if ``p`` resolves outside ``repo_root`` - a different drive
            (a surviving drive letter) or an escape via ``..``. Fail-loud per
            CLAUDE.md section 2: a path that cannot be expressed cleanly
            relative to the repo must never leak its absolute, drive-qualified
            form into a log line or artifact.
    """
    root = Path(repo_root).resolve()
    target = Path(p)
    if not target.is_absolute():
        # An already-relative input is interpreted as repo-root-relative.
        target = root / target
    target = target.resolve()
    try:
        rel = target.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"path {target.as_posix()!r} escapes repo_root {root.as_posix()!r}"
        ) from exc
    posix = rel.as_posix()
    # Defence in depth on a path-traversal boundary: a successful relative_to
    # cannot leave a drive letter or a leading '..', but we re-assert both so
    # the contract is enforced at the seam rather than merely assumed.
    if PureWindowsPath(posix).drive:
        raise ValueError(f"path {posix!r} retains a drive letter after relativising")
    if posix == ".." or posix.startswith("../"):
        raise ValueError(
            f"path {posix!r} escapes repo_root {root.as_posix()!r}"
        )
    return posix
