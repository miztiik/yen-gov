"""Unit tests for the merge-preserving source-scoped CSV upsert.

Gate: writer-unit. Covers ``upsert_source_scoped`` - the write discipline for a
MULTI-SOURCE single-value file (one canonical ``geo/<id>.csv`` fed by more than
one publisher, e.g. ``installed-capacity-allocated-mw.csv`` = RBI Handbook
history + ICED recent years). Re-emitting one source must replace ONLY that
source's rows and preserve every other source's rows verbatim, with a loud
failure on any cross-source PK collision or a row that claims the wrong source.

No mocks (Holy Law #7). ``tmp_path`` fixtures + the real shipped column
contract (loaded the same way the csv_writer tests do - the default
``load_columns()`` inside the writer); never walks the real corpus.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.csv_writer import upsert_source_scoped, write_csv

_GEO_FC = "datasets/data/datapoints/geo/*.csv"
_SRC_A = "src-aaaaaaaaaaaa"
_SRC_B = "src-bbbbbbbbbbbb"


def _row(entity_id: str, time: int, value: float, source_id: str) -> dict:
    return {
        "entity_id": entity_id,
        "time": time,
        "value": value,
        "source_id": source_id,
    }


def _data_lines(path: Path) -> list[str]:
    # CSV data lines (header dropped), in on-disk (PK-sorted) order.
    return path.read_text(encoding="utf-8").splitlines()[1:]


def _lines_for_source(path: Path, source_id: str) -> list[str]:
    return [ln for ln in _data_lines(path) if ln.endswith(f",{source_id}")]


def _parsed(path: Path) -> list[dict]:
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def _seed_two_source_file(path: Path) -> None:
    # Source A owns the FY2010 rows; source B owns the FY2020 rows. Written
    # through the canonical writer so the seed is already in canonical (sorted,
    # LF, formatted) shape - "byte-identical" preservation is then well-defined.
    # Non-integer values avoid the integer-valued-float "10.0" -> "10" emit
    # quirk so the asserted value strings are unambiguous.
    write_csv(
        path=path,
        file_class=_GEO_FC,
        rows=[
            _row("maharashtra", 2010, 100.5, _SRC_A),
            _row("tamil-nadu", 2010, 200.5, _SRC_A),
            _row("maharashtra", 2020, 110.5, _SRC_B),
            _row("tamil-nadu", 2020, 210.5, _SRC_B),
        ],
    )


def test_reemit_source_b_updates_only_b_rows_and_keeps_a_byte_identical(tmp_path):
    path = tmp_path / "installed-capacity-allocated-mw.csv"
    _seed_two_source_file(path)
    a_lines_before = _lines_for_source(path, _SRC_A)
    assert len(a_lines_before) == 2

    upsert_source_scoped(
        path=path,
        file_class=_GEO_FC,
        new_rows=[
            _row("maharashtra", 2020, 999.25, _SRC_B),  # value changed
            _row("tamil-nadu", 2020, 888.25, _SRC_B),
        ],
        source_id=_SRC_B,
    )

    # Source A rows preserved byte-identical.
    assert _lines_for_source(path, _SRC_A) == a_lines_before
    by_pk = {(r["entity_id"], r["time"]): r for r in _parsed(path)}
    # Source B values replaced.
    assert by_pk[("maharashtra", "2020")]["value"] == "999.25"
    assert by_pk[("tamil-nadu", "2020")]["value"] == "888.25"
    # Source A untouched (value + source attribution).
    assert by_pk[("maharashtra", "2010")]["value"] == "100.5"
    assert by_pk[("maharashtra", "2010")]["source_id"] == _SRC_A


def test_reemit_source_b_with_dropped_key_removes_that_row_a_untouched(tmp_path):
    path = tmp_path / "installed-capacity-allocated-mw.csv"
    _seed_two_source_file(path)
    a_lines_before = _lines_for_source(path, _SRC_A)

    # B re-emit drops tamil-nadu/2020 (only maharashtra/2020 supplied).
    upsert_source_scoped(
        path=path,
        file_class=_GEO_FC,
        new_rows=[_row("maharashtra", 2020, 110.5, _SRC_B)],
        source_id=_SRC_B,
    )

    pks = {(r["entity_id"], r["time"]) for r in _parsed(path)}
    assert ("tamil-nadu", "2020") not in pks       # dropped B row removed
    assert ("maharashtra", "2020") in pks          # surviving B row kept
    # A rows entirely untouched.
    assert _lines_for_source(path, _SRC_A) == a_lines_before
    assert ("maharashtra", "2010") in pks
    assert ("tamil-nadu", "2010") in pks


def test_cross_source_pk_collision_raises(tmp_path):
    path = tmp_path / "installed-capacity-allocated-mw.csv"
    _seed_two_source_file(path)

    # An incoming B row whose PK (maharashtra, 2010) is owned by source A:
    # sources must not silently overwrite each other.
    with pytest.raises(ValueError, match="cross-source PK collision"):
        upsert_source_scoped(
            path=path,
            file_class=_GEO_FC,
            new_rows=[_row("maharashtra", 2010, 1.5, _SRC_B)],
            source_id=_SRC_B,
        )


def test_new_row_with_wrong_source_id_raises(tmp_path):
    path = tmp_path / "installed-capacity-allocated-mw.csv"
    _seed_two_source_file(path)

    # A row that claims source A while the call names source B is a
    # programming error.
    with pytest.raises(ValueError, match="must belong to the named source"):
        upsert_source_scoped(
            path=path,
            file_class=_GEO_FC,
            new_rows=[_row("maharashtra", 2020, 5.5, _SRC_A)],
            source_id=_SRC_B,
        )


def test_upsert_into_nonexistent_path_creates_file_with_only_new_rows(tmp_path):
    path = tmp_path / "installed-capacity-allocated-mw.csv"
    assert not path.exists()

    out = upsert_source_scoped(
        path=path,
        file_class=_GEO_FC,
        new_rows=[
            _row("maharashtra", 2020, 110.5, _SRC_B),
            _row("tamil-nadu", 2020, 210.5, _SRC_B),
        ],
        source_id=_SRC_B,
    )

    assert out == path
    assert path.exists()
    rows = _parsed(path)
    assert {(r["entity_id"], r["time"]) for r in rows} == {
        ("maharashtra", "2020"),
        ("tamil-nadu", "2020"),
    }
    assert all(r["source_id"] == _SRC_B for r in rows)
    assert _data_lines(path) == [
        "maharashtra,2020,110.5,src-bbbbbbbbbbbb",
        "tamil-nadu,2020,210.5,src-bbbbbbbbbbbb",
    ]


def test_last_row_wins_on_repeated_pk_within_new_rows(tmp_path):
    path = tmp_path / "installed-capacity-allocated-mw.csv"

    out = upsert_source_scoped(
        path=path,
        file_class=_GEO_FC,
        new_rows=[
            _row("maharashtra", 2020, 1.5, _SRC_B),
            _row("maharashtra", 2020, 2.5, _SRC_B),  # same PK -> wins
        ],
        source_id=_SRC_B,
    )

    rows = _parsed(out)
    assert len(rows) == 1
    assert rows[0]["value"] == "2.5"
