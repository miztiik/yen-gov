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


# --- B2b.5.1 election file-class roundtrips --------------------------------
#
# Sub-sub-plan B2b.5.1 pins write-time validator passthrough for the four
# election file classes declared in columns.json (added by B1.1, PR #629).
# Each test here writes ONE sample row through the generic writer to confirm
# the header, dtype coercion, and (where declared) PK sort behave correctly
# under the election column shape. The cross-format-parity gate (parent 22.6)
# will exercise these emitters against real on-disk parquet in B2b.5.2..5.4.


_ASSEMBLY_CANDIDACIES_FC = (
    "datasets/elections/assembly/state=*/election=*/candidacies.csv"
)
_ASSEMBLY_SUMMARY_FC = (
    "datasets/elections/assembly/state=*/election=*/summary.csv"
)
_PARLIAMENT_CANDIDACIES_FC = (
    "datasets/elections/parliament/election=*/candidacies.csv"
)
_PARLIAMENT_SUMMARY_FC = (
    "datasets/elections/parliament/election=*/summary.csv"
)


def _assembly_candidacy_row(*, entity_id: str, position: int) -> dict:
    return {
        "entity_id": entity_id,
        "state": "tamil-nadu",
        "election_year": 2021,
        "constituency_no": 234,
        "constituency_name": "Kanyakumari",
        "candidate_name": f"Candidate {position}",
        "party_id": "p-bjp",
        "votes": 50000 - position,
        "vote_share_pct": 45.5 - position,
        "position": position,
        "result": "won" if position == 1 else "lost",
        "sex": "M",
        "age": 45 + position,
        "education": "Graduate",
        "profession": "Politics",
        "candidate_type": "incumbent",
        "source_id": "tcpd-ge-2021",
    }


def test_writes_assembly_candidacies_file_class(tmp_path):
    path = tmp_path / "candidacies.csv"
    write_csv(
        path=path,
        file_class=_ASSEMBLY_CANDIDACIES_FC,
        rows=[
            _assembly_candidacy_row(entity_id="IN-AC-2008-S22-234", position=2),
            _assembly_candidacy_row(entity_id="IN-AC-2008-S22-234", position=1),
        ],
    )
    lines = _read(path).splitlines()
    assert lines[0] == (
        "entity_id,state,election_year,constituency_no,constituency_name,"
        "candidate_name,party_id,votes,vote_share_pct,position,result,"
        "sex,age,education,profession,candidate_type,source_id"
    )
    # No PK on candidacies; input order is preserved (stable sort by empty key).
    assert lines[1].startswith("IN-AC-2008-S22-234,tamil-nadu,2021,234,Kanyakumari,Candidate 2,")
    assert lines[2].startswith("IN-AC-2008-S22-234,tamil-nadu,2021,234,Kanyakumari,Candidate 1,")


def test_assembly_candidacies_rejects_bad_result_value_at_validator_time(tmp_path):
    # The writer is dtype-strict but enum-relaxed (enum lives on the validator).
    # Verify the writer happily round-trips an unrecognised enum string so the
    # validator catches it (one source of truth for closed-enum membership).
    path = tmp_path / "candidacies.csv"
    row = _assembly_candidacy_row(entity_id="IN-AC-2008-S22-234", position=1)
    row["result"] = "tied"  # not in {won, lost, forfeit}
    write_csv(path=path, file_class=_ASSEMBLY_CANDIDACIES_FC, rows=[row])
    assert "tied" in _read(path)


