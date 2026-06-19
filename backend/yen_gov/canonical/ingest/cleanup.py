"""``ingest clean`` -- sweep stale ingest ephemera under the runtime base (Row 12).

The pipeline leaves two kinds of regenerable ephemera under the runtime base
directory (``core.runtime.resolve_runtime_dir``, default ``<repo>/.runtime``):

* ``logs/<run_id>/`` -- one stage-tagged JSON-lines stream per run (Row 3).
* ``cache/ingest/<adapter_slug>/`` -- the raw-bytes fetch cache (Row 5); a
  within-run claim-check, never the delta contract (that is the committed
  checkpoint's ``raw_sha256``).

``clean`` removes entries older than a retention window. The DURABLE state the
pipeline keeps -- the committed year-checkpoint at
``datasets/_ops/ingest-state/<adapter_slug>.json`` -- lives OUTSIDE the runtime
base and is therefore structurally unreachable here; the under-runtime-base
assertion makes that a fail-loud guarantee, not merely a convention.

Design rulings (Gregor = contracts, Fowler = craft), baked here so a later row
does not re-litigate them:

* **Targets are runtime-base-relative, asserted under the base.**
  :data:`CLEAN_TARGETS` names the ephemera subtrees relative to the runtime base
  (``logs``, ``cache/ingest``). Every target is routed through
  :func:`paths.to_repo_relative_posix` with the runtime base as the root, which
  FAILS LOUD on a target that escapes the base (a stray ``..`` or a drive
  letter). So a careless future edit that pointed a target at ``datasets/_ops``
  (durable state) or anywhere outside the base is REFUSED, not silently swept.
* **All targets are validated up front.** A refused target aborts BEFORE any
  deletion, so a bad entry can never leave a half-done sweep.
* **Age is the NEWEST mtime in the entry.** A run dir's own mtime does not
  advance when a log LINE is appended (only when a child is added/removed), so a
  long, still-active run could look stale by top-level mtime. Taking the max
  mtime over the entry's whole subtree keeps a recently-written run from being
  swept. For a plain-file entry it is just the file mtime.
* **``days < 90`` without ``force`` aborts.** 90 days is the retention floor; a
  shorter window is an aggressive sweep that must be opted into explicitly, so an
  over-eager ``clean --days 1`` cannot quietly delete a run an operator is still
  inspecting.
* **``dry_run`` mutates nothing.** It returns the SAME ``CleanReport.removed``
  list it would have deleted, so an operator can preview the sweep.
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from yen_gov.canonical.ingest.paths import to_repo_relative_posix

__all__ = [
    "CLEAN_TARGETS",
    "DEFAULT_RETENTION_DAYS",
    "CleanReport",
    "CleanupError",
    "clean",
]

#: Retention floor (days). Both the default window AND the threshold below which
#: a sweep needs ``force=True``. A run older than this is regenerable scrap.
DEFAULT_RETENTION_DAYS = 90

#: Ephemera subtrees, relative to the runtime base, that ``clean`` sweeps. These
#: mirror the producers: ``logs`` (``core.logging``) and ``cache/ingest``
#: (``canonical.ingest.fetch.CACHE_DIR_REL`` == ``.runtime/cache/ingest``). The
#: committed checkpoint under ``datasets/_ops/`` is deliberately ABSENT -- it is
#: durable state, not ephemera, and the under-base assertion would refuse it.
CLEAN_TARGETS: tuple[str, ...] = ("logs", "cache/ingest")

_SECONDS_PER_DAY = 86_400


class CleanupError(RuntimeError):
    """A refused clean: a target escaped the runtime base, or ``days < 90`` w/o force."""


@dataclass(frozen=True)
class CleanReport:
    """What ``clean`` removed (or, in a dry run, WOULD remove).

    ``removed`` entries are POSIX paths relative to the runtime base
    (``logs/<run_id>``, ``cache/ingest/<adapter_slug>``), routed through the
    path-emit seam so nothing absolute or drive-qualified leaks into CLI output.
    """

    removed: tuple[str, ...]
    dry_run: bool

    @property
    def count(self) -> int:
        return len(self.removed)


def _newest_mtime(entry: Path) -> float:
    """Return the most recent mtime in ``entry`` (itself + every descendant).

    Using the subtree max (not the entry's own mtime) means a run dir whose log
    file was just appended to is treated as fresh even though the directory's own
    mtime is older.
    """
    newest = entry.stat().st_mtime
    if entry.is_dir():
        for child in entry.rglob("*"):
            try:
                mtime = child.stat().st_mtime
            except OSError:
                # A vanished / again-unreadable child cannot keep the entry
                # alive; skip it rather than abort the whole sweep.
                continue
            if mtime > newest:
                newest = mtime
    return newest


def _target_dir(runtime_dir: Path, sub: str) -> Path:
    """Resolve one CLEAN_TARGET under ``runtime_dir``, asserting it stays inside.

    Routes through :func:`to_repo_relative_posix` with the runtime base as the
    root: that relativises + fails loud on a drive letter or a ``..`` escape. A
    target that resolves OUTSIDE the runtime base is REFUSED (``CleanupError``),
    so the sweep can never reach durable state (e.g. ``datasets/_ops/``).
    """
    target = runtime_dir / sub
    try:
        to_repo_relative_posix(target, repo_root=runtime_dir)
    except ValueError as exc:
        raise CleanupError(
            f"clean target {sub!r} resolves outside the runtime base "
            f"{Path(runtime_dir).as_posix()!r}: {exc}"
        ) from exc
    return target


def clean(
    *,
    days: int = DEFAULT_RETENTION_DAYS,
    force: bool = False,
    dry_run: bool = False,
    runtime_dir: Path | str,
    targets: Sequence[str] = CLEAN_TARGETS,
    now: float | None = None,
) -> CleanReport:
    """Remove ingest ephemera older than ``days`` under the runtime base.

    Args:
        days: retention window. Entries whose newest mtime is older than this are
            removed. Defaults to the 90-day floor.
        force: permit ``days < 90``. Without it, a sub-floor window ABORTS.
        dry_run: when True, mutate NOTHING -- the returned ``CleanReport.removed``
            lists what WOULD be removed.
        runtime_dir: the runtime base directory (the dir that contains ``logs/``
            and ``cache/ingest/``); resolve it via
            ``core.runtime.resolve_runtime_dir`` so the ``YEN_GOV_RUNTIME_DIR``
            override is honoured.
        targets: the runtime-base-relative subtrees to sweep (defaults to
            :data:`CLEAN_TARGETS`; injectable so the escape guard is testable).
        now: epoch seconds to measure age against (defaults to ``time.time()``).

    Returns:
        A :class:`CleanReport` of the entries removed (or, in a dry run, that
        would be).

    Raises:
        CleanupError: if ``days < 90`` without ``force``, or a target escapes the
            runtime base.
    """
    if days < DEFAULT_RETENTION_DAYS and not force:
        raise CleanupError(
            f"--days {days} is below the {DEFAULT_RETENTION_DAYS}-day retention "
            "floor; pass --force to sweep a shorter window"
        )

    base = Path(runtime_dir)
    cutoff = (time.time() if now is None else now) - days * _SECONDS_PER_DAY

    # Validate every target up front so a target that escapes the runtime base
    # aborts BEFORE any deletion -- never a half-done sweep.
    target_dirs = [_target_dir(base, sub) for sub in targets]

    removed: list[str] = []
    for target_dir in target_dirs:
        if not target_dir.is_dir():
            continue
        for entry in sorted(target_dir.iterdir()):
            if _newest_mtime(entry) >= cutoff:
                continue
            rel = to_repo_relative_posix(entry, repo_root=base)
            if not dry_run:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
            removed.append(rel)

    return CleanReport(removed=tuple(removed), dry_run=dry_run)
