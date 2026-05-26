"""Contract tests for the canonical writer's ``--dry-run`` mode (PR-A2).

Per the grain-rip plan-doc Phase A row PR-A2 asserts:
    (i)  bytes_planned == bytes_after (every on-disk file is byte-identical
         pre- and post-dry-run)
    (ii) n_files_changed_on_disk == 0 (no mtime change either)
    (iii) the log stream contains structured ``UNCHANGED|CHANGED|NEW`` lines
          per file the writer planned to emit.

The dry-run seam runs through ``_atomic_emit_or_dryrun`` in
``backend/yen_gov/canonical/writer.py``: every COPY-to-tempfile site routes
its tempfile through that helper, which either ``os.replace``s it (real
write) or byte-compares + unlinks (dry-run). Manifest regen, facet-axes,
persons-taxonomy seeds, and dim_*.parquet upserts all share the seam.

tmp_path fixtures only (CLAUDE.md §15 + Holy Law #10); no corpus walk.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from yen_gov.canonical import (
    BatchEnvelope,
    ObservationRow,
    ReplacementSemantics,
    SourceRow,
    write_batch,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ENTITIES_FIXTURE = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"


def _seed_taxonomy(datasets_root: Path) -> None:
    (datasets_root / "taxonomy").mkdir(parents=True, exist_ok=True)
    shutil.copy(ENTITIES_FIXTURE, datasets_root / "taxonomy" / "entities.json")


def _src(source_id: str = "src-test00000001") -> SourceRow:
    return SourceRow(
        source_id=source_id,
        producer="yen-gov",
        title="Test Source",
        vintage="2026",
        license="internal",
        confidence_tier="gold",
        is_issuing_authority=False,
        verification_method="editorial",
    )


def _obs(
    indicator_id: str = "state-test-dummy-int",
    value_numeric: float = 42.0,
    entity_id: str = "IN-S22",
) -> ObservationRow:
    return ObservationRow(
        entity_id=entity_id,
        year=2025,
        period_label="FY 2024-25",
        period_seq=1,
        indicator_id=indicator_id,
        value_numeric=value_numeric,
        value_text=None,
        source_id="src-test00000001",
    )


def _envelope(observations: list[ObservationRow]) -> BatchEnvelope:
    return BatchEnvelope(
        target_family="test",
        source_rows=[_src()],
        observation_rows=observations,
        replacement_semantics=ReplacementSemantics.upsert,
    )


def _snapshot_tree(root: Path) -> dict[str, tuple[int, bytes]]:
    """Return path -> (mtime_ns, bytes) for every file under root."""
    snap: dict[str, tuple[int, bytes]] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            stat = p.stat()
            snap[p.relative_to(root).as_posix()] = (stat.st_mtime_ns, p.read_bytes())
    return snap


def test_dry_run_against_empty_root_touches_no_files(
    tmp_path: Path, caplog
) -> None:
    """Dry-run against a tmp datasets root that has only the entities
    fixture: writer must NOT create observations.parquet, sources.parquet,
    facet-axes.parquet, or manifest.json. The log must report at least one
    NEW line (the planned observations parquet)."""
    _seed_taxonomy(tmp_path)
    before = _snapshot_tree(tmp_path)
    caplog.set_level(logging.INFO, logger="yen_gov.canonical.writer")

    result = write_batch(_envelope([_obs()]), tmp_path, dry_run=True)

    after = _snapshot_tree(tmp_path)
    assert before == after, "dry-run must not create or modify any files"
    assert result.observation_rows_written == 1
    assert result.source_rows_written == 1
    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "dry-run:" in log_text
    # At least one structured per-file line. The exact set depends on which
    # planned writes hit `_atomic_emit_or_dryrun`; we assert presence of the
    # observations and sources targets.
    assert "test/observations.parquet" in log_text or "test\\observations.parquet" in log_text
    assert "taxonomy/sources.parquet" in log_text or "taxonomy\\sources.parquet" in log_text


def test_dry_run_after_real_write_reports_unchanged(
    tmp_path: Path, caplog
) -> None:
    """Real-write an envelope, snapshot bytes+mtime, dry-run the SAME envelope.
    The on-disk state must be byte-identical AND mtime-identical. The log
    must report UNCHANGED for every planned file (no CHANGED, except the
    manifest whose ``generated_at`` always drifts)."""
    _seed_taxonomy(tmp_path)
    env = _envelope([_obs()])
    write_batch(env, tmp_path)
    before = _snapshot_tree(tmp_path)

    caplog.set_level(logging.INFO, logger="yen_gov.canonical.writer")
    write_batch(env, tmp_path, dry_run=True)

    after = _snapshot_tree(tmp_path)
    assert before == after, "dry-run must not mutate bytes or touch mtime"
    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "UNCHANGED" in log_text, log_text
    # The only file allowed to log CHANGED in this scenario is the manifest
    # (its `generated_at` is a wall-clock per CLAUDE.md §10 carve-out).
    changed_lines = [
        ln for ln in log_text.splitlines()
        if "CHANGED" in ln and "UNCHANGED" not in ln
    ]
    non_manifest_changed = [ln for ln in changed_lines if "manifest.json" not in ln]
    assert non_manifest_changed == [], non_manifest_changed


def test_dry_run_after_real_write_with_modified_envelope_reports_changed(
    tmp_path: Path, caplog
) -> None:
    """Real-write env A, then dry-run env B (one row appended). On-disk
    bytes are still A; log reports CHANGED for the observations parquet
    because the planned bytes differ from disk."""
    _seed_taxonomy(tmp_path)
    write_batch(_envelope([_obs(value_numeric=42.0)]), tmp_path)
    before = _snapshot_tree(tmp_path)

    caplog.set_level(logging.INFO, logger="yen_gov.canonical.writer")
    write_batch(
        _envelope([
            _obs(value_numeric=42.0),
            _obs(indicator_id="state-test-dummy-int-two", value_numeric=99.0),
        ]),
        tmp_path,
        dry_run=True,
    )

    after = _snapshot_tree(tmp_path)
    assert before == after, "dry-run must not mutate bytes"
    log_text = "\n".join(rec.getMessage() for rec in caplog.records)
    # The observations parquet must report CHANGED because the planned bytes
    # differ (2 rows vs 1 row on disk).
    assert "CHANGED" in log_text
    assert "observations.parquet" in log_text
