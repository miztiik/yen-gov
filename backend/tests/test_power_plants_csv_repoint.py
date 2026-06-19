"""B1.6.3 writer-unit gate: india_geodata/power_plants row-builder + write_csv.

Locks the contract for sub-row B1.6.3 of
``docs/archive/plans/20260604-b1.6-misc-repoint-subplan.md``: point features aggregate
to one national-grain row per fuel facet, each emitted via the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, and stamps every row with the
deterministic ``source_id`` derived from the per-source citation triple
(producer / title / vintage per ADR-0042).

No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md anti-pattern on
walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.adapters.india_geodata.power_plants import (
    _CSV_FILE_CLASS,
    _CSV_NATIONAL_ENTITY_ID,
    _CSV_OUT_REL_DIR,
    _CSV_PRODUCER,
    _CSV_SNAPSHOT_TIME,
    _CSV_TITLE,
    _CSV_VINTAGE,
    _FUEL_FACET,
    build_csv_variables,
    emit_csv_variables,
)


def _geojson() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {"properties": {"type": "coal_power_plant", "inst_cap": "1040"}},
            {"properties": {"type": "coal_power_plant", "inst_cap": "500"}},
            {"properties": {"type": "hydro_power_plant", "inst_cap": "250.5"}},
            {"properties": {"type": "natural_gas_power_plant", "inst_cap": "300"}},
            # Skipped: unknown fuel token.
            {"properties": {"type": "fusion_power_plant", "inst_cap": "9000"}},
            # Skipped: missing / blank capacity.
            {"properties": {"type": "coal_power_plant", "inst_cap": None}},
            {"properties": {"type": "coal_power_plant", "inst_cap": ""}},
        ],
    }


def _source_id() -> str:
    return derive_source_id(_CSV_PRODUCER, _CSV_TITLE, _CSV_VINTAGE)


def test_fuel_facet_map_is_kebab_case_and_unprefixed():
    for facet in _FUEL_FACET.values():
        assert "__" not in facet
        assert "_" not in facet
        vid = f"installed-capacity-mw-{facet}"
        assert not vid.startswith(("state-", "district-", "national-"))


def test_build_csv_variables_aggregates_per_fuel_facet_at_national_grain():
    source_id = _source_id()
    by_variable = build_csv_variables(_geojson(), source_id=source_id)

    assert set(by_variable.keys()) == {
        "installed-capacity-mw-coal",
        "installed-capacity-mw-hydro",
        "installed-capacity-mw-natural-gas",
    }
    coal_rows = by_variable["installed-capacity-mw-coal"]
    assert len(coal_rows) == 1
    row = coal_rows[0]
    assert row["entity_id"] == _CSV_NATIONAL_ENTITY_ID == "IN"
    assert row["time"] == _CSV_SNAPSHOT_TIME == 2019
    assert row["value"] == 1540.0
    assert row["source_id"] == source_id
    assert by_variable["installed-capacity-mw-hydro"][0]["value"] == 250.5
    assert by_variable["installed-capacity-mw-natural-gas"][0]["value"] == 300.0


def test_build_csv_variables_skips_unknown_fuels_and_blank_capacity():
    by_variable = build_csv_variables(_geojson(), source_id=_source_id())
    # The fusion_power_plant feature carries 9000 MW; if it leaked into
    # any bucket the coal/hydro/gas totals would shift.
    assert "installed-capacity-mw-fusion" not in by_variable
    assert by_variable["installed-capacity-mw-coal"][0]["value"] == 1540.0


def test_emit_csv_variables_writes_one_file_per_variable(tmp_path: Path):
    by_variable = build_csv_variables(_geojson(), source_id=_source_id())
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 3
    target = tmp_path / _CSV_OUT_REL_DIR / "installed-capacity-mw-coal.csv"
    assert target.exists()

    text = target.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with target.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed_rows = list(reader)
    assert parsed_rows == [
        {
            "entity_id": "IN",
            "time": "2019",
            "value": "1540",
            "source_id": _source_id(),
        },
    ]


def test_file_class_matches_writer_glob():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
