"""Tests for the G16 ECI LS2024 emitter.

No real-corpus walk: each test stages a synthetic ECI-shaped raw slice + a
minimal electoral (PC) / parties / source catalogue under ``tmp_path`` and
asserts the emitted parliament candidacies / summary CSVs against the real
``columns.json`` contract + the parity invariant
``summary == recompute(candidacies)``. The ECI-raw-specific surface (3-line
banner header, embedded LF in the "polled in the constituency" column key,
candidate-share columns NOT being PC turnout, the single-step PC bind that
sidesteps the ``eci_no == 0`` collision, FEMALE/MALE -> F/M, NOTA exclusion,
and the disclaimer-row trailer filter) is exercised here; the shared mapping
helpers (`_sex`, `_int_or_none`, `recompute_summary_row`) are covered by
``test_assembly_results`` + ``test_parliament_results``.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.reingest import parliament_2024_eci
from yen_gov.canonical.reingest.assembly_results import recompute_summary_row
from yen_gov.canonical.reingest.elections import (
    PARLIAMENT_CANDIDACIES_FC,
    PARLIAMENT_SUMMARY_FC,
)

SOURCE_ID = "src-eci-ls2024-test"

# Mirrors the real ECI Statement 33 header (including the embedded LF in the
# "polled in the constituency" column and the trailing empty columns from the
# raw file).
_ECI_HEADER = [
    "State Name",
    "PC Name",
    "Candidate Name",
    "Gender",
    "Age",
    "Category",
    "Party Name",
    "Party Symbol",
    "Total Votes Polled In\nThe Constituency",
    "Valid Votes",
    "General",
    "Postal",
    "Total",
    "Over Total Electors In Constituency",
    "Over Total Votes Polled In Constituency",
    "Over Total Valid Votes Polled In Constituency",
    "Total Electors",
]


def _eci_row(**over) -> dict[str, str]:
    """Build one ECI-raw-shaped row with sane defaults; override per test."""
    base = {
        "State Name": "Tamil Nadu",
        "PC Name": "Chennai North",
        "Candidate Name": "A",
        "Gender": "MALE",
        "Age": "50",
        "Category": "GEN",
        "Party Name": "DMK",
        "Party Symbol": "Sun",
        "Total Votes Polled In\nThe Constituency": "200",
        "Valid Votes": "180",
        "General": "95",
        "Postal": "5",
        "Total": "100",
        "Over Total Electors In Constituency": "40.0",
        "Over Total Votes Polled In Constituency": "50.0",
        "Over Total Valid Votes Polled In Constituency": "55.5",
        "Total Electors": "250",
    }
    base.update({k: str(v) for k, v in over.items()})
    return base


def _write_eci(path: Path, rows: list[dict[str, str]]) -> Path:
    """Write a synthetic ECI raw CSV with the 2-line banner + real header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    # Two banner rows (mirrors the real file's first two lines).
    buf.write("33 - CONSTITUENCY WISE DETAILED RESULT" + "," * 19 + "\n")
    buf.write("," * 10 + "Votes Secured,,,% of Votes Secured,,,,," + "\n")
    writer = csv.DictWriter(buf, fieldnames=_ECI_HEADER, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in _ECI_HEADER})
    path.write_text(buf.getvalue(), encoding="utf-8", newline="")
    return path


def _stage_catalogue(
    root: Path, pcs: list[tuple[str, str, int]]
) -> Path:
    """Stage electoral.csv (PC rows) + parties.csv + source.csv under tmp_path.

    ``pcs`` is ``[(state_slug, pc_name, eci_no), ...]`` - eci_no may be 0 to
    exercise the single-step lookup that sidesteps the eci_no=0 collision.
    """
    entities = root / "datasets" / "data" / "entities"
    entities.mkdir(parents=True, exist_ok=True)
    lines = [
        "entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation"
    ]
    for state_slug, pc_name, eci_no in pcs:
        eid = f"IN-PC-2008-{state_slug}-{2000 + len(lines)}"
        lines.append(
            f"{eid},{pc_name},pc,2008,{state_slug},,{eci_no},,GEN"
        )
    (entities / "electoral.csv").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    (entities / "parties.csv").write_text(
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia\n"
        "parties.IN.DMK,DMK,Dravida Munnetra Kazhagam,,,,\n"
        "parties.IN.BJP,BJP,Bharatiya Janata Party,,,,\n",
        encoding="utf-8",
    )
    (entities / "source.csv").write_text(
        "source_id,owner,title,vintage,url\n"
        f"{SOURCE_ID},Election Commission of India,LS 2024,2024,\n",
        encoding="utf-8",
    )
    return entities / "electoral.csv"


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _three_way_contest(state_name: str, pc_name: str) -> list[dict[str, str]]:
    """Three real candidates + NOTA for one PC."""
    return [
        _eci_row(
            **{
                "State Name": state_name,
                "PC Name": pc_name,
                "Candidate Name": "W-Winner",
                "Gender": "FEMALE",
                "Party Name": "DMK",
                "Total": "120",
                "Over Total Valid Votes Polled In Constituency": "60.0",
                "Total Votes Polled In\nThe Constituency": "200",
                "Valid Votes": "200",
                "Total Electors": "250",
            }
        ),
        _eci_row(
            **{
                "State Name": state_name,
                "PC Name": pc_name,
                "Candidate Name": "R-Runner",
                "Gender": "MALE",
                "Party Name": "BJP",
                "Total": "70",
                "Over Total Valid Votes Polled In Constituency": "35.0",
                "Total Votes Polled In\nThe Constituency": "200",
                "Valid Votes": "200",
                "Total Electors": "250",
            }
        ),
        _eci_row(
            **{
                "State Name": state_name,
                "PC Name": pc_name,
                "Candidate Name": "T-Third",
                "Gender": "MALE",
                "Party Name": "IND",
                "Total": "10",
                "Over Total Valid Votes Polled In Constituency": "5.0",
                "Total Votes Polled In\nThe Constituency": "200",
                "Valid Votes": "200",
                "Total Electors": "250",
            }
        ),
        _eci_row(
            **{
                "State Name": state_name,
                "PC Name": pc_name,
                "Candidate Name": "NOTA",
                "Gender": "",
                "Age": "",
                "Category": "",
                "Party Name": "NOTA",
                "Party Symbol": "NOTA",
                "Total": "5",
                "Over Total Valid Votes Polled In Constituency": "2.5",
                "Total Votes Polled In\nThe Constituency": "200",
                "Valid Votes": "200",
                "Total Electors": "250",
            }
        ),
    ]


