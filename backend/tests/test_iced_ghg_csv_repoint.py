"""B1.4.1 writer-unit gate: iced_ghg row-builder + write_csv round-trip.

Locks the contract for sub-row B1.4.1 of
``docs/archive/plans/20260604-b1.4-iced-repoint-subplan.md``: the iced_ghg ingest splits
its facet-keyed parser output into one ``variable_id`` per
(sector, sub-sector) pair, emits each via the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, and stamps every row with the
deterministic ``source_id`` derived from the citation triple.

No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md anti-pattern on
walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.adapters.iced_ghg.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE,
    _CSV_SOURCE_VINTAGE,
    _slug_segment,
    build_csv_variables,
    emit_csv_variables,
)


def _parsed_rows() -> list[dict[str, object]]:
    # Mirrors the shape of `parse_ghg_subsector` output.
    return [
        {"entity_id": "IN", "time": "2010", "value": 100.5,
         "facet": "Energy|Transport"},
        {"entity_id": "IN", "time": "2020", "value": 200.0,
         "facet": "Energy|Transport"},
        {"entity_id": "IN", "time": "2020", "value": 60.0,
         "facet": "Agriculture|Rice Cultivation"},
    ]


def test_build_csv_variables_splits_per_facet_with_canonical_columns():
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(_parsed_rows(), source_id=source_id)

    assert set(by_variable.keys()) == {
        "ghg-emissions-ggco2e-energy-transport",
        "ghg-emissions-ggco2e-agriculture-rice-cultivation",
    }
    transport = by_variable["ghg-emissions-ggco2e-energy-transport"]
    assert len(transport) == 2
    assert {tuple(sorted(r.keys())) for r in transport} == {
        ("entity_id", "source_id", "time", "value")
    }
    for row in transport:
        assert row["entity_id"] == "IN"
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id


def test_slug_segment_is_kebab_and_ban_safe():
    # Plan section 21.6 / 21.12 ban `__`; ADR-0044 bans grain prefixes.
    assert _slug_segment("Energy") == "energy"
    assert _slug_segment("Rice Cultivation") == "rice-cultivation"
    assert _slug_segment("Land-Use & Forestry") == "land-use-forestry"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_emit_csv_variables_writes_one_file_per_variable(tmp_path: Path):
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(_parsed_rows(), source_id=source_id)
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 2
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    assert (
        out_dir / "ghg-emissions-ggco2e-energy-transport.csv"
    ).exists()

    transport_path = out_dir / "ghg-emissions-ggco2e-energy-transport.csv"
    text = transport_path.read_text(encoding="utf-8")
    # Header order matches the file class's declared column order.
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    # Trailing newline + LF line endings (writer contract).
    assert text.endswith("\n")
    assert "\r" not in text

    with transport_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed = list(reader)
    # Deterministic sort on PK (entity_id, time).
    assert [r["time"] for r in parsed] == ["2010", "2020"]
    assert parsed[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    # Trip-wire: if the file class string drifts, this guard catches it
    # before the per-family PR ships against a stale glob.
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
