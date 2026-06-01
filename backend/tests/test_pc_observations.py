"""PR-A3 tests — ECI Lok Sabha (PC) parser + pc-* observation adapter.

Uses tiny synthetic Report-33 / Report-34 fixtures (NOT the real corpus per
CLAUDE.md §10). Entity/party resolution reads the real
``datasets/taxonomy/{entities,parties}.json`` because those are canonical
registries, not election corpus.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.eci.identity import Period
from yen_gov.canonical.adapters.eci.party_lookup import load_party_lookup
from yen_gov.canonical.adapters.eci.pc_observations import (
    dim_rows_from_pc,
    observations_from_pc,
)
from yen_gov.sources.eci.ls_constituencywise import (
    LsConstituencywiseError,
    parse_ls_constituencywise,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS_ROOT = REPO_ROOT / "datasets"

# Report-33 header row (index 2). The per-PC total-polled column carries an
# embedded newline in the real source file; reproduce it faithfully.
_R33_HEADER = [
    "State Name", "PC Name", "Candidate Name", "Gender", "Age", "Category",
    "Party Name", "Total Votes Polled In\nThe Constituency", "Valid Votes",
    "General", "Postal", "Total", "Total Electors",
]


def _r33_row(state, pc, cand, party, polled, valid, general, postal, total, electors):
    return [
        state, pc, cand, "MALE", "50", "GENERAL", party,
        str(polled), str(valid), str(general), str(postal), str(total),
        str(electors),
    ]


def _write_report33(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["33 - CONSTITUENCY WISE DETAILED RESULT"])
        w.writerow(["", "", "", "", "", "", "", "Votes Secured"])
        w.writerow(_R33_HEADER)
        for row in rows:
            w.writerow(row)
        w.writerow(["Disclaimer: these are provisional figures."])


def _write_report34(path: Path, triples: list[tuple[str, int, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["34 - DETAILS OF ASSEMBLY SEGMENT OF PC"])
        w.writerow(["State/UT Name", "PC NO", "PC NAME"])
        for state, pc_no, pc_name in triples:
            w.writerow([state, str(pc_no), pc_name])


@pytest.fixture()
def fixture_pair(tmp_path: Path) -> tuple[Path, Path]:
    r33 = tmp_path / "report33.csv"
    r34 = tmp_path / "report34.csv"
    rows = [
        # Chennai South (pc 4) — DMK winner over AIADMK, with NOTA.
        _r33_row("Tamil Nadu", "Chennai South", "Alice", "Dravida Munnetra Kazhagam",
                 820000, 810000, 495000, 5000, 500000, 1000000),
        _r33_row("Tamil Nadu", "Chennai South", "Bob", "All India Anna Dravida Munnetra Kazhagam",
                 820000, 810000, 297000, 3000, 300000, 1000000),
        _r33_row("Tamil Nadu", "Chennai South", "None of the Above", "NOTA",
                 820000, 810000, 9900, 100, 10000, 1000000),
        # Chennai North (pc 3) — BJP winner over INC.
        _r33_row("Tamil Nadu", "Chennai North", "Carol", "Bharatiya Janata Party",
                 760000, 755000, 396000, 4000, 400000, 900000),
        _r33_row("Tamil Nadu", "Chennai North", "Dan", "Indian National Congress",
                 760000, 755000, 347000, 3000, 350000, 900000),
        _r33_row("Tamil Nadu", "Chennai North", "None of the Above", "NOTA",
                 760000, 755000, 4950, 50, 5000, 900000),
    ]
    _write_report33(r33, rows)
    _write_report34(r34, [
        ("Tamil Nadu", 4, "Chennai South"),
        ("Tamil Nadu", 3, "Chennai North"),
    ])
    return r33, r34


def test_parse_yields_two_pcs(fixture_pair):
    r33, r34 = fixture_pair
    results = parse_ls_constituencywise(r33, crosswalk_path=r34, datasets_root=DATASETS_ROOT)
    assert len(results) == 2
    chennai_south = next(r for r in results if r.pc_name == "Chennai South")
    assert chennai_south.state_code == "S22"
    assert chennai_south.pc_no == 4
    assert chennai_south.total_electors == 1000000
    assert chennai_south.total_votes_polled == 820000
    # 3 candidate rows incl NOTA.
    assert len(chennai_south.candidates) == 3
    assert sum(1 for c in chennai_south.candidates if c.is_nota) == 1


def test_observations_winner_margin_turnout(fixture_pair):
    r33, r34 = fixture_pair
    results = parse_ls_constituencywise(r33, crosswalk_path=r34, datasets_root=DATASETS_ROOT)
    lookup = load_party_lookup(DATASETS_ROOT)
    period = Period(period_label="LsGenJun2024", year=2024, period_seq=6)
    chennai_south = next(r for r in results if r.pc_name == "Chennai South")
    rows = observations_from_pc(
        result=chennai_south, period=period, delim_year=2008,
        party_lookup=lookup, source_id="src-test",
    )
    by_ind = {r.indicator_id: r for r in rows if r.entity_id == "IN-PC-2008-S22-4"}

    # Winner party = DMK (value_text), winner candidate id rank 1.
    assert by_ind["pc-winner-party-id"].value_text == "parties.IN.DMK"
    assert by_ind["pc-winner-candidate-id"].value_text == "IN-PC-2008-S22-4-LsGenJun2024-C01"
    # Margin = 500000 − 300000.
    assert by_ind["pc-margin-votes"].value_numeric == 200000.0
    # Turnout = 820000 / 1000000 * 100.
    assert by_ind["pc-turnout-pct"].value_numeric == pytest.approx(82.0)
    # NOTA votes raw + pct over polled.
    assert by_ind["pc-nota-votes"].value_numeric == 10000.0
    assert by_ind["pc-nota-pct"].value_numeric == pytest.approx(10000 / 820000 * 100)
    # Field size excludes NOTA.
    assert by_ind["pc-candidates-total"].value_numeric == 2.0
    # No collapsed tail -> no others rows.
    assert "pc-others-votes" not in by_ind


def test_dim_rows_from_pc(fixture_pair):
    r33, r34 = fixture_pair
    results = parse_ls_constituencywise(r33, crosswalk_path=r34, datasets_root=DATASETS_ROOT)
    chennai_north = next(r for r in results if r.pc_name == "Chennai North")
    dims = dim_rows_from_pc(result=chennai_north, delim_year=2008, source_id="src-test")
    assert dims == [{
        "pc_id": "IN-PC-2008-S22-3",
        "state_code": "S22",
        "delim_year": 2008,
        "pc_no": 3,
        "name": "Chennai North",
        "source_id": "src-test",
    }]


def test_header_shift_raises(tmp_path: Path):
    """A Report-33 whose header is not at row index 2 fails fast."""
    r33 = tmp_path / "bad33.csv"
    with r33.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        # Header is mis-placed: the real header sits at row index 1, leaving a
        # group sub-header (missing required columns) at index 2 where the
        # parser asserts. Data rows follow so the "no data rows" guard passes.
        w.writerow(["33 - CONSTITUENCY WISE DETAILED RESULT"])
        w.writerow(_R33_HEADER)
        w.writerow(["", "", "", "", "", "", "", "Votes Secured"])
        w.writerow(_r33_row("Tamil Nadu", "Chennai South", "Alice", "DMK",
                            820000, 810000, 495000, 5000, 500000, 1000000))
        w.writerow(_r33_row("Tamil Nadu", "Chennai South", "Bob", "AIADMK",
                            820000, 810000, 297000, 3000, 300000, 1000000))
    r34 = tmp_path / "ok34.csv"
    _write_report34(r34, [("Tamil Nadu", 4, "Chennai South")])
    with pytest.raises(LsConstituencywiseError, match="missing required columns"):
        parse_ls_constituencywise(r33, crosswalk_path=r34, datasets_root=DATASETS_ROOT)


def test_crosswalk_conflict_raises(tmp_path: Path):
    r34 = tmp_path / "conflict34.csv"
    _write_report34(r34, [
        ("Tamil Nadu", 4, "Chennai South"),
        ("Tamil Nadu", 5, "Chennai South"),
    ])
    from yen_gov.sources.eci.ls_constituencywise import parse_pc_crosswalk
    with pytest.raises(LsConstituencywiseError, match="conflicting PC NO"):
        parse_pc_crosswalk(r34)


def test_pc_absent_from_crosswalk_raises(fixture_pair, tmp_path: Path):
    r33, _ = fixture_pair
    r34 = tmp_path / "partial34.csv"
    _write_report34(r34, [("Tamil Nadu", 4, "Chennai South")])  # missing Chennai North
    with pytest.raises(LsConstituencywiseError, match="absent from Report 34 crosswalk"):
        parse_ls_constituencywise(r33, crosswalk_path=r34, datasets_root=DATASETS_ROOT)