def test_writes_assembly_summary_file_class_with_pk_sort(tmp_path):
    path = tmp_path / "summary.csv"
    write_csv(
        path=path,
        file_class=_ASSEMBLY_SUMMARY_FC,
        rows=[
            {
                "entity_id": "IN-AC-2008-S22-234",
                "state": "tamil-nadu",
                "election_year": 2021,
                "constituency_name": "Kanyakumari",
                "electors": 250000,
                "votes_polled": 180000,
                "turnout_pct": 72.0,
                "winner_candidate": "Alice",
                "winner_party_id": "p-bjp",
                "winner_votes": 95000,
                "winner_share_pct": 52.78,
                "runnerup_candidate": "Bob",
                "runnerup_party_id": "p-dmk",
                "runnerup_votes": 60000,
                "margin_votes": 35000,
                "margin_pct": 19.45,
                "source_id": "tcpd-ae-2021",
            },
            {
                "entity_id": "IN-AC-2008-S22-001",
                "state": "tamil-nadu",
                "election_year": 2021,
                "constituency_name": "Gummidipoondi",
                "electors": 230000,
                "votes_polled": 170000,
                "turnout_pct": 73.9,
                "winner_candidate": "Carol",
                "winner_party_id": "p-dmk",
                "winner_votes": 90000,
                "winner_share_pct": 52.94,
                "runnerup_candidate": "Dan",
                "runnerup_party_id": "p-bjp",
                "runnerup_votes": 55000,
                "margin_votes": 35000,
                "margin_pct": 20.59,
                "source_id": "tcpd-ae-2021",
            },
        ],
    )
    lines = _read(path).splitlines()
    # PK is entity_id; rows sort ascending so AC-001 precedes AC-234.
    assert lines[1].startswith("IN-AC-2008-S22-001,")
    assert lines[2].startswith("IN-AC-2008-S22-234,")


def test_writes_parliament_candidacies_file_class_with_mandatory_state(tmp_path):
    path = tmp_path / "candidacies.csv"
    row = _assembly_candidacy_row(entity_id="IN-PC-2008-S22-39", position=1)
    row["constituency_no"] = 39
    row["constituency_name"] = "Kanyakumari"
    write_csv(path=path, file_class=_PARLIAMENT_CANDIDACIES_FC, rows=[row])
    lines = _read(path).splitlines()
    assert lines[0] == (
        "entity_id,state,election_year,constituency_no,constituency_name,"
        "candidate_name,party_id,votes,vote_share_pct,position,result,"
        "sex,age,education,profession,candidate_type,source_id"
    )
    assert "tamil-nadu" in lines[1]


def test_parliament_candidacies_rejects_missing_mandatory_state(tmp_path):
    # plan section 23.4: state is MANDATORY on parliament CSVs even though the
    # path has no state= partition (constituency_no restarts per state).
    row = _assembly_candidacy_row(entity_id="IN-PC-2008-S22-39", position=1)
    row["state"] = None
    with pytest.raises(ValueError, match="non-nullable"):
        write_csv(
            path=tmp_path / "candidacies.csv",
            file_class=_PARLIAMENT_CANDIDACIES_FC,
            rows=[row],
        )


def test_writes_parliament_summary_file_class(tmp_path):
    path = tmp_path / "summary.csv"
    write_csv(
        path=path,
        file_class=_PARLIAMENT_SUMMARY_FC,
        rows=[
            {
                "entity_id": "IN-PC-2008-S22-39",
                "state": "tamil-nadu",
                "election_year": 2024,
                "constituency_name": "Kanyakumari",
                "electors": 1500000,
                "votes_polled": 1100000,
                "turnout_pct": 73.33,
                "winner_candidate": "Eve",
                "winner_party_id": "p-inc",
                "winner_votes": 550000,
                "winner_share_pct": 50.0,
                "runnerup_candidate": "Frank",
                "runnerup_party_id": "p-bjp",
                "runnerup_votes": 400000,
                "margin_votes": 150000,
                "margin_pct": 13.64,
                "source_id": "tcpd-ge-2024",
            },
        ],
    )
    lines = _read(path).splitlines()
    assert lines[0] == (
        "entity_id,state,election_year,constituency_name,electors,votes_polled,"
        "turnout_pct,winner_candidate,winner_party_id,winner_votes,"
        "winner_share_pct,runnerup_candidate,runnerup_party_id,runnerup_votes,"
        "margin_votes,margin_pct,source_id"
    )
    assert lines[1].startswith("IN-PC-2008-S22-39,tamil-nadu,2024,Kanyakumari,")
    # winner_votes is integer-dtype number; 550000 must emit without ".0".
    assert ",550000," in lines[1]
