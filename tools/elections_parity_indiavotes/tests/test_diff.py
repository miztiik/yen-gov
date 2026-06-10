"""Unit tests for the diff engine + scraper parser.

Pure-function tests against synthetic fixtures. NO live IndiaVotes traffic;
NO yen-gov backend imports. Runnable from a clean parity-only venv:

    pip install httpx beautifulsoup4 lxml pytest
    pytest tools/elections_parity_indiavotes/tests/test_diff.py

These tests ARE the G1-EVIDENCE oracle when IndiaVotes is unreachable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The tool ships as a script (no package install). Make its modules
# importable by prepending the package dir to sys.path BEFORE the imports.
_TOOL_ROOT = Path(__file__).resolve().parent.parent
if str(_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(_TOOL_ROOT))

from diff import (  # noqa: E402
    agreement_pct,
    compute_diff,
    normalise_name,
    normalise_party,
    read_yengov_winners,
)
from scrape import parse_winners, resolve_target  # noqa: E402


FIXTURES = Path(__file__).resolve().parent / "fixtures"
IV_HTML = FIXTURES / "indiavotes-chhattisgarh-general-2024.html"
YENGOV_PERFECT = FIXTURES / "yengov-chhattisgarh-perfect-match.csv"
YENGOV_MISMATCH = FIXTURES / "yengov-chhattisgarh-with-mismatches.csv"


# --- normaliser tests -------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("parties.IN.BJP", "bjp"),
        ("BJP", "bjp"),
        ("inc", "inc"),
        ("", ""),
        ("Parties.in.bjp", "bjp"),
        ("parties.IN.BSP+", "bsp"),
    ],
)
def test_normalise_party_strips_namespace_and_case(raw, expected):
    assert normalise_party(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Raipur", "raipur"),
        ("  raipur  ", "raipur"),
        ("Bilas-Pur", "bilaspur"),
        ("KORBA (SC)", "korbasc"),
    ],
)
def test_normalise_name_lowercases_and_strips_punctuation(raw, expected):
    assert normalise_name(raw) == expected


# --- scrape.parse_winners ---------------------------------------------------


def test_parse_winners_extracts_three_rows_from_synthetic_fixture():
    rows = parse_winners([IV_HTML])
    assert len(rows) == 3
    by_name = {r["constituency_name"]: r for r in rows}
    assert set(by_name) == {"Raipur", "Bilaspur", "Korba"}
    raipur = by_name["Raipur"]
    assert raipur["winner_name"] == "BRIJMOHAN AGRAWAL"
    assert raipur["winner_party"] == "BJP"
    # IV publishes vote SHARE (% age) and margin-pct, not raw counts; the
    # parser deliberately drops them to None so the operator does not get
    # bogus integers in the comparison CSV.
    assert raipur["votes"] is None
    assert raipur["margin"] is None


def test_parse_winners_strips_reservation_suffix_from_constituency():
    """IndiaVotes ships 'BastarST' / 'KorbaSC' / 'Janjgir-ChampaSC'; the
    parser strips the trailing SC/ST/SC-ST so the constituency join key
    matches yen-gov's separate reservation column."""

    tmp = FIXTURES / "_reservation.html"
    try:
        tmp.write_text(
            "<html><body><table>"
            "<thead><tr><th>Constituency</th><th>Winner</th></tr></thead>"
            "<tbody>"
            "<tr><td>BastarST</td><td>MAHESH KASHYAP(BJP)</td></tr>"
            "<tr><td>Janjgir-ChampaSC</td><td>KAMLESH JANGDE(BJP)</td></tr>"
            "</tbody></table></body></html>",
            encoding="utf-8",
        )
        rows = parse_winners([tmp])
        names = {r["constituency_name"] for r in rows}
        assert names == {"Bastar", "Janjgir-Champa"}
    finally:
        tmp.unlink(missing_ok=True)


def test_parse_winners_returns_empty_for_no_table():
    """A page with no <table> at all degrades to zero rows, not a crash."""

    tmp = FIXTURES / "_no-table.html"
    try:
        tmp.write_text("<html><body><p>no results yet</p></body></html>", encoding="utf-8")
        assert parse_winners([tmp]) == []
    finally:
        tmp.unlink(missing_ok=True)


# --- scrape.resolve_target --------------------------------------------------


