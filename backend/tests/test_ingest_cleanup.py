"""Tests for ``ingest clean`` -- the runtime-ephemera sweep (Row 12).

Covers the four gates (dry-run no-op; targets resolve under the runtime base; a
target outside the base is refused; ``days < 90`` without force aborts), the
oracle (an old log dir is removed while the committed ``_ops`` checkpoint is left
untouched), and the ``YEN_GOV_RUNTIME_DIR`` override. No network, no real corpus
-- a fake runtime + ``_ops`` tree under ``tmp_path``.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from yen_gov.canonical.ingest.cleanup import CleanupError, clean
from yen_gov.core.runtime import RUNTIME_DIR_ENV, resolve_runtime_dir

_DAY = 86_400


def _age(path: Path, days_ago: float) -> None:
    """Set the mtime of ``path`` (and, if a dir, every descendant) into the past."""
    ts = time.time() - days_ago * _DAY
    paths = [path]
    if path.is_dir():
        paths.extend(path.rglob("*"))
    for p in paths:
        os.utime(p, (ts, ts))


def _seed_run(runtime_dir: Path, run_id: str, *, age_days: float) -> Path:
    """Create ``runtime_dir/logs/<run_id>/yen-gov.log``, aged ``age_days`` back."""
    run_dir = runtime_dir / "logs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "yen-gov.log").write_text(
        '{"event":"fetch.started"}\n', encoding="utf-8"
    )
    _age(run_dir, age_days)
    return run_dir


def _seed_checkpoint(repo_root: Path, slug: str) -> Path:
    """Create the committed checkpoint ``datasets/_ops/ingest-state/<slug>.json``."""
    cp = repo_root / "datasets" / "_ops" / "ingest-state" / f"{slug}.json"
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"adapter_slug": slug, "years": {}}), encoding="utf-8")
    # Aged too, to prove survival is about LOCATION (outside the base), not age.
    _age(cp, 400)
    return cp


def test_dry_run_mutates_nothing(tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".runtime"
    run_dir = _seed_run(runtime_dir, "20250101-aaaa0001", age_days=200)

    report = clean(days=90, force=False, dry_run=True, runtime_dir=runtime_dir)

    assert report.dry_run is True
    assert "logs/20250101-aaaa0001" in report.removed
    assert run_dir.exists(), "dry-run must not delete anything"


def test_recent_entry_survives(tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".runtime"
    fresh = _seed_run(runtime_dir, "20260619-bbbb0002", age_days=1)

    report = clean(days=90, force=False, dry_run=False, runtime_dir=runtime_dir)

    assert report.removed == ()
    assert fresh.exists()


def test_refuses_target_outside_runtime(tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".runtime"
    old_run = _seed_run(runtime_dir, "20250101-ffff0006", age_days=200)

    # A target that escapes the runtime base must be refused before any deletion.
    with pytest.raises(CleanupError):
        clean(
            days=90,
            force=False,
            dry_run=False,
            runtime_dir=runtime_dir,
            targets=("logs", "../../datasets/_ops"),
        )

    assert old_run.exists(), "a refused target must abort before any deletion"


def test_days_below_floor_without_force_aborts(tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".runtime"
    run_dir = _seed_run(runtime_dir, "20250101-cccc0003", age_days=200)

    with pytest.raises(CleanupError):
        clean(days=30, force=False, dry_run=False, runtime_dir=runtime_dir)
    assert run_dir.exists(), "an aborted sub-floor sweep deletes nothing"

    # ... but --force permits the aggressive sweep.
    report = clean(days=30, force=True, dry_run=False, runtime_dir=runtime_dir)
    assert "logs/20250101-cccc0003" in report.removed
    assert not run_dir.exists()


def test_oracle_removes_log_keeps_checkpoint(tmp_path: Path) -> None:
    repo_root = tmp_path
    runtime_dir = repo_root / ".runtime"
    old_run = _seed_run(runtime_dir, "20250101-dddd0004", age_days=200)
    checkpoint = _seed_checkpoint(repo_root, "rbi-handbook")

    report = clean(days=90, force=False, dry_run=False, runtime_dir=runtime_dir)

    assert not old_run.exists(), "the stale log run dir must be swept"
    assert checkpoint.exists(), "the committed _ops checkpoint must be untouched"
    assert checkpoint.read_text(encoding="utf-8"), "checkpoint content intact"
    assert "logs/20250101-dddd0004" in report.removed
    # The checkpoint is never even a candidate -- it lives outside the base.
    assert all("_ops" not in rel for rel in report.removed)


def test_clean_also_sweeps_fetch_cache(tmp_path: Path) -> None:
    runtime_dir = tmp_path / ".runtime"
    cache_entry = runtime_dir / "cache" / "ingest" / "rbi-handbook"
    cache_entry.mkdir(parents=True)
    (cache_entry / "2024.xlsx").write_bytes(b"stale-bytes")
    _age(cache_entry, 200)

    report = clean(days=90, force=False, dry_run=False, runtime_dir=runtime_dir)

    assert not cache_entry.exists()
    assert "cache/ingest/rbi-handbook" in report.removed


def test_runtime_dir_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    relocated = tmp_path / "scratch-runtime"

    # Unset -> default <repo_root>/.runtime.
    monkeypatch.delenv(RUNTIME_DIR_ENV, raising=False)
    assert resolve_runtime_dir(repo_root) == repo_root / ".runtime"

    # Set -> the override wins wholesale.
    monkeypatch.setenv(RUNTIME_DIR_ENV, str(relocated))
    assert resolve_runtime_dir(repo_root) == relocated

    # ... and clean sweeps the relocated base end-to-end.
    old_run = _seed_run(relocated, "20250101-eeee0005", age_days=200)
    report = clean(
        days=90,
        force=False,
        dry_run=False,
        runtime_dir=resolve_runtime_dir(repo_root),
    )
    assert not old_run.exists()
    assert "logs/20250101-eeee0005" in report.removed
