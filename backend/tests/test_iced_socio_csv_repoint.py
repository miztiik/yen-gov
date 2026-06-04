"""B1.4.6 writer-unit gate: iced_socio row-builder + write_csv round-trip.

Locks the contract for sub-row B1.4.6 of
``docs/archive/plans/20260604-b1.4-iced-repoint-subplan.md``: the iced_socio ingest
emits per-capita consumption as a single non-faceted variable and the
economy-wide GHG series split into one ``variable_id`` per sector facet.
Each emission goes through the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, reduces ``YYYY``/``YYYY-MM``
periods to integer years, and stamps every row with the deterministic
``source_id`` derived from each indicator's citation triple.

Mirrors the shape of ``test_iced_power_csv_repoint.py`` (B1.4.5,
PR #639). No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md
anti-pattern on walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.sources.iced_socio.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE_GHG,
    _CSV_SOURCE_TITLE_PCC,
    _CSV_SOURCE_VINTAGE,
    _CSV_VARIABLE_PREFIX_GHG,
    _CSV_VARIABLE_PREFIX_PCC,
    _period_to_year_int,
    _slug_segment,
    build_csv_variables,
    emit_csv_variables,
)


def _parsed_pcc_rows() -> list[dict[str, object]]:
    # Mirrors `parse_per_capita_consumption()[0]`: no facet column.
    return [
        {"entity_id": "IN-S22", "time": "2017-04", "value": 95000.0},
        {"entity_id": "IN-S27", "time": "2017-04", "value": 120000.0},
    ]


def _parsed_ghg_rows() -> list[dict[str, object]]:
    # Mirrors `parse_ghg_economy_wide`: entity_id=IN, facet=sector, time YYYY.
    return [
        {"entity_id": "IN", "time": "2016", "value": 2200000.0, "facet": "Energy"},
        {"entity_id": "IN", "time": "2016", "value": 400000.0, "facet": "Agriculture"},
        {"entity_id": "IN", "time": "2018", "value": 2350000.0, "facet": "Energy"},
    ]


def test_build_csv_variables_facet_splits_per_sector():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_GHG, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_ghg_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_GHG,
    )
    assert set(by_variable.keys()) == {
        "ghg-emissions-by-sector-ggco2e-energy",
        "ghg-emissions-by-sector-ggco2e-agriculture",
    }
    energy = by_variable["ghg-emissions-by-sector-ggco2e-energy"]
    assert len(energy) == 2
    for row in energy:
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id
        assert tuple(sorted(row.keys())) == (
            "entity_id", "source_id", "time", "value",
        )


def test_build_csv_variables_unfaceted_collapses_to_single_variable():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_PCC, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_pcc_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_PCC,
    )
    assert set(by_variable.keys()) == {"per-capita-consumption-inr"}
    rows = by_variable["per-capita-consumption-inr"]
    assert [(r["entity_id"], r["time"]) for r in rows] == [
        ("IN-S22", 2017),
        ("IN-S27", 2017),
    ]


def test_period_to_year_int_accepts_year_and_fiscal_year():
    assert _period_to_year_int("2024-04") == 2024
    assert _period_to_year_int("2018") == 2018


def test_slug_segment_is_kebab_and_ban_safe():
    assert _slug_segment("Energy") == "energy"
    assert _slug_segment("Land Use & LULUCF") == "land-use-lulucf"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_emit_csv_variables_writes_one_file_per_facet(tmp_path: Path):
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE_GHG, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(
        _parsed_ghg_rows(),
        source_id=source_id,
        variable_prefix=_CSV_VARIABLE_PREFIX_GHG,
    )
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 2
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    energy_path = out_dir / "ghg-emissions-by-sector-ggco2e-energy.csv"
    agri_path = out_dir / "ghg-emissions-by-sector-ggco2e-agriculture.csv"
    assert energy_path.exists()
    assert agri_path.exists()

    text = energy_path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with energy_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed = list(reader)
    assert [(r["entity_id"], r["time"]) for r in parsed] == [
        ("IN", "2016"),
        ("IN", "2018"),
    ]
    assert parsed[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