def test_resolve_target_general_uses_lok_sabha_template(tmp_path):
    target = resolve_target("general-2024", "chhattisgarh", cache_root=tmp_path)
    assert target.url == "https://www.indiavotes.com/lok-sabha/2024/chhattisgarh"
    assert target.event_slug == "general-2024"
    assert target.state_slug == "chhattisgarh"
    # cache_path has today's date in it; we don't pin the date string here
    # to keep the test stable across time zones, but it MUST end with the
    # expected suffix.
    assert target.cache_path.parts[-3:] == ("general-2024", "chhattisgarh", "page-1.html")


def test_resolve_target_assembly_uses_vidhan_sabha_template(tmp_path):
    target = resolve_target("assembly-2023", "chhattisgarh", cache_root=tmp_path)
    assert target.url == "https://www.indiavotes.com/vidhan-sabha/chhattisgarh/2023"


def test_resolve_target_rejects_bye_slug(tmp_path):
    with pytest.raises(ValueError, match="non-bye"):
        resolve_target(
            "general-bye-2024-bihar-bastar",
            "bihar",
            cache_root=tmp_path,
        )


# --- diff.read_yengov_winners ----------------------------------------------


def test_read_yengov_winners_reads_canonical_summary_csv_shape():
    """The new surface (PR-W1c fix-up, 2026-06-10) is
    ``datasets/elections/{parliament,assembly}/.../summary.csv``; this test
    pins the row shape returned by the reader."""

    rows = read_yengov_winners(YENGOV_PERFECT, "general-2024", "chhattisgarh")
    assert len(rows) == 3
    by_name = {r["constituency_name"]: r for r in rows}
    assert set(by_name) == {"RAIPUR", "BILASPUR", "KORBA"}
    raipur = by_name["RAIPUR"]
    assert raipur["entity_id"] == "IN-PC-2008-chhattisgarh-302"
    assert raipur["state_slug"] == "chhattisgarh"
    assert raipur["winner_party_id"] == "parties.IN.BJP"
    assert raipur["winner_party_short"] == "BJP"
    assert raipur["winner_candidate"] == "BRIJMOHAN AGRAWAL"
    assert raipur["winner_votes"] == 1_050_351
    assert raipur["winner_share_pct"] == pytest.approx(66.38)
    assert raipur["margin_votes"] == 575_285
    assert raipur["margin_pct"] == pytest.approx(36.36)
    assert raipur["runnerup_candidate"] == "VIKAS UPADHYAY"
    assert raipur["runnerup_party_id"] == "parties.IN.INC"
    assert raipur["runnerup_party_short"] == "INC"


def test_read_yengov_winners_returns_empty_when_summary_csv_missing(tmp_path):
    """Missing summary.csv signals an upstream data gap, not a function bug."""

    missing = tmp_path / "never-existed" / "summary.csv"
    assert read_yengov_winners(missing, "general-2024", "chhattisgarh") == []


def test_read_yengov_winners_general_filters_to_state(tmp_path):
    """Parliament summary.csv is national-scope on disk; the reader
    filters rows to ``state == state_slug`` for general events so a
    Chhattisgarh probe does not pick up Madhya Pradesh rows."""

    csv_path = tmp_path / "summary.csv"
    csv_path.write_text(
        "entity_id,state,election_year,constituency_name,electors,votes_polled,"
        "turnout_pct,winner_candidate,winner_party_id,winner_party_short_raw,"
        "winner_votes,winner_share_pct,runnerup_candidate,runnerup_party_id,"
        "runnerup_party_short_raw,runnerup_votes,margin_votes,margin_pct,source_id\n"
        "IN-PC-2008-chhattisgarh-302,chhattisgarh,2024,RAIPUR,100,80,80.0,"
        "WINNER A,parties.IN.BJP,BJP,50,62.5,LOSER A,parties.IN.INC,INC,30,20,25.0,src-x\n"
        "IN-PC-2008-chhattisgarh-295,chhattisgarh,2024,BILASPUR,200,160,80.0,"
        "WINNER B,parties.IN.BJP,BJP,90,56.25,LOSER B,parties.IN.INC,INC,70,20,12.5,src-x\n"
        "IN-PC-2008-madhya-pradesh-201,madhya-pradesh,2024,BHOPAL,300,240,80.0,"
        "WINNER C,parties.IN.BJP,BJP,140,58.33,LOSER C,parties.IN.INC,INC,100,40,16.66,src-x\n"
        "IN-PC-2008-madhya-pradesh-205,madhya-pradesh,2024,INDORE,400,320,80.0,"
        "WINNER D,parties.IN.BJP,BJP,200,62.5,LOSER D,parties.IN.INC,INC,120,80,25.0,src-x\n",
        encoding="utf-8",
    )
    rows = read_yengov_winners(csv_path, "general-2024", "chhattisgarh")
    assert len(rows) == 2
    assert {r["constituency_name"] for r in rows} == {"RAIPUR", "BILASPUR"}
    assert all(r["state_slug"] == "chhattisgarh" for r in rows)


