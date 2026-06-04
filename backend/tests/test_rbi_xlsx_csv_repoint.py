"""B1.5.4 writer-unit gate: rbi_xlsx row-builder + write_csv.

Locks the contract for sub-row B1.5.4 of
``TODO/20260604-b1.5-rbi-repoint-subplan.md``: each rbi_xlsx
SHIPPED_SPECS spec maps to one or more kebab-case ``variable_id`` files
(split per facet because the writer does not yet support facet
columns), is emitted via the canonical
``yen_gov.canonical.csv_writer.write_csv`` against file class
``datasets/data/datapoints/geo/*.csv``, and stamps every row with the
deterministic ``source_id`` derived from one shared citation triple
(producer / title / vintage = single State Finances publication).

No mocks (Holy Law #7); uses ``tmp_path`` per CLAUDE.md anti-pattern on
walking the real corpus from pytest.
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.sources.rbi_xlsx.ingest import (
    _CSV_FILE_CLASS,
    _CSV_OUT_REL_DIR,
    _CSV_SOURCE_PRODUCER,
    _CSV_SOURCE_TITLE,
    _CSV_SOURCE_VINTAGE,
    _FACET_SUFFIX,
    _INDICATOR_TO_BASE_VARIABLE_ID,
    _fy_start_year,
    _slug_segment,
    _variable_id_for,
    build_csv_variables,
    emit_csv_variables,
)
from yen_gov.sources.rbi_xlsx.parsers import (
    SHIPPED_SPECS,
    IndicatorSpec,
    ParsedIndicator,
    ParsedRow,
)


def _spec_outstanding() -> IndicatorSpec:
    return IndicatorSpec(
        indicator_id="fiscal/outstanding_debt_pct_gsdp",
        sheet_match="ST_20",
        header_label_match="state",
        period_kind="fy_end_year",
    )


def _parsed_outstanding() -> ParsedIndicator:
    return ParsedIndicator(
        indicator_id="fiscal/outstanding_debt_pct_gsdp",
        rows=[
            # Accounts (facet=None): year-end stamp YYYY-03 lifts to YYYY-1.
            ParsedRow(entity_id="S22", time="2008-03", value=17.5),
            ParsedRow(entity_id="S01", time="2008-03", value=22.3),
            # RE / BE facets, distinct variable_ids.
            ParsedRow(entity_id="S22", time="2025-03", value=24.1, facet="RE"),
            ParsedRow(entity_id="S22", time="2026-03", value=25.0, facet="BE"),
            # Null row dropped.
            ParsedRow(entity_id="S22", time="2009-03", value=None),
        ],
        period_columns=4,
    )


def test_build_csv_variables_splits_by_facet():
    spec = _spec_outstanding()
    parsed = _parsed_outstanding()
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(spec, parsed, source_id=source_id)

    assert set(by_variable.keys()) == {
        "outstanding-debt-pct-gsdp",
        "outstanding-debt-pct-gsdp-revised-estimate",
        "outstanding-debt-pct-gsdp-budget-estimate",
    }
    accounts = by_variable["outstanding-debt-pct-gsdp"]
    # Two accounts rows survive; null is dropped; sorted by (entity_id, time).
    assert [(r["entity_id"], r["time"]) for r in accounts] == [
        ("S01", 2007),
        ("S22", 2007),
    ]
    for row in accounts:
        assert row["source_id"] == source_id
        assert isinstance(row["time"], int)
    re_rows = by_variable["outstanding-debt-pct-gsdp-revised-estimate"]
    assert len(re_rows) == 1 and re_rows[0]["time"] == 2024
    be_rows = by_variable["outstanding-debt-pct-gsdp-budget-estimate"]
    assert len(be_rows) == 1 and be_rows[0]["time"] == 2025


def test_fy_start_year_handles_span_and_end_year():
    # fy_span: YYYY-04 is start of FY YYYY-(YYYY+1); lift to YYYY.
    assert _fy_start_year("2023-04") == 2023
    # fy_end_year: YYYY-03 is end of FY (YYYY-1)-YYYY; lift to YYYY-1.
    assert _fy_start_year("2008-03") == 2007
    assert _fy_start_year("2026-03") == 2025


def test_slug_segment_is_kebab_and_ban_safe():
    assert _slug_segment("Outstanding Debt") == "outstanding-debt"
    assert _slug_segment("INR (crore)") == "inr-crore"
    assert "__" not in _slug_segment("foo__bar  baz")


def test_variable_id_map_covers_all_shipped_specs_and_is_grain_safe():
    assert {s.indicator_id for s in SHIPPED_SPECS} == set(
        _INDICATOR_TO_BASE_VARIABLE_ID.keys()
    )
    for vid in _INDICATOR_TO_BASE_VARIABLE_ID.values():
        assert "__" not in vid
        assert not vid.startswith(("state-", "district-", "national-"))
    # Every supported facet keeps the base id grain-safe.
    for spec in SHIPPED_SPECS:
        for facet in _FACET_SUFFIX:
            vid = _variable_id_for(spec, facet)
            assert "__" not in vid
            assert not vid.startswith(("state-", "district-", "national-"))


def test_emit_csv_variables_writes_one_file_per_variable(tmp_path: Path):
    spec = _spec_outstanding()
    parsed = _parsed_outstanding()
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _CSV_SOURCE_TITLE, _CSV_SOURCE_VINTAGE
    )
    by_variable = build_csv_variables(spec, parsed, source_id=source_id)
    written = emit_csv_variables(repo_root=tmp_path, by_variable=by_variable)

    assert len(written) == 3
    out_dir = tmp_path / _CSV_OUT_REL_DIR
    target = out_dir / "outstanding-debt-pct-gsdp.csv"
    assert target.exists()

    text = target.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "entity_id,time,value,source_id"
    assert text.endswith("\n")
    assert "\r" not in text

    with target.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["entity_id"] for r in rows] == ["S01", "S22"]
    assert [r["time"] for r in rows] == ["2007", "2007"]
    assert rows[0]["source_id"] == source_id


def test_file_class_matches_writer_glob():
    assert _CSV_FILE_CLASS == "datasets/data/datapoints/geo/*.csv"
