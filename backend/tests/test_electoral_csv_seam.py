"""Unit tests for the electoral observation + source CSV write seam (Row 8).

Covers the shared helper that the three ECI election adapters now use instead
of the retired envelope/parquet writer:

- state-slug partition derivation (AC / PC / rollup / candidate ids -> the
  same per-state file; unknown codes fail loud);
- 1:1 observation-row -> 9-column CSV projection (drops observation_id);
- ``write_electoral_results`` UPSERT (per-state partition, last-wins dedupe on
  the logical key, and - critically for election data - no-drop of
  pre-existing rows);
- ``upsert_source_csv`` additive append (idempotent, url mapping, order
  preserved, fail-loud on a missing ledger).
"""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from yen_gov.canonical.adapters.eci.electoral_csv import (
    observation_row_to_csv,
    state_slug_for_entity_id,
    upsert_source_csv,
    write_electoral_results,
)
from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug

_ELECTORAL_COLS = {
    "entity_id",
    "year",
    "period_label",
    "period_seq",
    "indicator_id",
    "value_numeric",
    "value_text",
    "source_id",
    "derivation",
}


def _obs(
    entity_id: str,
    indicator_id: str,
    *,
    year: int = 2021,
    period_label: str = "AcGenApr2021",
    period_seq: int = 4,
    value_numeric: float | None = None,
    value_text: str | None = None,
    source_id: str = "src-aaaaaaaaaaaa",
    derivation: str | None = "raw",
) -> SimpleNamespace:
    return SimpleNamespace(
        entity_id=entity_id,
        year=year,
        period_label=period_label,
        period_seq=period_seq,
        indicator_id=indicator_id,
        value_numeric=value_numeric,
        value_text=value_text,
        source_id=source_id,
        derivation=derivation,
    )


def _src(
    source_id: str,
    *,
    producer: str = "Election Commission of India",
    title: str = "T",
    vintage: str = "2021",
    url_main: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        source_id=source_id,
        producer=producer,
        title=title,
        vintage=vintage,
        url_main=url_main,
    )


def _seed_source_csv(datasets_root: Path, rows: tuple = ()) -> Path:
    path = datasets_root / "data" / "entities" / "source.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["source_id", "producer", "title", "vintage", "url"])
        for row in rows:
            writer.writerow(row)
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --- state-slug partition derivation ---------------------------------------


def test_state_slug_ac_pc_rollup_route_to_same_state() -> None:
    s22 = eci_to_lgd_slug("S22")
    assert state_slug_for_entity_id("IN-S22-AC-2008-1") == s22
    assert state_slug_for_entity_id("IN-PC-2008-S22-5") == s22
    assert state_slug_for_entity_id("IN-S22-AcGenApr2021") == s22
    assert state_slug_for_entity_id("IN-S22-AcGenApr2021-PARTY-DMK") == s22


def test_state_slug_candidate_ids_route_by_state() -> None:
    s22 = eci_to_lgd_slug("S22")
    assert state_slug_for_entity_id("IN-S22-AC-2008-1-AcGenApr2021-C01") == s22
    assert state_slug_for_entity_id("IN-PC-2008-S22-1-LsGenJun2024-C01") == s22


def test_state_slug_unknown_code_fails_loud() -> None:
    with pytest.raises(ValueError):
        state_slug_for_entity_id("IN-Z99-AC-2008-1")
    with pytest.raises(ValueError):
        state_slug_for_entity_id("garbage")


# --- observation_row_to_csv -------------------------------------------------


def test_observation_row_to_csv_is_nine_cols_without_observation_id() -> None:
    d = observation_row_to_csv(
        _obs("IN-S22-AC-2008-1", "ac-votes-polled", value_numeric=123.0)
    )
    assert set(d) == _ELECTORAL_COLS
    assert "observation_id" not in d
    assert d["value_numeric"] == 123.0
    assert d["value_text"] is None


# --- write_electoral_results: partition + tuple parity ----------------------


