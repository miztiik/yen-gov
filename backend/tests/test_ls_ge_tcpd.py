"""Tier-A unit + contract tests for the TCPD historical-GE PC parser.

Per CLAUDE.md section 15: no mocks, no big-corpus walk. The parser tests use a
tiny inline TCPD-shaped CSV fixture; the resolver/envelope tests read only the
small committed reference CSV + entities.json + party lookup.

Pins:
1. ``parse_ls_ge_tcpd`` filters to ``Election_Type == GE``, the requested year,
   and ``Poll_No == 0`` (re-polls excluded); groups candidate rows per PC.
2. The Delhi spelling alias resolves; a reorganisation state (J&K) resolves
   through the crosswalk override; age is always None; education/profession are
   normalised from the panel columns; NOTA candidates are flagged.
3. A missing required column is a fail-fast.
4. The driver path (``build_pc_envelope_from_tcpd``) yields ``2008``-delimitation
   ``pc_id`` values and carries the TCPD education/profession enrichment onto the
   person rows, while the ECI 2024 default path stays byte-identical (guarded in
   test_eci_ls_driver.py).

See also:
    - backend/yen_gov/sources/eci/ls_ge_tcpd.py
    - backend/yen_gov/canonical/adapters/eci_ls.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yen_gov.canonical.adapters.eci.pc_crosswalk import load_crosswalk_and_lookup
from yen_gov.canonical.adapters.eci_ls import (
    EVENT_BY_GE_YEAR,
    LS_1999,
    LS_2004,
    LS_2009,
    LS_2014,
    LS_2019,
    build_pc_envelope_from_tcpd,
)
from yen_gov.sources.eci.ls_ge_tcpd import (
    LsGeTcpdError,
    TCPD_STATE_NAME_ALIASES,
    parse_ls_ge_tcpd,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS = REPO_ROOT / "datasets"

_HEADER = [
    "State_Name",
    "Constituency_No",
    "Constituency_Name",
    "Year",
    "Poll_No",
    "Election_Type",
    "Candidate",
    "Party",
    "Sex",
    "Votes",
    "Valid_Votes",
    "Electors",
    "MyNeta_education",
    "TCPD_Prof_Main",
]

GE = "Lok Sabha Election (GE)"


def _row(**kw: object) -> list[str]:
    base = {
        "State_Name": "Tamil_Nadu",
        "Constituency_No": "1",
        "Constituency_Name": "Tiruvallur",
        "Year": "2019",
        "Poll_No": "0",
        "Election_Type": GE,
        "Candidate": "A Candidate",
        "Party": "BJP",
        "Sex": "M",
        "Votes": "100",
        "Valid_Votes": "300",
        "Electors": "500",
        "MyNeta_education": "Graduate",
        "TCPD_Prof_Main": "Business",
    }
    base.update({k: str(v) for k, v in kw.items()})
    return [base[c] for c in _HEADER]


def _write_csv(tmp_path: Path, rows: list[list[str]]) -> Path:
    import csv

    p = tmp_path / "ge.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(_HEADER)
        w.writerows(rows)
    return p


@pytest.fixture(scope="module")
def crosswalk_lookup():
    return load_crosswalk_and_lookup(DATASETS)


# ---------------------------------------------------------------------------
# Pin 1: filtering + grouping
# ---------------------------------------------------------------------------

def test_filters_repoll_wrong_year_and_wrong_type(tmp_path, crosswalk_lookup):
    crosswalk, lookup = crosswalk_lookup
    rows = [
        _row(Candidate="Winner", Votes="200"),
        _row(Candidate="Runner Up", Party="DMK", Votes="100"),
        # Excluded: re-poll for the same seat.
        _row(Candidate="Repoll Ghost", Poll_No="1", Votes="999"),
        # Excluded: different year.
        _row(Candidate="Old Timer", Year="2014", Votes="999"),
        # Excluded: assembly election, not GE.
        _row(Candidate="Assembly Person", Election_Type="Assembly Election (AE)", Votes="999"),
    ]
    csv_path = _write_csv(tmp_path, rows)
    results = parse_ls_ge_tcpd(csv_path, year=2019, crosswalk=crosswalk, state_lookup=lookup)
    assert len(results) == 1
    (pc,) = results
    names = {c.name for c in pc.candidates}
    assert names == {"Winner", "Runner Up"}
    assert pc.state_code == "S22"  # Tamil Nadu
    assert pc.pc_no == 1


def test_groups_multiple_constituencies(tmp_path, crosswalk_lookup):
    crosswalk, lookup = crosswalk_lookup
    rows = [
        _row(Constituency_No="1", Constituency_Name="Tiruvallur", Candidate="A"),
        _row(Constituency_No="2", Constituency_Name="Chennai North", Candidate="B"),
        _row(Constituency_No="1", Constituency_Name="Tiruvallur", Candidate="C"),
    ]
    csv_path = _write_csv(tmp_path, rows)
    results = parse_ls_ge_tcpd(csv_path, year=2019, crosswalk=crosswalk, state_lookup=lookup)
    assert len(results) == 2
    by_no = {r.pc_no: r for r in results}
    assert {c.name for c in by_no[1].candidates} == {"A", "C"}
    assert {c.name for c in by_no[2].candidates} == {"B"}


# ---------------------------------------------------------------------------
# Pin 2: resolution, enrichment, NOTA
# ---------------------------------------------------------------------------

def test_delhi_alias_resolves(tmp_path, crosswalk_lookup):
    crosswalk, lookup = crosswalk_lookup
    assert TCPD_STATE_NAME_ALIASES["Delhi"] == "NCT of Delhi"
    rows = [_row(State_Name="Delhi", Constituency_No="1", Constituency_Name="Chandni Chowk")]
    csv_path = _write_csv(tmp_path, rows)
    (pc,) = parse_ls_ge_tcpd(csv_path, year=2019, crosswalk=crosswalk, state_lookup=lookup)
    assert pc.state_code == "U05"  # NCT of Delhi
    assert pc.pc_no == 1


def test_reorg_override_resolves_jk(tmp_path, crosswalk_lookup):
    crosswalk, lookup = crosswalk_lookup
    rows = [_row(State_Name="Jammu_&_Kashmir", Constituency_No="1", Constituency_Name="Baramulla")]
    csv_path = _write_csv(tmp_path, rows)
    (pc,) = parse_ls_ge_tcpd(csv_path, year=2019, crosswalk=crosswalk, state_lookup=lookup)
    # J&K seat 1 maps to the post-reorg J&K UT (U08).
    assert pc.state_code == "U08"
    assert pc.pc_no >= 1


def test_age_always_none_and_eduprof_normalised(tmp_path, crosswalk_lookup):
    crosswalk, lookup = crosswalk_lookup
    rows = [
        _row(
            Candidate="Bio Person",
            Sex="F",
            MyNeta_education="Post Graduate",
            TCPD_Prof_Main="Agriculture",
        ),
    ]
    csv_path = _write_csv(tmp_path, rows)
    (pc,) = parse_ls_ge_tcpd(csv_path, year=2019, crosswalk=crosswalk, state_lookup=lookup)
    (cand,) = pc.candidates
    assert cand.age is None
    assert cand.education == "Post Graduate"
    assert cand.profession == "Agriculture"
    assert cand.gender == "F"


def test_blank_eduprof_become_none(tmp_path, crosswalk_lookup):
    crosswalk, lookup = crosswalk_lookup
    rows = [_row(MyNeta_education="", TCPD_Prof_Main="")]
    csv_path = _write_csv(tmp_path, rows)
    (pc,) = parse_ls_ge_tcpd(csv_path, year=2019, crosswalk=crosswalk, state_lookup=lookup)
    (cand,) = pc.candidates
    assert cand.education is None
    assert cand.profession is None


def test_nota_flagged(tmp_path, crosswalk_lookup):
    crosswalk, lookup = crosswalk_lookup
    rows = [
        _row(Candidate="Real Person", Votes="100"),
        _row(Candidate="NOTA", Party="NOTA", Sex="", Votes="5", MyNeta_education="", TCPD_Prof_Main=""),
    ]
    csv_path = _write_csv(tmp_path, rows)
    (pc,) = parse_ls_ge_tcpd(csv_path, year=2019, crosswalk=crosswalk, state_lookup=lookup)
    nota = [c for c in pc.candidates if c.is_nota]
    assert len(nota) == 1
    assert nota[0].name == "NOTA"
    # total_votes_polled sums all candidate votes including NOTA.
    assert pc.total_votes_polled == 105


# ---------------------------------------------------------------------------
# Pin 3: fail-fast on malformed input
# ---------------------------------------------------------------------------

def test_missing_required_column_is_fatal(tmp_path, crosswalk_lookup):
    crosswalk, lookup = crosswalk_lookup
    p = tmp_path / "bad.csv"
    import csv

    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        # Drop MyNeta_education.
        header = [c for c in _HEADER if c != "MyNeta_education"]
        w.writerow(header)
        w.writerow(["Tamil_Nadu", "1", "X", "2019", "0", GE, "A", "BJP", "M", "1", "1", "1", "Business"])
    with pytest.raises(LsGeTcpdError, match="MyNeta_education"):
        parse_ls_ge_tcpd(p, year=2019, crosswalk=crosswalk, state_lookup=lookup)


def test_unresolvable_state_is_fatal(tmp_path, crosswalk_lookup):
    crosswalk, lookup = crosswalk_lookup
    rows = [_row(State_Name="Atlantis", Constituency_No="1")]
    csv_path = _write_csv(tmp_path, rows)
    with pytest.raises(LsGeTcpdError, match="resolve"):
        parse_ls_ge_tcpd(csv_path, year=2019, crosswalk=crosswalk, state_lookup=lookup)


# ---------------------------------------------------------------------------
# Pin 4: driver path produces 2008-delim pc_id + enrichment on persons
# ---------------------------------------------------------------------------

def test_envelope_from_tcpd_pcid_grammar_and_enrichment(tmp_path):
    rows = [
        _row(Constituency_No="1", Constituency_Name="Tiruvallur", Candidate="Winner",
             Votes="200", MyNeta_education="Doctorate", TCPD_Prof_Main="Education"),
        _row(Constituency_No="1", Constituency_Name="Tiruvallur", Candidate="Runner",
             Party="DMK", Votes="100", MyNeta_education="Graduate", TCPD_Prof_Main="Business"),
    ]
    csv_path = _write_csv(tmp_path, rows)
    env, pc_count, _unresolved = build_pc_envelope_from_tcpd(
        datasets_root=DATASETS,
        csv_path=csv_path,
        year=2019,
        event=LS_2019,
        allow_unknown_parties=True,
    )
    assert pc_count == 1
    (dim,) = env.pc_dim_rows
    assert dim.pc_id == "IN-PC-2008-S22-1"
    assert dim.delim_year == 2008
    # The TCPD enrichment must reach the person rows.
    edu = {p.education for p in env.person_dim_rows}
    prof = {p.profession for p in env.person_dim_rows}
    assert "Doctorate" in edu
    assert "Education" in prof
    # Historical GE carries no age.
    assert all(p.age is None for p in env.person_dim_rows)


# ---------------------------------------------------------------------------
# Pin 5: PR-4 — 2009 + 2014 events (both 2008 delimitation)
# ---------------------------------------------------------------------------

def test_event_registry_has_2009_and_2014():
    for year, label, seq in ((2009, "LsGenMay2009", 3), (2014, "LsGenMay2014", 4)):
        event = EVENT_BY_GE_YEAR[year]
        assert event.delim_year == 2008
        assert event.period.period_label == label
        assert event.period.year == year
        assert event.period.period_seq == seq
        assert event.source_input_id == "tcpd_ge"


@pytest.mark.parametrize("year, event", [(2009, LS_2009), (2014, LS_2014)])
def test_ap_undivided_numbering_splits_to_modern_successors(
    tmp_path, crosswalk_lookup, year, event
):
    """Undivided-AP seats (1-42) split onto modern Telangana (S29) + AP (S01).

    Telangana split from Andhra Pradesh on 2 June 2014, after both the 2009 and
    2014 polls. TCPD numbers the seats within undivided AP (1-42); the crosswalk
    maps 1-17 to Telangana (S29, same pc_no) and 18-42 to residual AP (S01,
    offset -17).
    """
    crosswalk, lookup = crosswalk_lookup
    rows = [
        _row(State_Name="Andhra_Pradesh", Constituency_No="17",
             Constituency_Name="Khammam", Year=str(year), Candidate="TG Person"),
        _row(State_Name="Andhra_Pradesh", Constituency_No="18",
             Constituency_Name="Araku", Year=str(year), Candidate="AP Person"),
    ]
    csv_path = _write_csv(tmp_path, rows)
    results = parse_ls_ge_tcpd(csv_path, year=year, crosswalk=crosswalk, state_lookup=lookup)
    by_state = {(r.state_code, r.pc_no) for r in results}
    assert ("S29", 17) in by_state  # Telangana seat keeps its number
    assert ("S01", 1) in by_state  # residual AP seat renumbered (18 - 17)


def test_envelope_2014_carries_event_period(tmp_path):
    rows = [
        _row(Constituency_No="1", Constituency_Name="Tiruvallur", Candidate="Winner",
             Year="2014", Votes="200"),
    ]
    csv_path = _write_csv(tmp_path, rows)
    env, pc_count, _unresolved = build_pc_envelope_from_tcpd(
        datasets_root=DATASETS,
        csv_path=csv_path,
        year=2014,
        event=LS_2014,
        allow_unknown_parties=True,
    )
    assert pc_count == 1
    (dim,) = env.pc_dim_rows
    assert dim.pc_id == "IN-PC-2008-S22-1"
    assert dim.delim_year == 2008
    # Observations must be stamped with the 2014 period, not the 2024 default.
    assert any(o.period_label == "LsGenMay2014" for o in env.observation_rows)
    assert all(o.period_label != "LsGenJun2024" for o in env.observation_rows)


# ---------------------------------------------------------------------------
# Pin 6: PR-5 — 1999 + 2004 events (both 1976 delimitation; table-only years)
# ---------------------------------------------------------------------------

def test_event_registry_has_1999_and_2004():
    for year, label, seq in ((1999, "LsGenOct1999", 1), (2004, "LsGenMay2004", 2)):
        event = EVENT_BY_GE_YEAR[year]
        assert event.delim_year == 1976
        assert event.period.period_label == label
        assert event.period.year == year
        assert event.period.period_seq == seq
        assert event.source_input_id == "tcpd_ge"


@pytest.mark.parametrize("year, event", [(1999, LS_1999), (2004, LS_2004)])
def test_1976_delim_pcid_carries_1976_prefix(tmp_path, year, event):
    """1976-delimitation years stamp ``IN-PC-1976-*`` so the map can gray them.

    The product paints a choropleth only for 2008-delimitation years; the
    ``delim_year`` embedded in the ``pc_id`` is the single source of truth that
    distinguishes a "boundaries differ" historical year from a paint-able one.
    """
    rows = [
        _row(State_Name="Tamil_Nadu", Constituency_No="1",
             Constituency_Name="Madras North", Year=str(year), Candidate="Winner"),
    ]
    csv_path = _write_csv(tmp_path, rows)
    env, pc_count, _unresolved = build_pc_envelope_from_tcpd(
        datasets_root=DATASETS,
        csv_path=csv_path,
        year=year,
        event=event,
        allow_unknown_parties=True,
    )
    assert pc_count == 1
    (dim,) = env.pc_dim_rows
    assert dim.pc_id == "IN-PC-1976-S22-1"
    assert dim.delim_year == 1976


def test_1999_pre2000_states_code_as_was(tmp_path, crosswalk_lookup):
    """1999 has no Chhattisgarh/Jharkhand/Uttarakhand; seats sit in parent states.

    Those states were created in 2000. The TCPD 1999 panel numbers their seats
    inside Madhya Pradesh / Bihar / Uttar Pradesh, and the automatic resolver
    codes them as-was (no override rows).
    """
    crosswalk, lookup = crosswalk_lookup
    rows = [
        _row(State_Name="Madhya_Pradesh", Constituency_No="1",
             Constituency_Name="Morena", Year="1999", Candidate="MP Person"),
    ]
    csv_path = _write_csv(tmp_path, rows)
    (result,) = parse_ls_ge_tcpd(
        csv_path, year=1999, crosswalk=crosswalk, state_lookup=lookup
    )
    assert result.state_code == "S12"  # Madhya Pradesh, undivided


def test_envelope_1999_carries_event_period(tmp_path):
    rows = [
        _row(Constituency_No="1", Constituency_Name="Madras North", Candidate="Winner",
             Year="1999", Votes="200", State_Name="Tamil_Nadu"),
    ]
    csv_path = _write_csv(tmp_path, rows)
    env, pc_count, _unresolved = build_pc_envelope_from_tcpd(
        datasets_root=DATASETS,
        csv_path=csv_path,
        year=1999,
        event=LS_1999,
        allow_unknown_parties=True,
    )
    assert pc_count == 1
    (dim,) = env.pc_dim_rows
    assert dim.pc_id == "IN-PC-1976-S22-1"
    assert dim.delim_year == 1976
    assert any(o.period_label == "LsGenOct1999" for o in env.observation_rows)
    assert all(o.period_label != "LsGenJun2024" for o in env.observation_rows)

