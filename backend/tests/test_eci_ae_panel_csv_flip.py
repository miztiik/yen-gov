"""Parity oracle for the eci_ae_panel flip to per-state electoral CSV (Row 8).

Proves that flipping the Assembly-panel adapter from the retired
envelope/parquet writer to ``write_electoral_results`` preserves EVERY
``(entity_id, year, indicator_id)`` observation tuple, per event - a dropped
election row is a hard fail. Also pins the additive source.csv upsert and the
UPSERT no-drop guarantee.

Reuses the proven panel + parties fixtures from ``test_eci_ae_panel_adapter``.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from test_eci_ae_panel_adapter import _write_csv, _write_parties

from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.adapters.eci_ae_panel import build_envelope, ingest_panel


def _seed_source_csv(datasets_root: Path) -> Path:
    path = datasets_root / "data" / "entities" / "source.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("source_id,producer,title,vintage,url\n", encoding="utf-8")
    return path


def _read_electoral_dir(datasets_root: Path) -> list[dict[str, str]]:
    electoral = datasets_root / "data" / "datapoints" / "electoral"
    out: list[dict[str, str]] = []
    for path in sorted(electoral.glob("*_election_results.csv")):
        with path.open(encoding="utf-8", newline="") as fh:
            out.extend(csv.DictReader(fh))
    return out


def _tuples_by_event(rows, *, get) -> dict[str, set[tuple[str, int, str]]]:
    grouped: dict[str, set[tuple[str, int, str]]] = defaultdict(set)
    for row in rows:
        entity_id, year, period_label, indicator_id = get(row)
        grouped[period_label].add((entity_id, year, indicator_id))
    return grouped


def test_ingest_panel_preserves_per_event_tuples(tmp_path: Path) -> None:
    datasets_root = tmp_path / "datasets"
    _write_parties(datasets_root)
    _seed_source_csv(datasets_root)
    csv_path = tmp_path / "panel.csv"
    _write_csv(csv_path)

    # BEFORE: the observation tuples the adapter builds, per event.
    batch, _events, _report = build_envelope(
        datasets_root=datasets_root,
        csv_path=csv_path,
        state_code="S22",
        allow_unknown_parties=True,
    )
    before = _tuples_by_event(
        batch.observation_rows,
        get=lambda r: (r.entity_id, r.year, r.period_label, r.indicator_id),
    )

    # FLIP: run the full ingest (build + write per-state CSV + source upsert).
    result = ingest_panel(
        repo_root=tmp_path,
        csv_path=csv_path,
        state_code="S22",
        allow_unknown_parties=True,
    )
    assert not result.skipped
    assert result.observation_rows_written == len(batch.observation_rows)
    # S22 -> one per-state file.
    assert result.csv_paths == (
        datasets_root / "data" / "datapoints" / "electoral"
        / f"{eci_to_lgd_slug('S22')}_election_results.csv",
    )

    # AFTER: the observation tuples actually on disk, per event.
    after = _tuples_by_event(
        _read_electoral_dir(datasets_root),
        get=lambda r: (r["entity_id"], int(r["year"]), r["period_label"], r["indicator_id"]),
    )

    assert set(after) == set(before), "event set diverged"
    for event_id, before_tuples in before.items():
        assert after[event_id] == before_tuples, f"tuple parity broke for event {event_id}"


def test_ingest_panel_source_upsert_is_additive(tmp_path: Path) -> None:
    datasets_root = tmp_path / "datasets"
    _write_parties(datasets_root)
    source_csv = _seed_source_csv(datasets_root)
    sentinel = "src-deadbeef0000"
    with source_csv.open("a", encoding="utf-8", newline="") as fh:
        fh.write(f"{sentinel},Seed,Seed title,2000,\n")
    csv_path = tmp_path / "panel.csv"
    _write_csv(csv_path)

    batch, _events, _report = build_envelope(
        datasets_root=datasets_root,
        csv_path=csv_path,
        state_code="S22",
        allow_unknown_parties=True,
    )
    expected_source_ids = {s.source_id for s in batch.source_rows}
    assert len(expected_source_ids) == 2  # 1971 + 2021 reports

    ingest_panel(
        repo_root=tmp_path,
        csv_path=csv_path,
        state_code="S22",
        allow_unknown_parties=True,
    )

    with source_csv.open(encoding="utf-8", newline="") as fh:
        ids = {r["source_id"] for r in csv.DictReader(fh)}
    assert sentinel in ids, "pre-existing citation row was dropped"
    assert expected_source_ids <= ids, "adapter citation rows were not appended"


def test_ingest_panel_upsert_does_not_drop_foreign_state_rows(tmp_path: Path) -> None:
    datasets_root = tmp_path / "datasets"
    _write_parties(datasets_root)
    _seed_source_csv(datasets_root)
    csv_path = tmp_path / "panel.csv"
    _write_csv(csv_path)

    # Pre-seed the S22 file with a foreign row from an unrelated event.
    electoral = datasets_root / "data" / "datapoints" / "electoral"
    electoral.mkdir(parents=True, exist_ok=True)
    state_file = electoral / f"{eci_to_lgd_slug('S22')}_election_results.csv"
    state_file.write_text(
        "entity_id,year,period_label,period_seq,indicator_id,value_numeric,value_text,source_id,derivation\n"
        "IN-S22-AC-2008-99,1962,AcGenFeb1962,2,ac-votes-polled,7.0,,src-feedfeedfeed,sum\n",
        encoding="utf-8",
    )

    ingest_panel(
        repo_root=tmp_path,
        csv_path=csv_path,
        state_code="S22",
        allow_unknown_parties=True,
    )

    with state_file.open(encoding="utf-8", newline="") as fh:
        keys = {(r["entity_id"], r["period_label"], r["indicator_id"]) for r in csv.DictReader(fh)}
    assert ("IN-S22-AC-2008-99", "AcGenFeb1962", "ac-votes-polled") in keys
