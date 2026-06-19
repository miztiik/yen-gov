"""B1.5.1 writer-unit gate: rbi_appendix_national row-builder + write_csv.

Locks the contract for sub-row B1.5.1 of
``docs/archive/plans/20260604-b1.5-rbi-repoint-subplan.md``: each of the four
SHIPPED_SPECS appendix indicators maps 1:1 to a kebab-case
``variable_id`` (no faceting on this family), is emitted via the
canonical ``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, and stamps every row with the
deterministic ``source_id`` derived from one shared citation triple
(producer / title / vintage = single Appendix Table 2 publication).

No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md anti-pattern on
walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.adapters.rbi_appendix_national.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE,
    _CSV_SOURCE_VINTAGE,
    _INDICATOR_TO_VARIABLE_ID,
    _fy_start_year,
    _slug_segment,
    build_csv_variables,
    emit_csv_variables,
)
from yen_gov.canonical.adapters.rbi_appendix_national.parsers import (
    AppendixSpec,
    ParsedIndicator,
    ParsedRow,
)


def _parsed_indicator() -> tuple[AppendixSpec, ParsedIndicator]:
    spec = AppendixSpec(
        indicator_id="fiscal/centre_transfers_to_states_net",
        item_label_match="net transfer of resources",
    )
    parsed = ParsedIndicator(
        indicator_id=spec.indicator_id,
        rows=[
            ParsedRow(entity_id="IN", time="2007-04", value=1234.5),
            ParsedRow(entity_id="IN", time="2008-04", value=2345.6),
            # Null rows are dropped (real workbooks have N.A. cells).
            ParsedRow(entity_id="IN", time="2009-04", value=None),
        ],
        sheet_count=1,
        period_count=3,
    )
    return spec, parsed


def test_build_csv_variables_maps_one_variable_per_spec_with_canonical_columns():
    spec, parsed = _parsed_indicator()
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(spec, parsed, source_id=source_id)

    assert set(by_variable.keys()) == {"centre-transfers-to-states-net-inr-crore"}
    rows = by_variable["centre-transfers-to-states-net-inr-crore"]
    # Null-valued parser row is dropped.
    assert len(rows) == 2
    assert {tuple(sorted(r.keys())) for r in rows} == {
        ("entity_id", "source_id", "time", "value")
    }
    for row in rows:
        assert row["entity_id"] == "IN"
        assert isinstance(row["time"], int)
        assert row["source_id"] == source_id


def test_fy_start_year_lifts_integer_year():
    assert _fy_start_year("2007-04") == 2007
    assert _fy_start_year("2025-04") == 2025


def test_slug_segment_is_kebab_and_ban_safe():
    # Plan section 21.6 / 21.12 ban `__`; ADR-0044 bans grain prefixes.
    assert _slug_segment("Centre Transfers") == "centre-transfers"
    assert _slug_segment("INR (crore)") == "inr-crore"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_indicator_variable_id_map_covers_all_shipped_specs():
    # Trip-wire: if a new spec lands without a variable_id, the
    # ingest will KeyError; this guard makes the gap visible at test
    # time instead of at first ingest run.
    from yen_gov.canonical.adapters.rbi_appendix_national.parsers import SHIPPED_SPECS

    assert {s.indicator_id for s in SHIPPED_SPECS} == set(
        _INDICATOR_TO_VARIABLE_ID.keys()
    )
    for vid in _INDICATOR_TO_VARIABLE_ID.values():
        assert "__" not in vid
        assert not vid.startswith(("state-", "district-", "national-"))


def test_emit_csv_variables_writes_one_file_per_variable(tmp_path: Path):
    spec, parsed = _parsed_indicator()
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(spec, parsed, source_id=source_id)
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 1
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    target = out_dir / "centre-transfers-to-states-net-inr-crore.csv"
    assert target.exists()

    text = target.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with target.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        parsed_rows = list(reader)
    # Deterministic sort on PK (entity_id, time).
    assert [r["time"] for r in parsed_rows] == ["2007", "2008"]
    assert parsed_rows[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    # Trip-wire: if the file class string drifts, this guard catches
    # it before the family PR ships against a stale glob.
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
