"""B1.4.7 writer-unit gate: iced_discom row-builder + write_csv round-trip.

Locks the contract for sub-row B1.4.7 of
``docs/archive/plans/20260604-b1.4-iced-repoint-subplan.md``: the iced_discom ingest
emits each opperf category (T&D loss, billing, collection) as a single
non-faceted variable and the RPO compliance series split into one
``variable_id`` per facet (solar / non-solar / total). Each emission
goes through the canonical ``yen_gov.canonical.csv_writer.write_csv``
against file class ``datasets/data/datapoints/geo/*.csv``, reduces
``YYYY-04`` fiscal-year periods to integer years, and stamps every
row with the deterministic ``source_id`` derived from each indicator's
citation triple.

Mirrors the shape of ``test_iced_socio_csv_repoint.py`` (B1.4.6,
PR #640). No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md
anti-pattern on walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.adapters.iced_discom.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE_RPO,
    _CSV_SOURCE_TITLE_TD_LOSS,
    _CSV_SOURCE_VINTAGE,
    _CSV_VARIABLE_PREFIX_RPO,
    _CSV_VARIABLE_PREFIX_TD_LOSS,
    _period_to_year_int,
    _slug_segment,
    build_csv_variables,
    emit_csv_variables,
)


def _parsed_td_loss_rows() -> list[dict[str, object]]:
    # Mirrors `parse_opperf_states` per-category output: no facet column.
    return [
        {"entity_id": "IN-S22", "time": "2020-04", "value": 18.5},
        {"entity_id": "IN-S27", "time": "2020-04", "value": 14.2},
    ]


def _parsed_rpo_rows() -> list[dict[str, object]]:
    # Mirrors `parse_rpo`: entity_id state, fiscal-year period, faceted.
    return [
        {"entity_id": "IN-S22", "time": "2020-04", "value": 95.0, "facet": "solar"},
        {"entity_id": "IN-S22", "time": "2020-04", "value": 88.0, "facet": "non-solar"},
        {"entity_id": "IN-S22", "time": "2020-04", "value": 91.0, "facet": "total"},
        {"entity_id": "IN-S27", "time": "2020-04", "value": 102.0, "facet": "solar"},
    ]


def test_build_csv_variables_facet_splits_per_axis():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_RPO, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_rpo_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_RPO,
    )
    assert set(by_variable.keys()) == {
        "rpo-compliance-pct-solar",
        "rpo-compliance-pct-non-solar",
        "rpo-compliance-pct-total",
    }
    solar = by_variable["rpo-compliance-pct-solar"]
    assert len(solar) == 2
    for row in solar:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id
        assert tuple(sorted(row.keys())) == (
            "entity_id", "source_id", "time", "value",
        )


def test_build_csv_variables_unfaceted_collapses_to_single_variable():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_TD_LOSS, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_td_loss_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_TD_LOSS,
    )
    assert set(by_variable.keys()) == {"transmission-distribution-loss-pct"}
    rows = by_variable["transmission-distribution-loss-pct"]
    assert [(r["entity_id"], r["time"]) for r in rows] == [
        ("IN-S22", 2020),
        ("IN-S27", 2020),
    ]


def test_period_to_year_int_reduces_fiscal_year_to_start_year():
    assert _period_to_year_int("2020-04") == 2020
    assert _period_to_year_int("2018") == 2018


def test_slug_segment_is_kebab_and_ban_safe():
    assert _slug_segment("Solar") == "solar"
    assert _slug_segment("Non-Solar") == "non-solar"
    assert _slug_segment("Total Compliance") == "total-compliance"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_emit_csv_variables_writes_one_file_per_facet(tmp_path: Path):
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_RPO, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_rpo_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_RPO,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 3
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    solar_path = out_dir / "rpo-compliance-pct-solar.csv"
    non_solar_path = out_dir / "rpo-compliance-pct-non-solar.csv"
    total_path = out_dir / "rpo-compliance-pct-total.csv"
    assert solar_path.exists()
    assert non_solar_path.exists()
    assert total_path.exists()

    text = solar_path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with solar_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed = list(reader)
    assert [(r["entity_id"], r["time"]) for r in parsed] == [
        ("IN-S22", "2020"),
        ("IN-S27", "2020"),
    ]
    assert parsed[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