def _emit(root: Path, rows, pcs):
    eci_csv = _write_eci(
        root
        / "datasets"
        / "ephemeral"
        / "2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv",
        rows,
    )
    electoral = _stage_catalogue(root, pcs)
    parties = root / "datasets" / "data" / "entities" / "parties.csv"
    return parliament_2024_eci.emit_parliament_2024(
        eci_csv=eci_csv,
        electoral_csv=electoral,
        out_root=root,
        source_id=SOURCE_ID,
        parties_csv=parties,
    )


# --- Test 1: country-wide emit + parity + validator + state mandatory -------


def test_emit_country_wide_with_two_states_and_pcs(tmp_path: Path) -> None:
    rows = _three_way_contest("Tamil Nadu", "Chennai North") + _three_way_contest(
        "Kerala", "Thiruvananthapuram"
    )
    info = _emit(
        tmp_path,
        rows,
        [("tamil-nadu", "Chennai North", 1), ("kerala", "Thiruvananthapuram", 1)],
    )
    rel = info["candidacies"].relative_to(tmp_path).as_posix()
    assert rel == "datasets/elections/parliament/election=2024/candidacies.csv"
    assert info["states"] == 2
    assert info["n_summary"] == 2
    assert info["n_candidacies"] == 6  # 3 real candidates per PC; NOTA excluded.
    validate_csv(
        path=info["candidacies"],
        file_class=PARLIAMENT_CANDIDACIES_FC,
        repo_root=tmp_path,
    )
    validate_csv(
        path=info["summary"], file_class=PARLIAMENT_SUMMARY_FC, repo_root=tmp_path
    )
    cand = _read(info["candidacies"])
    assert {r["state"] for r in cand} == {"tamil-nadu", "kerala"}


# --- Test 2: NOTA excluded --------------------------------------------------


def test_nota_excluded_from_candidacies(tmp_path: Path) -> None:
    info = _emit(
        tmp_path,
        _three_way_contest("Tamil Nadu", "Chennai North"),
        [("tamil-nadu", "Chennai North", 1)],
    )
    cand = _read(info["candidacies"])
    names = {r["candidate_name"] for r in cand}
    assert "NOTA" not in names
    assert names == {"W-Winner", "R-Runner", "T-Third"}


# --- Test 3: position assigned by votes desc; winner has position=1 ---------


def test_position_assigned_by_votes_desc(tmp_path: Path) -> None:
    info = _emit(
        tmp_path,
        _three_way_contest("Tamil Nadu", "Chennai North"),
        [("tamil-nadu", "Chennai North", 1)],
    )
    cand = _read(info["candidacies"])
    by_name = {r["candidate_name"]: r for r in cand}
    assert by_name["W-Winner"]["position"] == "1"
    assert by_name["W-Winner"]["result"] == "won"
    assert by_name["R-Runner"]["position"] == "2"
    assert by_name["R-Runner"]["result"] == "lost"
    assert by_name["T-Third"]["position"] == "3"
    assert by_name["T-Third"]["result"] == "lost"


# --- Test 4: summary == recompute(candidacies) ------------------------------