def test_write_electoral_results_partitions_and_preserves_tuples(tmp_path: Path) -> None:
    datasets_root = tmp_path / "datasets"
    rows = [
        _obs("IN-S22-AC-2008-1", "ac-votes-polled", value_numeric=100.0),
        _obs("IN-S22-AC-2008-1", "ac-winner-party-id", value_text="parties.IN.DMK", derivation="join"),
        _obs("IN-S05-AC-2008-1", "ac-votes-polled", value_numeric=50.0),
    ]
    paths = write_electoral_results(datasets_root=datasets_root, observation_rows=rows)

    assert set(paths) == {eci_to_lgd_slug("S22"), eci_to_lgd_slug("S05")}
    before = {(r.entity_id, r.year, r.indicator_id) for r in rows}
    after: set[tuple[str, int, str]] = set()
    for path in paths.values():
        for d in _read_csv(path):
            after.add((d["entity_id"], int(d["year"]), d["indicator_id"]))
    assert after == before


def test_write_electoral_results_upsert_preserves_foreign_rows(tmp_path: Path) -> None:
    """A drop of a pre-existing election row is a HARD FAIL: writing one event
    must not erase another event's rows already in the same state file."""
    datasets_root = tmp_path / "datasets"
    slug = eci_to_lgd_slug("S22")
    write_electoral_results(
        datasets_root=datasets_root,
        observation_rows=[
            _obs(
                "IN-S22-AC-2008-1", "ac-votes-polled",
                year=2016, period_label="AcGenMay2016", period_seq=5, value_numeric=10.0,
            )
        ],
    )
    write_electoral_results(
        datasets_root=datasets_root,
        observation_rows=[
            _obs("IN-S22-AC-2008-1", "ac-votes-polled", value_numeric=20.0),
        ],
    )
    path = datasets_root / "data" / "datapoints" / "electoral" / f"{slug}_election_results.csv"
    keys = {(d["period_label"], d["indicator_id"]) for d in _read_csv(path)}
    assert ("AcGenMay2016", "ac-votes-polled") in keys
    assert ("AcGenApr2021", "ac-votes-polled") in keys


def test_write_electoral_results_dedupes_logical_key_last_wins(tmp_path: Path) -> None:
    datasets_root = tmp_path / "datasets"
    paths = write_electoral_results(
        datasets_root=datasets_root,
        observation_rows=[
            _obs("IN-S22-AC-2008-1", "ac-votes-polled", value_numeric=1.0),
            _obs("IN-S22-AC-2008-1", "ac-votes-polled", value_numeric=2.0),
        ],
    )
    (path,) = paths.values()
    data = _read_csv(path)
    assert len(data) == 1
    assert float(data[0]["value_numeric"]) == 2.0


def test_write_electoral_results_empty_is_noop(tmp_path: Path) -> None:
    datasets_root = tmp_path / "datasets"
    assert write_electoral_results(datasets_root=datasets_root, observation_rows=[]) == {}


# --- upsert_source_csv ------------------------------------------------------


def test_upsert_source_csv_is_additive_and_maps_url(tmp_path: Path) -> None:
    datasets_root = tmp_path / "datasets"
    existing_id = "src-000000000000"
    _seed_source_csv(datasets_root, rows=((existing_id, "Existing", "Existing title", "2020", ""),))

    upsert_source_csv(
        datasets_root=datasets_root,
        source_rows=[
            _src("src-111111111111", url_main="https://eci.gov.in/x"),
            _src(existing_id),  # already present -> not duplicated
        ],
    )

    rows = _read_csv(datasets_root / "data" / "entities" / "source.csv")
    ids = [r["source_id"] for r in rows]
    assert ids.count(existing_id) == 1
    assert "src-111111111111" in ids
    assert ids[0] == existing_id  # existing row order preserved (appended at end)
    new_row = next(r for r in rows if r["source_id"] == "src-111111111111")
    assert new_row["url"] == "https://eci.gov.in/x"
    assert new_row["producer"] == "Election Commission of India"


def test_upsert_source_csv_missing_ledger_fails_loud(tmp_path: Path) -> None:
    datasets_root = tmp_path / "datasets"
    with pytest.raises(FileNotFoundError):
        upsert_source_csv(datasets_root=datasets_root, source_rows=[_src("src-222222222222")])
