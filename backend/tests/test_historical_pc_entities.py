"""PR-Q7c tests for the historical PC entity minter + the multi-delim parliament emit.

Pin the behaviour of
``backend/yen_gov/canonical/reingest/_run_historical_pc_entities.py``:

  (1) ``build_entity_rows`` mints rows of the correct shape (entity_id
      format, name selection, delim_year derivation, reservation).
  (2) ``append_new_rows`` is idempotent: rows whose ``entity_id`` is
      already on ``electoral.csv`` are skipped.
  (3) Defunct TCPD state names (``Madras`` / ``Mysore`` /
      ``Goa_Daman_&_Diu`` / ``Goa,_Daman_&_Diu``) are dropped at the
      group-key boundary. The PC minter recognises BOTH Goa variants
      (the GE compilation uses the comma form 1967-1984).
  (4) ``aliases`` collects every historical ``Constituency_Name`` variant
      pipe-joined, EXCLUDING the chosen ``name``.
  (5) On naming-mode ties, alphabetical sort wins (deterministic).
  (6) Integration: a single ``ge.csv`` with both DelimID 3 (1999) +
      DelimID 4 (2009) rows for the same (state, eci_no) emits to two
      distinct year files, each bound to the correct PC entity cohort.
  (7) The minter walks exactly the PR-Q7a historical DelimIDs.
  (8) The appended row block is byte-stable sorted by
      ``(delim_year, state, eci_no)``.

No real-corpus walk (CLAUDE.md anti-pattern). All fixtures synthetic
under ``tmp_path``.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from yen_gov.canonical.reingest import parliament_results
from yen_gov.canonical.reingest._run_historical_pc_entities import (
    HISTORICAL_DELIM_IDS,
    SKIP_STATES,
    append_new_rows,
    build_entity_rows,
)
from yen_gov.canonical.reingest.assembly_results import (
    TCPD_DELIM_ID_TO_DELIM_YEAR,
)

SOURCE_ID = "src-tcpd-ge-q7c-test"

_GE_HEADER = [
    "State_Name", "Constituency_No", "Year", "DelimID", "Poll_No", "Position",
    "Candidate", "Sex", "Party", "Votes", "Age", "Deposit_Lost", "Valid_Votes",
    "Electors", "Constituency_Name", "Constituency_Type",
    "Turnout_Percentage", "Vote_Share_Percentage", "Incumbent", "Turncoat",
    "MyNeta_education", "TCPD_Prof_Main_Desc",
]


def _ge_row(**over) -> dict[str, str]:
    base = {
        "State_Name": "Bihar", "Constituency_No": "1", "Year": "1999",
        "DelimID": "3", "Poll_No": "0", "Position": "1", "Candidate": "A",
        "Sex": "M", "Party": "INC", "Votes": "100", "Age": "50",
        "Deposit_Lost": "no", "Valid_Votes": "180", "Electors": "250",
        "Constituency_Name": "Patliputra", "Constituency_Type": "GEN",
        "Turnout_Percentage": "72.0", "Vote_Share_Percentage": "55.5",
        "Incumbent": "FALSE", "Turncoat": "FALSE",
        "MyNeta_education": "Graduate", "TCPD_Prof_Main_Desc": "Lawyer",
    }
    base.update({k: str(v) for k, v in over.items()})
    return base


def _write_ge(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=_GE_HEADER, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in _GE_HEADER})
    path.write_text(buf.getvalue(), encoding="utf-8", newline="")
    return path


def _write_electoral(path: Path, body: list[str] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation"]
    if body:
        lines.extend(body)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# --- Test 1: mint shape ------------------------------------------------------


def test_mint_pc_entities_correct_id_shape(tmp_path):
    """Verify entity_id, delim_year, state slug, eci_no, reservation derivation.

    Two source rows: one DelimID=3 (year 1999) for Bihar PC 12, one
    DelimID=1 (year 1962) for Bihar PC 7. Expectation: the minter emits
    two rows with ids ``IN-PC-1976-bihar-12`` + ``IN-PC-1962-bihar-7``,
    each carrying ``entity_kind=pc``, the matching delim_year, the
    slugified state, and the source's Constituency_Type as ``reservation``.
    """
    ge = _write_ge(
        tmp_path / "ge.csv",
        [
            _ge_row(
                State_Name="Bihar", DelimID=3, Year=1999, Constituency_No=12,
                Constituency_Name="Patna East", Constituency_Type="GEN",
            ),
            _ge_row(
                State_Name="Bihar", DelimID=1, Year=1962, Constituency_No=7,
                Constituency_Name="Gaya", Constituency_Type="SC",
            ),
        ],
    )

    rows, counts, ties = build_entity_rows(ge)

    assert ties == []
    assert sorted(r["entity_id"] for r in rows) == [
        "IN-PC-1962-bihar-7",
        "IN-PC-1976-bihar-12",
    ]
    by_id = {r["entity_id"]: r for r in rows}

    patna_east = by_id["IN-PC-1976-bihar-12"]
    assert patna_east["name"] == "Patna East"
    assert patna_east["entity_kind"] == "pc"
    assert patna_east["delim_year"] == "1976"
    assert patna_east["state"] == "bihar"
    assert patna_east["parent"] == ""
    assert patna_east["eci_no"] == "12"
    assert patna_east["reservation"] == "GEN"
    assert patna_east["aliases"] == ""

    gaya = by_id["IN-PC-1962-bihar-7"]
    assert gaya["delim_year"] == "1962"
    assert gaya["reservation"] == "SC"
    assert gaya["name"] == "Gaya"

    assert counts == {("bihar", "3"): 1, ("bihar", "1"): 1}


# --- Test 2: idempotency on existing entity_id -------------------------------


def test_mint_pc_skips_existing(tmp_path):
    """A pre-existing row with the same derived entity_id is NOT duplicated.

    Stage ``electoral.csv`` with one historical row; the minter sees a
    matching TCPD group and emits the row in ``candidate_rows`` (the pure
    builder does not know about disk state); ``append_new_rows`` then
    skips it.
    """
    electoral = _write_electoral(
        tmp_path / "electoral.csv",
        ["IN-PC-1976-bihar-1,Patliputra,pc,1976,bihar,,1,,GEN"],
    )
    ge = _write_ge(
        tmp_path / "ge.csv",
        [_ge_row(State_Name="Bihar", DelimID=3, Year=1999, Constituency_No=1,
                 Constituency_Name="Patliputra", Constituency_Type="GEN")],
    )
    rows, _counts, _ties = build_entity_rows(ge)
    assert len(rows) == 1

    n_new, n_skipped = append_new_rows(electoral, rows)
    assert n_new == 0
    assert n_skipped == 1

    # File byte-identical (the existing row remains; no append).
    assert electoral.read_text(encoding="utf-8") == (
        "entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation\n"
        "IN-PC-1976-bihar-1,Patliputra,pc,1976,bihar,,1,,GEN\n"
    )


# --- Test 3: defunct state names are skipped (both Goa variants) ------------


def test_mint_pc_skips_defunct_state(tmp_path):
    """``Madras`` / ``Mysore`` / both ``Goa*Daman_&_Diu`` shapes dropped silently.

    The GE compilation uses the comma form ``Goa,_Daman_&_Diu`` for
    1967-1984; the AE compilation uses ``Goa_Daman_&_Diu`` (no comma)
    for an analogous role. PR-Q7c's PC minter recognises BOTH so the
    cross-compilation defunct-state rule stays uniform.
    """
    ge = _write_ge(
        tmp_path / "ge.csv",
        [
            _ge_row(State_Name="Madras", DelimID=1, Year=1962,
                    Constituency_No=1, Constituency_Name="Madras-1"),
            _ge_row(State_Name="Mysore", DelimID=2, Year=1967,
                    Constituency_No=2, Constituency_Name="Mysore-1"),
            # GE-specific defunct form (with comma).
            _ge_row(State_Name="Goa,_Daman_&_Diu", DelimID=3, Year=1980,
                    Constituency_No=3, Constituency_Name="Panaji"),
            # AE form (no comma) - defensive shared rule.
            _ge_row(State_Name="Goa_Daman_&_Diu", DelimID=3, Year=1980,
                    Constituency_No=4, Constituency_Name="Mapusa"),
            # Sanity row for a kept state so the minter has SOMETHING to emit.
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=5, Constituency_Name="Bihar-PC-5",
                    Constituency_Type="GEN"),
        ],
    )

    rows, counts, _ties = build_entity_rows(ge)

    # All four defunct-state rows dropped at group-key boundary.
    assert {"Madras", "Mysore", "Goa_Daman_&_Diu", "Goa,_Daman_&_Diu"} <= SKIP_STATES
    assert [r["entity_id"] for r in rows] == ["IN-PC-1976-bihar-5"]
    assert counts == {("bihar", "3"): 1}


# --- Test 4: aliases collect every historical Constituency_Name variant -----


def test_mint_pc_aliases_collect_name_variants(tmp_path):
    """Three TCPD rows with three name spellings -> aliases column has the rest.

    The most-recent (Year=2004) spelling wins as ``name``; the older
    variants (Year=1989, Year=1996) are collected into ``aliases``
    pipe-joined, deduped case-insensitively, sorted alphabetically.
    Case-difference variants of the chosen name are EXCLUDED from
    aliases (so the alias never duplicates ``name``).
    """
    ge = _write_ge(
        tmp_path / "ge.csv",
        [
            _ge_row(State_Name="Bihar", DelimID=3, Year=1989,
                    Constituency_No=12, Constituency_Name="Patna-East"),
            _ge_row(State_Name="Bihar", DelimID=3, Year=1996,
                    Constituency_No=12, Constituency_Name="PATNA-EAST"),
            _ge_row(State_Name="Bihar", DelimID=3, Year=2004,
                    Constituency_No=12, Constituency_Name="Patna East"),
        ],
    )
    rows, _counts, ties = build_entity_rows(ge)
    assert len(rows) == 1
    row = rows[0]

    assert row["name"] == "Patna East"  # the Year=2004 spelling wins
    # Aliases: deduped case-insensitively (Patna-East + PATNA-EAST collapse
    # to one entry); the chosen-name's case-variants are excluded.
    assert row["aliases"] == "Patna-East"
    assert ties == []


def test_mint_pc_records_naming_mode_ties(tmp_path):
    """When the most-recent year has a mode-tie, the receipt records the row.

    Year 1999 carries two names with the same count: ``Aurangabad`` and
    ``Aurangbad``. Alphabetical order wins -> ``Aurangabad`` becomes the
    canonical name; the tie is logged. Older-year variants still flow into
    aliases.
    """
    ge = _write_ge(
        tmp_path / "ge.csv",
        [
            _ge_row(State_Name="Bihar", DelimID=3, Year=1989, Position=1,
                    Constituency_No=20, Constituency_Name="Aurangabad-1989"),
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999, Position=1,
                    Constituency_No=20, Constituency_Name="Aurangabad"),
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999, Position=2,
                    Constituency_No=20, Constituency_Name="Aurangbad"),
        ],
    )
    rows, _counts, ties = build_entity_rows(ge)
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Aurangabad"  # alphabetical break on mode tie
    assert ties == [("bihar", "3", 20, "Aurangabad")]
    # Both alternative names land in aliases (deduped, sorted).
    assert row["aliases"] == "Aurangabad-1989|Aurangbad"


# --- Test 5: parliament binder binds per-delim against the right cohort -----


def test_mint_pc_multi_delim_binding(tmp_path):
    """Two GE rows (DelimID 3 year 1999 + DelimID 4 year 2009) for the same
    state + eci_no bind to two distinct cohorts when both entity rows exist.

    The driver-side multi-delim loop calls ``emit_parliament`` once per
    delim. This test exercises the binder directly twice to mirror that
    shape (no temporal coupling between the calls). Both writes succeed
    against their corresponding entities and land in distinct year files.
    """
    # Note: parliament needs >= 2 candidates per PC to be a valid contest
    # (winner + runner-up). Stage 2 per (state, year, pc) row group.
    ge = _write_ge(
        tmp_path / "datasets" / "ephemeral" / "All_States_GE.csv",
        [
            # DelimID 3, year 1999 -- binds against the 1976 PC cohort.
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=12, Position=1, Candidate="W",
                    Party="INC", Votes=100, Vote_Share_Percentage=55.5,
                    Deposit_Lost="no"),
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=12, Position=2, Candidate="R",
                    Party="INC", Votes=80, Vote_Share_Percentage=44.5,
                    Deposit_Lost="no"),
            # DelimID 4, year 2009 -- binds against the 2008 PC cohort.
            _ge_row(State_Name="Bihar", DelimID=4, Year=2009,
                    Constituency_No=12, Position=1, Candidate="W",
                    Party="INC", Votes=100, Vote_Share_Percentage=55.5,
                    Deposit_Lost="no"),
            _ge_row(State_Name="Bihar", DelimID=4, Year=2009,
                    Constituency_No=12, Position=2, Candidate="R",
                    Party="INC", Votes=80, Vote_Share_Percentage=44.5,
                    Deposit_Lost="no"),
        ],
    )

    entities = tmp_path / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    _write_electoral(
        entities / "electoral.csv",
        [
            "IN-PC-1976-bihar-12,Patliputra,pc,1976,bihar,,12,,GEN",
            "IN-PC-2008-bihar-3001,Patliputra,pc,2008,bihar,,12,,GEN",
        ],
    )
    (entities / "parties.csv").write_text(
        "party_id,short,full,aliases,is_sentinel\n"
        "parties.IN.INC,INC,Indian National Congress,,\n"
        "parties.IN.UNK,UNK,Unresolved Party,,true\n",
        encoding="utf-8",
    )

    # DelimID 3 -> binds to 1976 PC cohort.
    emitted_3 = parliament_results.emit_parliament(
        ge_csv=ge,
        electoral_csv=entities / "electoral.csv",
        out_root=tmp_path,
        source_id=SOURCE_ID,
        delim_id="3",
        parties_csv=entities / "parties.csv",
    )
    assert set(emitted_3) == {1999}
    cand_3 = _read_csv(emitted_3[1999]["candidacies"])
    assert len(cand_3) == 2
    assert {r["entity_id"] for r in cand_3} == {"IN-PC-1976-bihar-12"}

    # DelimID 4 -> binds to 2008 PC cohort (overwrites the file, but that's
    # fine for this isolated test - production sequential delim runs DO
    # produce per-year files which are disjoint across delims).
    emitted_4 = parliament_results.emit_parliament(
        ge_csv=ge,
        electoral_csv=entities / "electoral.csv",
        out_root=tmp_path,
        source_id=SOURCE_ID,
        delim_id="4",
        parties_csv=entities / "parties.csv",
    )
    assert set(emitted_4) == {2009}
    cand_4 = _read_csv(emitted_4[2009]["candidacies"])
    assert len(cand_4) == 2
    assert {r["entity_id"] for r in cand_4} == {"IN-PC-2008-bihar-3001"}

    # The two delims wrote into distinct year files.
    assert (
        tmp_path / "datasets" / "elections" / "parliament"
        / "election=1999" / "candidacies.csv"
    ).is_file()
    assert (
        tmp_path / "datasets" / "elections" / "parliament"
        / "election=2009" / "candidacies.csv"
    ).is_file()


# --- Test 6: PR-Q7a mapping parity ------------------------------------------


def test_mint_pc_delim_id_mapping_parity():
    """Minter walks exactly the three historical DelimIDs declared by PR-Q7a."""
    assert HISTORICAL_DELIM_IDS == ("1", "2", "3")
    for delim_id in HISTORICAL_DELIM_IDS:
        assert delim_id in TCPD_DELIM_ID_TO_DELIM_YEAR
        assert TCPD_DELIM_ID_TO_DELIM_YEAR[delim_id] < 2008  # historical
    # DelimID 4 (the in-force cycle) is NOT in the minter's responsibility.
    assert "4" not in HISTORICAL_DELIM_IDS


# --- Test 7: deterministic sort of appended rows ----------------------------


def test_mint_pc_append_block_sorts_deterministically(tmp_path):
    """The appended block lands in (delim_year, state, eci_no) order.

    Re-runs over the same TCPD vintage produce byte-stable diffs.
    """
    ge = _write_ge(
        tmp_path / "ge.csv",
        [
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=20, Constituency_Name="Aurangabad"),
            _ge_row(State_Name="Bihar", DelimID=1, Year=1962,
                    Constituency_No=5, Constituency_Name="Patna"),
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=1, Constituency_Name="Patliputra"),
        ],
    )
    rows, _counts, _ties = build_entity_rows(ge)

    # The pure builder pre-sorts by (delim_year, state, eci_no); ascending.
    assert [r["entity_id"] for r in rows] == [
        "IN-PC-1962-bihar-5",
        "IN-PC-1976-bihar-1",
        "IN-PC-1976-bihar-20",
    ]

    electoral = _write_electoral(tmp_path / "electoral.csv")
    append_new_rows(electoral, rows)

    appended = electoral.read_text(encoding="utf-8").splitlines()
    # Header + 3 appended rows in the same deterministic order.
    # (Default _ge_row carries Constituency_Type=GEN -> reservation=GEN.)
    assert appended[1:] == [
        "IN-PC-1962-bihar-5,Patna,pc,1962,bihar,,5,,GEN",
        "IN-PC-1976-bihar-1,Patliputra,pc,1976,bihar,,1,,GEN",
        "IN-PC-1976-bihar-20,Aurangabad,pc,1976,bihar,,20,,GEN",
    ]


# --- Test 8: reservation honours most-recent valid Constituency_Type --------


def test_mint_pc_reservation_picks_most_recent_valid(tmp_path):
    """Most-recent valid TCPD Constituency_Type wins; BL / empty are skipped.

    Year 1989 says BL (skipped); year 1999 says SC. The minter picks SC.
    """
    ge = _write_ge(
        tmp_path / "ge.csv",
        [
            _ge_row(State_Name="Bihar", DelimID=3, Year=1989,
                    Constituency_No=4, Constituency_Name="Sasaram",
                    Constituency_Type="BL"),
            _ge_row(State_Name="Bihar", DelimID=3, Year=1999,
                    Constituency_No=4, Constituency_Name="Sasaram",
                    Constituency_Type="SC"),
        ],
    )
    rows, _counts, _ties = build_entity_rows(ge)
    assert len(rows) == 1
    assert rows[0]["reservation"] == "SC"