def test_read_yengov_winners_assembly_does_not_filter_by_state(tmp_path):
    """Assembly summary.csv is per-state on disk (path partition pins state);
    the reader returns every row without an inline state filter."""

    csv_path = tmp_path / "summary.csv"
    csv_path.write_text(
        "entity_id,state,election_year,constituency_name,electors,votes_polled,"
        "turnout_pct,winner_candidate,winner_party_id,winner_party_short_raw,"
        "winner_votes,winner_share_pct,runnerup_candidate,runnerup_party_id,"
        "runnerup_party_short_raw,runnerup_votes,margin_votes,margin_pct,source_id\n"
        "IN-AC-2008-tamil-nadu-3857,tamil-nadu,2026,ARAKKONAM,100,80,80.0,"
        "WIN A,parties.IN.DMK,DMK,50,62.5,LOSE A,parties.IN.AIADMK,AIADMK,30,20,25.0,src-x\n"
        "IN-AC-2008-tamil-nadu-3858,tamil-nadu,2026,SHOLINGUR,200,160,80.0,"
        "WIN B,parties.IN.DMK,DMK,90,56.25,LOSE B,parties.IN.AIADMK,AIADMK,70,20,12.5,src-x\n",
        encoding="utf-8",
    )
    rows = read_yengov_winners(csv_path, "assembly-2026", "tamil-nadu")
    assert len(rows) == 2


# --- compute_diff -- the G1-EVIDENCE oracle ---------------------------------


def test_compute_diff_zero_deltas_on_perfect_match():
    """SYNTHETIC ORACLE 1: perfect match -> 0 disagreements, 100% agreement."""

    iv = parse_winners([IV_HTML])
    yg = read_yengov_winners(YENGOV_PERFECT, "general-2024", "chhattisgarh")
    rows = compute_diff(
        iv,
        yg,
        state_slug="chhattisgarh",
        event_slug="general-2024",
    )
    # 3 constituencies x 2 rows (one per source) = 6 rows.
    assert len(rows) == 6
    assert all(r["agrees"] == "true" for r in rows)
    assert all(r["delta_notes"] == "" for r in rows)
    assert agreement_pct(rows) == pytest.approx(100.0)


def test_compute_diff_identifies_mismatches():
    """SYNTHETIC ORACLE 2: 2 of 3 seats disagree -> exactly 2 mismatches surfaced."""

    iv = parse_winners([IV_HTML])  # BJP, BJP, INC for Raipur/Bilaspur/Korba
    yg = read_yengov_winners(YENGOV_MISMATCH, "general-2024", "chhattisgarh")
    rows = compute_diff(
        iv,
        yg,
        state_slug="chhattisgarh",
        event_slug="general-2024",
    )
    # Still 6 rows (3 seats x 2 sources). Find the per-constituency verdict.
    by_constituency: dict[str, bool] = {}
    for r in rows:
        by_constituency[r["constituency_name"]] = (
            by_constituency.get(r["constituency_name"], True) and r["agrees"] == "true"
        )
    # Raipur: BJP vs INC -> mismatch. Bilaspur: BJP vs BJP -> agree. Korba: INC vs BSP -> mismatch.
    assert by_constituency == {"RAIPUR": False, "BILASPUR": True, "KORBA": False}
    assert agreement_pct(rows) == pytest.approx(100.0 / 3, abs=0.01)


