"""PR-Q7b tests for the historical AC entity minter + the multi-delim fanout.

Pin the behaviour of
``backend/yen_gov/canonical/reingest/_run_historical_ac_entities.py`` plus the
multi-delim emit shape of ``assembly_results.emit_state_assembly``:

  (1) ``build_entity_rows`` mints rows of the correct shape (entity_id
      format, name selection, delim_year derivation).
  (2) ``append_new_rows`` is idempotent: rows whose ``entity_id`` is
      already on ``electoral.csv`` are skipped.
  (3) Defunct TCPD state names (``Madras`` / ``Mysore`` /
      ``Goa_Daman_&_Diu``) are dropped at the group-key boundary.
  (4) ``aliases`` collects every historical ``Constituency_Name`` variant
      pipe-joined, EXCLUDING the chosen ``name``.
  (5) Integration: a single ``ae.csv`` with both DelimID 3 (1985) + DelimID 4
      (2009) rows for the same (state, eci_no) emits to two distinct year
      directories, each bound to the correct delim cohort.

No real-corpus walk (CLAUDE.md anti-pattern). All fixtures synthetic
under ``tmp_path``.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from yen_gov.canonical.reingest import assembly_results
from yen_gov.canonical.reingest._run_historical_ac_entities import (
    HISTORICAL_DELIM_IDS,
    SKIP_STATES,
    append_new_rows,
    build_entity_rows,
)
from yen_gov.canonical.reingest.assembly_results import (
    TCPD_DELIM_ID_TO_DELIM_YEAR,
    emit_state_assembly,
)

SOURCE_ID = "src-tcpd-ae-q7b-test"

_AE_HEADER = [
    "State_Name", "Assembly_No", "Constituency_No", "Year", "DelimID",
    "Poll_No", "Position", "Candidate", "Sex", "Party", "Votes", "Age",
    "Deposit_Lost", "Valid_Votes", "Electors", "Constituency_Name",
    "Constituency_Type", "Turnout_Percentage", "Vote_Share_Percentage",
    "Incumbent", "Turncoat", "MyNeta_education", "TCPD_Prof_Main_Desc",
]


def _ae_row(**over) -> dict[str, str]:
    base = {
        "State_Name": "Bihar", "Assembly_No": "1", "Constituency_No": "1",
        "Year": "1980", "DelimID": "3", "Poll_No": "0", "Position": "1",
        "Candidate": "A", "Sex": "MALE", "Party": "INC", "Votes": "100",
        "Age": "50", "Deposit_Lost": "no", "Valid_Votes": "180",
        "Electors": "250", "Constituency_Name": "Bagaha",
        "Constituency_Type": "GEN", "Turnout_Percentage": "72.0",
        "Vote_Share_Percentage": "55.5", "Incumbent": "FALSE",
        "Turncoat": "FALSE", "MyNeta_education": "Graduate",
        "TCPD_Prof_Main_Desc": "Doctor",
    }
    base.update({k: str(v) for k, v in over.items()})
    return base


def _write_ae(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=_AE_HEADER, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in _AE_HEADER})
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


def test_mint_entities_correct_id_shape(tmp_path):
    """Verify entity_id, delim_year, state slug, eci_no, reservation derivation.

    Two source rows: one DelimID=3 (year 1985) for Bihar AC 12, one
    DelimID=1 (year 1962) for Bihar AC 7. Expectation: the minter emits
    two rows with ids ``IN-AC-1976-bihar-12`` + ``IN-AC-1962-bihar-7``,
    each carrying ``entity_kind=ac``, the matching delim_year, the
    slugified state, and the source's Constituency_Type as ``reservation``.
    """
    ae = _write_ae(
        tmp_path / "ae.csv",
        [
            _ae_row(
                State_Name="Bihar", DelimID=3, Year=1985, Constituency_No=12,
                Constituency_Name="Patna East", Constituency_Type="GEN",
            ),
            _ae_row(
                State_Name="Bihar", DelimID=1, Year=1962, Constituency_No=7,
                Constituency_Name="Gaya", Constituency_Type="SC",
            ),
        ],
    )

    rows, counts, ties = build_entity_rows(ae)

    assert ties == []
    assert sorted(r["entity_id"] for r in rows) == [
        "IN-AC-1962-bihar-7",
        "IN-AC-1976-bihar-12",
    ]
    by_id = {r["entity_id"]: r for r in rows}

    bagaha = by_id["IN-AC-1976-bihar-12"]
    assert bagaha["name"] == "Patna East"
    assert bagaha["entity_kind"] == "ac"
    assert bagaha["delim_year"] == "1976"
    assert bagaha["state"] == "bihar"
    assert bagaha["parent"] == ""
    assert bagaha["eci_no"] == "12"
    assert bagaha["reservation"] == "GEN"
    assert bagaha["aliases"] == ""

    gaya = by_id["IN-AC-1962-bihar-7"]
    assert gaya["delim_year"] == "1962"
    assert gaya["reservation"] == "SC"
    assert gaya["name"] == "Gaya"

    # Counts table matches.
    assert counts == {("bihar", "3"): 1, ("bihar", "1"): 1}


# --- Test 2: idempotency on existing entity_id -------------------------------


def test_mint_skips_existing(tmp_path):
    """A pre-existing row with the same derived entity_id is NOT duplicated.

    Stage ``electoral.csv`` with one historical row; the minter sees a
    matching TCPD group and emits the row in ``candidate_rows`` (the pure
    builder does not know about disk state); ``append_new_rows`` then
    skips it.
    """
    electoral = _write_electoral(
        tmp_path / "electoral.csv",
        ["IN-AC-1976-bihar-1,Patliputra,ac,1976,bihar,,1,,GEN"],
    )
    ae = _write_ae(
        tmp_path / "ae.csv",
        [_ae_row(State_Name="Bihar", DelimID=3, Year=1980, Constituency_No=1,
                 Constituency_Name="Patliputra", Constituency_Type="GEN")],
    )
    rows, _counts, _ties = build_entity_rows(ae)
    assert len(rows) == 1

    n_new, n_skipped = append_new_rows(electoral, rows)
    assert n_new == 0
    assert n_skipped == 1

    # File byte-identical (the existing row remains; no append).
    assert electoral.read_text(encoding="utf-8") == (
        "entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation\n"
        "IN-AC-1976-bihar-1,Patliputra,ac,1976,bihar,,1,,GEN\n"
    )


# --- Test 3: defunct state names are skipped ---------------------------------


def test_mint_skips_defunct_state(tmp_path):
    """``Madras`` / ``Mysore`` / ``Goa_Daman_&_Diu`` are dropped silently."""
    ae = _write_ae(
        tmp_path / "ae.csv",
        [
            _ae_row(State_Name="Madras", DelimID=1, Year=1962,
                    Constituency_No=1, Constituency_Name="Madras-1"),
            _ae_row(State_Name="Mysore", DelimID=2, Year=1967,
                    Constituency_No=2, Constituency_Name="Mysore-1"),
            _ae_row(State_Name="Goa_Daman_&_Diu", DelimID=3, Year=1980,
                    Constituency_No=3, Constituency_Name="Daman-1"),
            # Sanity row for a kept state so the minter has SOMETHING to emit.
            _ae_row(State_Name="Bihar", DelimID=3, Year=1980,
                    Constituency_No=4, Constituency_Name="Bihar-AC-4",
                    Constituency_Type="GEN"),
        ],
    )

    rows, counts, _ties = build_entity_rows(ae)

    # All three defunct-state rows dropped at group-key boundary.
    assert SKIP_STATES == frozenset({"Madras", "Mysore", "Goa_Daman_&_Diu"})
    assert [r["entity_id"] for r in rows] == ["IN-AC-1976-bihar-4"]
    assert counts == {("bihar", "3"): 1}


# --- Test 4: aliases collect every historical Constituency_Name variant -----


def test_mint_aliases_collect_name_variants(tmp_path):
    """Three TCPD rows with three name spellings -> aliases column has the rest.

    The most-recent (Year=1990) spelling wins as ``name``; the older
    variants (Year=1980, Year=1985) are collected into ``aliases``
    pipe-joined, deduped case-insensitively, sorted alphabetically.
    Case-difference variants of the chosen name are EXCLUDED from
    aliases (so the alias never duplicates ``name``).
    """
    ae = _write_ae(
        tmp_path / "ae.csv",
        [
            _ae_row(State_Name="Bihar", DelimID=3, Year=1980,
                    Constituency_No=12, Constituency_Name="Patna-East"),
            _ae_row(State_Name="Bihar", DelimID=3, Year=1985,
                    Constituency_No=12, Constituency_Name="PATNA-EAST"),
            _ae_row(State_Name="Bihar", DelimID=3, Year=1990,
                    Constituency_No=12, Constituency_Name="Patna East"),
        ],
    )
    rows, _counts, ties = build_entity_rows(ae)
    assert len(rows) == 1
    row = rows[0]

    assert row["name"] == "Patna East"  # the Year=1990 spelling wins
    # Aliases: deduped case-insensitively (Patna-East + PATNA-EAST collapse
    # to one entry); the chosen-name's case-variants are excluded.
    assert row["aliases"] == "Patna-East"
    assert ties == []


def test_mint_records_naming_mode_ties(tmp_path):
    """When the most-recent year has a mode-tie, the receipt records the row.

    Year 1990 carries two names with the same count: ``Aurangabad`` and
    ``Aurangbad``. Alphabetical order wins -> ``Aurangabad`` becomes the
    canonical name; the tie is logged. Older-year variants still flow into
    aliases.
    """
    ae = _write_ae(
        tmp_path / "ae.csv",
        [
            _ae_row(State_Name="Bihar", DelimID=3, Year=1980, Position=1,
                    Constituency_No=20, Constituency_Name="Aurangabad-1980"),
            _ae_row(State_Name="Bihar", DelimID=3, Year=1990, Position=1,
                    Constituency_No=20, Constituency_Name="Aurangabad"),
            _ae_row(State_Name="Bihar", DelimID=3, Year=1990, Position=2,
                    Constituency_No=20, Constituency_Name="Aurangbad"),
        ],
    )
    rows, _counts, ties = build_entity_rows(ae)
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Aurangabad"  # alphabetical break on mode tie
    assert ties == [("bihar", "3", 20, "Aurangabad")]
    # Both alternative names land in aliases (deduped, sorted).
    assert row["aliases"] == "Aurangabad-1980|Aurangbad"


# --- Test 5: fanout binds per-delim against the matching entity cohort ------


def test_fanout_emits_per_delim_against_correct_cohort(tmp_path):
    """Two AE rows (DelimID 3 year 1985 + DelimID 4 year 2009) for the same
    state + eci_no bind to two distinct cohorts when both entity rows exist.

    The driver-side multi-delim fanout calls ``emit_state_assembly`` once
    per delim. This test exercises the binder directly twice to mirror that
    shape (no temporal coupling between the calls). Both writes succeed
    against their corresponding entities and land in distinct year dirs.
    """
    ae = _write_ae(
        tmp_path / "datasets" / "ephemeral" / "All_States_AE.csv",
        [
            # DelimID 3, year 1985 -- binds against the 1976 cohort.
            _ae_row(State_Name="Bihar", DelimID=3, Year=1985,
                    Constituency_No=12, Position=1, Candidate="W",
                    Party="INC", Votes=100, Vote_Share_Percentage=55.5,
                    Deposit_Lost="no"),
            _ae_row(State_Name="Bihar", DelimID=3, Year=1985,
                    Constituency_No=12, Position=2, Candidate="R",
                    Party="INC", Votes=80, Vote_Share_Percentage=44.5,
                    Deposit_Lost="no"),
            # DelimID 4, year 2009 -- binds against the 2008 cohort.
            _ae_row(State_Name="Bihar", DelimID=4, Year=2009,
                    Constituency_No=12, Position=1, Candidate="W",
                    Party="INC", Votes=100, Vote_Share_Percentage=55.5,
                    Deposit_Lost="no"),
            _ae_row(State_Name="Bihar", DelimID=4, Year=2009,
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
            "IN-AC-1976-bihar-12,Bagaha,ac,1976,bihar,,12,,GEN",
            "IN-AC-2008-bihar-3001,Bagaha,ac,2008,bihar,,12,,GEN",
        ],
    )
    (entities / "parties.csv").write_text(
        "party_id,short,full,aliases,is_sentinel\n"
        "parties.IN.INC,INC,Indian National Congress,,\n"
        "parties.IN.UNK,UNK,Unresolved Party,,true\n",
        encoding="utf-8",
    )

    # DelimID 3 -> binds to 1976 cohort.
    emitted_3 = emit_state_assembly(
        ae_csv=ae,
        electoral_csv=entities / "electoral.csv",
        out_root=tmp_path,
        state_name_tcpd="Bihar",
        state_slug="bihar",
        source_id=SOURCE_ID,
        parties_csv=entities / "parties.csv",
        delim_id="3",
    )
    assert set(emitted_3) == {1985}
    cand_3 = _read_csv(emitted_3[1985]["candidacies"])
    assert len(cand_3) == 2
    assert {r["entity_id"] for r in cand_3} == {"IN-AC-1976-bihar-12"}

    # DelimID 4 -> binds to 2008 cohort.
    emitted_4 = emit_state_assembly(
        ae_csv=ae,
        electoral_csv=entities / "electoral.csv",
        out_root=tmp_path,
        state_name_tcpd="Bihar",
        state_slug="bihar",
        source_id=SOURCE_ID,
        parties_csv=entities / "parties.csv",
        delim_id="4",
    )
    assert set(emitted_4) == {2009}
    cand_4 = _read_csv(emitted_4[2009]["candidacies"])
    assert len(cand_4) == 2
    assert {r["entity_id"] for r in cand_4} == {"IN-AC-2008-bihar-3001"}

    # The two delims wrote into distinct year directories.
    assert (
        tmp_path / "datasets" / "elections" / "assembly"
        / "state=bihar" / "election=1985" / "candidacies.csv"
    ).is_file()
    assert (
        tmp_path / "datasets" / "elections" / "assembly"
        / "state=bihar" / "election=2009" / "candidacies.csv"
    ).is_file()


# --- Public-surface sanity --------------------------------------------------


def test_historical_delim_ids_matches_mapping():
    """Minter walks exactly the three historical DelimIDs declared by PR-Q7a."""
    assert HISTORICAL_DELIM_IDS == ("1", "2", "3")
    for delim_id in HISTORICAL_DELIM_IDS:
        assert delim_id in TCPD_DELIM_ID_TO_DELIM_YEAR
        assert TCPD_DELIM_ID_TO_DELIM_YEAR[delim_id] < 2008  # historical
    # DelimID 4 (the in-force cycle) is NOT in the minter's responsibility.
    assert "4" not in HISTORICAL_DELIM_IDS


def test_append_new_rows_sorts_block_deterministically(tmp_path):
    """The appended block lands in (delim_year, state, eci_no) order.

    Re-runs over the same TCPD vintage produce byte-stable diffs.
    """
    ae = _write_ae(
        tmp_path / "ae.csv",
        [
            _ae_row(State_Name="Bihar", DelimID=3, Year=1980,
                    Constituency_No=20, Constituency_Name="Aurangabad"),
            _ae_row(State_Name="Bihar", DelimID=1, Year=1962,
                    Constituency_No=5, Constituency_Name="Patna"),
            _ae_row(State_Name="Bihar", DelimID=3, Year=1980,
                    Constituency_No=1, Constituency_Name="Bagaha"),
        ],
    )
    rows, _counts, _ties = build_entity_rows(ae)

    # The pure builder pre-sorts by (delim_year, state, eci_no); ascending.
    assert [r["entity_id"] for r in rows] == [
        "IN-AC-1962-bihar-5",
        "IN-AC-1976-bihar-1",
        "IN-AC-1976-bihar-20",
    ]

    electoral = _write_electoral(tmp_path / "electoral.csv")
    append_new_rows(electoral, rows)

    appended = electoral.read_text(encoding="utf-8").splitlines()
    # Header + 3 appended rows in the same deterministic order.
    # (Default _ae_row carries Constituency_Type=GEN -> reservation=GEN.)
    assert appended[1:] == [
        "IN-AC-1962-bihar-5,Patna,ac,1962,bihar,,5,,GEN",
        "IN-AC-1976-bihar-1,Bagaha,ac,1976,bihar,,1,,GEN",
        "IN-AC-1976-bihar-20,Aurangabad,ac,1976,bihar,,20,,GEN",
    ]
