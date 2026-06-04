"""Unit tests for the CSV writer (sub-plan B1.2).

Gate: writer-unit. Covers:

- happy-path emit (header + rows + LF + trailing newline + no BOM);
- file_class lookup against the shipped contract;
- declared-only columns; rejection of undeclared keys;
- dtype coercion (integer / number / boolean / string);
- nullability enforcement;
- deterministic sort by PK columns;
- ``__`` ban in filename;
- skip-write-if-equal optimisation preserves mtime.

No mocks (Holy Law #7). Uses ``tmp_path`` fixtures - never walks the real
on-disk corpus (CLAUDE.md anti-pattern).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from yen_gov.canonical.csv_writer import write_csv


_GEO_FC = "datasets/data/datapoints/geo/*.csv"
_VARIABLES_FC = "datasets/data/variables.csv"
_SOURCE_FC = "datasets/data/entities/source.csv"


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def test_writes_header_and_rows_with_lf_and_trailing_newline(tmp_path):
    path = tmp_path / "literacy-rate-pct-total.csv"
    rows = [
        {"entity_id": "IN-S22", "time": 2011, "value": 80.1, "source_id": "src-a"},
        {"entity_id": "IN-S01", "time": 2011, "value": 73.2, "source_id": "src-a"},
    ]
    write_csv(path=path, file_class=_GEO_FC, rows=rows)

    text = _read(path)
    assert "\r" not in text, "must emit LF only"
    assert not path.read_bytes().startswith(b"\xef\xbb\xbf"), "no BOM"
    assert text.endswith("\n"), "trailing newline required"
    lines = text.splitlines()
    assert lines[0] == "entity_id,time,value,source_id"
    # Sorted by (entity_id, time): IN-S01 then IN-S22.
    assert lines[1] == "IN-S01,2011,73.2,src-a"
    assert lines[2] == "IN-S22,2011,80.1,src-a"


def test_unknown_file_class_raises(tmp_path):
    with pytest.raises(KeyError, match="unknown file class"):
        write_csv(
            path=tmp_path / "foo.csv",
            file_class="datasets/data/does-not-exist.csv",
            rows=[],
        )


def test_double_underscore_in_filename_rejected(tmp_path):
    with pytest.raises(ValueError, match="__"):
        write_csv(
            path=tmp_path / "bad__name.csv",
            file_class=_GEO_FC,
            rows=[],
        )


def test_extra_undeclared_column_rejected(tmp_path):
    with pytest.raises(ValueError, match="undeclared"):
        write_csv(
            path=tmp_path / "x.csv",
            file_class=_GEO_FC,
            rows=[{
                "entity_id": "IN-S01",
                "time": 2011,
                "value": 1.0,
                "source_id": "s",
                "facet_sex": "F",  # facet support is B1.4+ follow-up
            }],
        )


def test_missing_non_nullable_pk_rejected(tmp_path):
    with pytest.raises(ValueError, match="non-nullable"):
        write_csv(
            path=tmp_path / "x.csv",
            file_class=_GEO_FC,
            rows=[{"time": 2011, "value": 1.0, "source_id": "s"}],
        )


def test_none_on_nullable_column_emits_empty_field(tmp_path):
    path = tmp_path / "x.csv"
    write_csv(
        path=path,
        file_class=_GEO_FC,
        rows=[{"entity_id": "IN-S01", "time": 2011, "value": None, "source_id": "s"}],
    )
    assert _read(path).splitlines()[1] == "IN-S01,2011,,s"


def test_integer_dtype_rejects_non_integer_float(tmp_path):
    with pytest.raises(ValueError, match="dtype='integer'"):
        write_csv(
            path=tmp_path / "x.csv",
            file_class=_GEO_FC,
            rows=[{"entity_id": "a", "time": 2011.5, "value": 1.0, "source_id": "s"}],
        )


def test_integer_dtype_coerces_integer_float_and_numeric_string(tmp_path):
    path = tmp_path / "x.csv"
    write_csv(
        path=path,
        file_class=_GEO_FC,
        rows=[
            {"entity_id": "a", "time": 2011.0, "value": 1.0, "source_id": "s"},
            {"entity_id": "b", "time": "2012", "value": 2.0, "source_id": "s"},
        ],
    )
    lines = _read(path).splitlines()
    assert lines[1] == "a,2011,1,s"
    assert lines[2] == "b,2012,2,s"


def test_number_dtype_preserves_fractional_and_strips_dot_zero(tmp_path):
    path = tmp_path / "x.csv"
    write_csv(
        path=path,
        file_class=_GEO_FC,
        rows=[
            {"entity_id": "a", "time": 2011, "value": 1.0, "source_id": "s"},
            {"entity_id": "b", "time": 2011, "value": 1.5, "source_id": "s"},
        ],
    )
    lines = _read(path).splitlines()
    assert lines[1] == "a,2011,1,s"
    assert lines[2] == "b,2011,1.5,s"


def test_deterministic_sort_by_composite_pk(tmp_path):
    path = tmp_path / "x.csv"
    rows = [
        {"entity_id": "B", "time": 2020, "value": 1.0, "source_id": "s"},
        {"entity_id": "A", "time": 2021, "value": 2.0, "source_id": "s"},
        {"entity_id": "A", "time": 2020, "value": 3.0, "source_id": "s"},
        {"entity_id": "B", "time": 2019, "value": 4.0, "source_id": "s"},
    ]
    write_csv(path=path, file_class=_GEO_FC, rows=rows)
    body = _read(path).splitlines()[1:]
    assert body == [
        "A,2020,3,s",
        "A,2021,2,s",
        "B,2019,4,s",
        "B,2020,1,s",
    ]


def test_skip_write_when_equal_preserves_mtime(tmp_path):
    path = tmp_path / "x.csv"
    rows = [{"entity_id": "a", "time": 2011, "value": 1.0, "source_id": "s"}]
    write_csv(path=path, file_class=_GEO_FC, rows=rows)
    mtime_before = path.stat().st_mtime_ns
    # Sleep one filesystem-resolution tick so any rewrite would visibly bump mtime.
    time.sleep(0.05)
    write_csv(path=path, file_class=_GEO_FC, rows=list(rows))
    assert path.stat().st_mtime_ns == mtime_before


def test_real_rewrite_updates_mtime(tmp_path):
    path = tmp_path / "x.csv"
    write_csv(
        path=path,
        file_class=_GEO_FC,
        rows=[{"entity_id": "a", "time": 2011, "value": 1.0, "source_id": "s"}],
    )
    mtime_before = path.stat().st_mtime_ns
    time.sleep(0.05)
    write_csv(
        path=path,
        file_class=_GEO_FC,
        rows=[{"entity_id": "a", "time": 2011, "value": 2.0, "source_id": "s"}],
    )
    assert path.stat().st_mtime_ns != mtime_before


def test_string_column_emits_value_verbatim(tmp_path):
    path = tmp_path / "source.csv"
    write_csv(
        path=path,
        file_class=_SOURCE_FC,
        rows=[
            {"source_id": "rbi-handbook-2024", "owner": "RBI", "title": "Handbook of Statistics",
             "vintage": "2024", "url": "https://example.org/h"},
            {"source_id": "ndlm-2023", "owner": None, "title": None, "vintage": None, "url": None},
        ],
    )
    lines = _read(path).splitlines()
    assert lines[0] == "source_id,owner,title,vintage,url"
    # Sorted by source_id.
    assert lines[1] == "ndlm-2023,,,,"
    assert lines[2] == "rbi-handbook-2024,RBI,Handbook of Statistics,2024,https://example.org/h"


def test_value_with_comma_is_quoted(tmp_path):
    path = tmp_path / "source.csv"
    write_csv(
        path=path,
        file_class=_SOURCE_FC,
        rows=[{"source_id": "x", "owner": None, "title": "A, B and C",
               "vintage": None, "url": None}],
    )
    assert _read(path).splitlines()[1] == 'x,,"A, B and C",,'


def test_empty_rows_emits_header_only(tmp_path):
    path = tmp_path / "variables.csv"
    write_csv(path=path, file_class=_VARIABLES_FC, rows=[])
    text = _read(path)
    assert text.splitlines() == [
        "indicator_id,name,concept_id,unit,derivation,topic,source_id,"
        "update_period_days,time_min,time_max,entity_kinds"
    ]
    assert text.endswith("\n")