def test_summary_equals_recompute_of_candidacies(tmp_path: Path) -> None:
    info = _emit(
        tmp_path,
        _three_way_contest("Tamil Nadu", "Chennai North"),
        [("tamil-nadu", "Chennai North", 1)],
    )
    cand = _read(info["candidacies"])
    summ = _read(info["summary"])
    assert len(summ) == 1
    s = summ[0]
    # Re-derive a summary row from the just-emitted candidacy rows + the PC
    # facts that the writer would have computed (turnout = polled/electors).
    # Note: CSV round-trip leaves all values as strings; coerce as needed.
    cand_dicts = [
        {
            **r,
            "votes": int(r["votes"]),
            "vote_share_pct": float(r["vote_share_pct"]) if r["vote_share_pct"] else None,
        }
        for r in cand
    ]
    recomputed = recompute_summary_row(
        entity_id=s["entity_id"],
        state_slug=s["state"],
        election_year=2024,
        candidacy_rows=cand_dicts,
        ac_facts={
            "electors": int(s["electors"]),
            "votes_polled": int(s["votes_polled"]),
            "turnout_pct": float(s["turnout_pct"]),
        },
        source_id=SOURCE_ID,
    )
    assert recomputed["winner_candidate"] == s["winner_candidate"]
    assert recomputed["winner_votes"] == int(s["winner_votes"])
    assert recomputed["runnerup_candidate"] == s["runnerup_candidate"]
    assert recomputed["margin_votes"] == int(s["margin_votes"])
    assert recomputed["turnout_pct"] == float(s["turnout_pct"])


# --- Test 5: unknown PC -> unbound, not emitted -----------------------------


def test_unknown_pc_lands_in_unbound(tmp_path: Path) -> None:
    rows = _three_way_contest("Tamil Nadu", "Chennai North") + _three_way_contest(
        "NCT OF Delhi", "New Delhi"
    )
    # Tamil Nadu PC is in the spine; Delhi PC is NOT (standing electoral.csv
    # gap that the LS2024 ingest surfaces).
    info = _emit(tmp_path, rows, [("tamil-nadu", "Chennai North", 1)])
    cand = _read(info["candidacies"])
    assert {r["state"] for r in cand} == {"tamil-nadu"}
    assert ("delhi", "New Delhi") in info["unbound"]
    # Delhi did NOT silently bind to the Tamil Nadu entity.
    assert all(r["entity_id"].startswith("IN-PC-2008-tamil-nadu-") for r in cand)


# --- Test 6: gender FEMALE/MALE -> F/M (with empty -> U for safety) ---------


def test_gender_female_male_to_single_letter(tmp_path: Path) -> None:
    info = _emit(
        tmp_path,
        _three_way_contest("Tamil Nadu", "Chennai North"),
        [("tamil-nadu", "Chennai North", 1)],
    )
    cand = _read(info["candidacies"])
    by_name = {r["candidate_name"]: r for r in cand}
    assert by_name["W-Winner"]["sex"] == "F"  # FEMALE -> F
    assert by_name["R-Runner"]["sex"] == "M"  # MALE -> M
    assert by_name["T-Third"]["sex"] == "M"  # MALE -> M


# --- Bonus: single-step bind sidesteps the eci_no=0 collision ---------------


def test_single_step_bind_handles_eci_no_zero_collision(tmp_path: Path) -> None:
    """Three Andhra Pradesh PCs all with eci_no=0 in the spine MUST stay
    distinct in the emit. Two-step (state, pc_name) -> eci_no -> entity_id
    would collide all three onto whichever entity has eci_no=0 first; the
    single-step (state_slug, pc_name) -> (entity_id, eci_no) lookup keeps
    them separate.
    """
    rows = (
        _three_way_contest("Andhra Pradesh", "Araku")
        + _three_way_contest("Andhra Pradesh", "Kadapa")
        + _three_way_contest("Andhra Pradesh", "Vizianagaram")
    )
    info = _emit(
        tmp_path,
        rows,
        [
            ("andhra-pradesh", "Araku", 0),
            ("andhra-pradesh", "Kadapa", 0),
            ("andhra-pradesh", "Vizianagaram", 0),
        ],
    )
    cand = _read(info["candidacies"])
    entity_ids = {r["entity_id"] for r in cand}
    assert len(entity_ids) == 3, (
        "three eci_no=0 PCs must bind to three distinct entity_ids; "
        f"got {entity_ids}"
    )
    # All carry constituency_no=0 (spine's verbatim value).
    assert {r["constituency_no"] for r in cand} == {"0"}


# --- Bonus: disclaimer-row trailer filtered out -----------------------------


def test_disclaimer_trailer_rows_filtered(tmp_path: Path) -> None:
    """ECI raw has 3 trailing disclaimer rows where the long disclaimer text
    is stuffed into ``State Name`` and ``PC Name`` is empty. Those rows must
    not land in ``unbound`` or ``candidacies``.
    """
    disclaimer_row = _eci_row(
        **{
            "State Name": "Disclaimer",
            "PC Name": "",
            "Candidate Name": "",
            "Party Name": "",
        }
    )
    rows = _three_way_contest("Tamil Nadu", "Chennai North") + [disclaimer_row]
    info = _emit(tmp_path, rows, [("tamil-nadu", "Chennai North", 1)])
    assert info["n_candidacies"] == 3
    # No spurious unbound entry from the disclaimer row.
    assert info["unbound"] == []
