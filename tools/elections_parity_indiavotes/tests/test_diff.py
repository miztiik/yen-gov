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
    period_label_matcher,
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


# --- period-label matcher ---------------------------------------------------


def test_period_label_matcher_accepts_general_2024():
    is_match = period_label_matcher("general-2024")
    assert is_match("LsGenJun2024")
    assert is_match("LsGenApr2024")  # hypothetical alternate month
    assert not is_match("LsGenJun2019")
    assert not is_match("AcGenMay2024")  # wrong body
    assert not is_match("")


def test_period_label_matcher_accepts_assembly_2023():
    is_match = period_label_matcher("assembly-2023")
    assert is_match("AcGenNov2023")
    assert not is_match("LsGenApr2024")


def test_period_label_matcher_rejects_bye_slug():
    with pytest.raises(ValueError):
        period_label_matcher("general-bye-2024-bihar-bastar")


def test_period_label_matcher_rejects_garbage():
    with pytest.raises(ValueError):
        period_label_matcher("not-a-slug")


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


def test_read_yengov_winners_pivots_long_format_into_per_entity_rows():
    rows = read_yengov_winners(YENGOV_PERFECT, "general-2024")
    assert len(rows) == 3
    by_id = {r["entity_id"]: r for r in rows}
    assert set(by_id) == {
        "IN-PC-2008-S26-R1",
        "IN-PC-2008-S26-B1",
        "IN-PC-2008-S26-K1",
    }
    raipur = by_id["IN-PC-2008-S26-R1"]
    assert raipur["winner_party"] == "parties.IN.BJP"
    assert raipur["votes"] == 1_050_351
    assert raipur["margin"] == 575_285


def test_read_yengov_winners_skips_non_matching_period_labels(tmp_path):
    """Rows with a period_label outside the requested event are ignored."""

    csv_path = tmp_path / "mini.csv"
    csv_path.write_text(
        "entity_id,year,period_label,period_seq,indicator_id,value_numeric,value_text,source_id,derivation\n"
        "IN-PC-2008-S26-X,2019,LsGenApr2019,5,pc-winner-party-id,,parties.IN.INC,src-x,join\n"
        "IN-PC-2008-S26-X,2024,LsGenJun2024,6,pc-winner-party-id,,parties.IN.BJP,src-y,join\n",
        encoding="utf-8",
    )
    rows = read_yengov_winners(csv_path, "general-2024")
    assert len(rows) == 1
    assert rows[0]["winner_party"] == "parties.IN.BJP"


# --- compute_diff -- the G1-EVIDENCE oracle ---------------------------------


def _name_map_for_synthetic():
    """Map synthetic entity_ids to constituency names matching the HTML fixture."""

    return {
        "IN-PC-2008-S26-R1": "Raipur",
        "IN-PC-2008-S26-B1": "Bilaspur",
        "IN-PC-2008-S26-K1": "Korba",
    }


def test_compute_diff_zero_deltas_on_perfect_match():
    """SYNTHETIC ORACLE 1: perfect match -> 0 disagreements, 100% agreement."""

    iv = parse_winners([IV_HTML])
    yg = read_yengov_winners(YENGOV_PERFECT, "general-2024")
    rows = compute_diff(
        iv,
        yg,
        state_slug="chhattisgarh",
        event_slug="general-2024",
        yengov_name_by_entity_id=_name_map_for_synthetic(),
    )
    # 3 constituencies x 2 rows (one per source) = 6 rows.
    assert len(rows) == 6
    assert all(r["agrees"] == "true" for r in rows)
    assert all(r["delta_notes"] == "" for r in rows)
    assert agreement_pct(rows) == pytest.approx(100.0)


def test_compute_diff_identifies_mismatches():
    """SYNTHETIC ORACLE 2: 2 of 3 seats disagree -> exactly 2 mismatches surfaced."""

    iv = parse_winners([IV_HTML])  # BJP, BJP, INC
    yg = read_yengov_winners(YENGOV_MISMATCH, "general-2024")  # INC, BJP, BSP
    rows = compute_diff(
        iv,
        yg,
        state_slug="chhattisgarh",
        event_slug="general-2024",
        yengov_name_by_entity_id=_name_map_for_synthetic(),
    )
    # Still 6 rows (3 seats x 2 sources). Find the per-constituency verdict.
    by_constituency: dict[str, bool] = {}
    for r in rows:
        by_constituency[r["constituency_name"]] = (
            by_constituency.get(r["constituency_name"], True) and r["agrees"] == "true"
        )
    # Raipur: BJP vs INC -> mismatch. Bilaspur: BJP vs BJP -> agree. Korba: INC vs BSP -> mismatch.
    assert by_constituency == {"Raipur": False, "Bilaspur": True, "Korba": False}
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
        yengov_name_by_entity_id={},
    )
    assert len(rows) == 1
    assert rows[0]["source"] == "indiavotes"
    assert rows[0]["agrees"] == "false"
    assert rows[0]["delta_notes"] == "no yen-gov match"