def test_compute_diff_surfaces_unmatched_constituencies():
    """A constituency present on only one side emits a 'no <other> match' row."""

    iv = [
        {
            "constituency_name": "Mahasamund",
            "winner_name": "Roopkumari Choudhary",
            "winner_party": "BJP",
            "votes": 700_000,
            "margin": 145_000,
        }
    ]
    yg = []  # yen-gov reports nothing for this seat
    rows = compute_diff(
        iv,
        yg,
        state_slug="chhattisgarh",
        event_slug="general-2024",
    )
    assert len(rows) == 1
    assert rows[0]["source"] == "indiavotes"
    assert rows[0]["agrees"] == "false"
    assert rows[0]["delta_notes"] == "no yen-gov match"


def test_compute_diff_byte_equal_join_on_summary_csv_shape(tmp_path):
    """End-to-end synthetic oracle: 3-row IndiaVotes fixture + 3-row yen-gov
    summary fixture where 2 winners agree on party_id and 1 disagrees. The
    delta CSV must report exactly 2 agreements + 1 disagreement."""

    iv = [
        {
            "constituency_name": "BASTAR",
            "winner_name": "MAHESH KASHYAP",
            "winner_party": "BJP",
            "votes": None,
            "margin": None,
        },
        {
            "constituency_name": "BILASPUR",
            "winner_name": "TOKHAN SAHU",
            "winner_party": "BJP",
            "votes": None,
            "margin": None,
        },
        {
            "constituency_name": "KORBA",
            "winner_name": "JYOTSNA CHARANDAS MAHANT",
            "winner_party": "INC",
            "votes": None,
            "margin": None,
        },
    ]
    csv_path = tmp_path / "summary.csv"
    csv_path.write_text(
        "entity_id,state,election_year,constituency_name,electors,votes_polled,"
        "turnout_pct,winner_candidate,winner_party_id,winner_party_short_raw,"
        "winner_votes,winner_share_pct,runnerup_candidate,runnerup_party_id,"
        "runnerup_party_short_raw,runnerup_votes,margin_votes,margin_pct,source_id\n"
        # BASTAR: yen-gov BJP -- agrees with IV BJP
        "IN-PC-2008-chhattisgarh-294,chhattisgarh,2024,BASTAR,100,80,80.0,"
        "MAHESH KASHYAP,parties.IN.BJP,BJP,50,62.5,KAWASI LAKHMA,parties.IN.INC,INC,30,20,25.0,src-x\n"
        # BILASPUR: yen-gov BJP -- agrees with IV BJP
        "IN-PC-2008-chhattisgarh-295,chhattisgarh,2024,BILASPUR,200,160,80.0,"
        "TOKHAN SAHU,parties.IN.BJP,BJP,90,56.25,DEVENDRA YADAV,parties.IN.INC,INC,70,20,12.5,src-x\n"
        # KORBA: yen-gov BSP -- DISAGREES with IV INC
        "IN-PC-2008-chhattisgarh-299,chhattisgarh,2024,KORBA,300,240,80.0,"
        "SOMEONE BSP,parties.IN.BSP,BSP,140,58.33,JYOTSNA CHARANDAS MAHANT,parties.IN.INC,INC,100,40,16.66,src-x\n",
        encoding="utf-8",
    )
    yg = read_yengov_winners(csv_path, "general-2024", "chhattisgarh")
    assert len(yg) == 3

    rows = compute_diff(
        iv,
        yg,
        state_slug="chhattisgarh",
        event_slug="general-2024",
    )
    # 3 seats x 2 sources = 6 rows.
    assert len(rows) == 6
    # 2 agreements (BASTAR, BILASPUR) + 1 disagreement (KORBA).
    by_constituency: dict[str, bool] = {}
    for r in rows:
        by_constituency[r["constituency_name"]] = (
            by_constituency.get(r["constituency_name"], True) and r["agrees"] == "true"
        )
    assert by_constituency == {"BASTAR": True, "BILASPUR": True, "KORBA": False}
    n_agree = sum(1 for v in by_constituency.values() if v)
    n_disagree = sum(1 for v in by_constituency.values() if not v)
    assert n_agree == 2
    assert n_disagree == 1
    # Verify the per-side column mapping: yen-gov rows project the
    # canonical column names back onto the legacy output columns.
    yengov_row = next(r for r in rows if r["source"] == "yen-gov" and r["constituency_name"] == "BASTAR")
    assert yengov_row["winner_party"] == "parties.IN.BJP"
    assert yengov_row["winner_name"] == "MAHESH KASHYAP"
    assert yengov_row["votes"] == 50
    assert yengov_row["margin"] == 20
