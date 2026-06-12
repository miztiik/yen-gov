"""Tests for ``tools.correlate_unk_via_tcpd_catalogue`` (PR-Q2).

Covers the brief's decision-tree fixtures:

  - B1 / B2 singleton resolution
  - NA'S placeholder collision handling
  - state-disambiguation
  - state-year collision skip
  - basic-slug collision with existing parties.csv (disambiguated mint)

All fixtures are real CSV files under ``tmp_path`` (Holy Law #7,
no mocks).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tools.correlate_unk_via_tcpd_catalogue.__main__ import (
    UnkLabel,
    build_tcpd_catalogue_indexes,
    decide,
)


PARTIES_FIELDNAMES = [
    "party_id",
    "short",
    "full",
    "eci_codes",
    "brand_colour",
    "symbol_asset",
    "wikipedia",
    "aliases",
    "recognition_scope",
    "home_state_codes",
    "founded_year",
    "dissolved_year",
    "predecessor_party_ids",
    "successor_party_ids",
    "name_history",
    "claims_to_parent_name",
    "name_native_script",
    "is_sentinel",
]

TCPD_FIELDNAMES = [
    "Assembly",
    "State_Name",
    "Party_Name",
    "Party_Type",
    "Party_ID",
    "Frequent_Abbreviation",
    "Last_Abbreviation",
    "Abbreviations",
    "Start_Year",
    "Last_Year",
    "No_Assemblies_Contested",
    "Assemblies_Contested",
    "Candidates_Contested",
    "Candidates_Represented",
    "Females_Contested",
    "Females_Represented",
    "SC_Seats_Contested",
    "SC_Seats_Represented",
    "ST_Seats_Contested",
    "ST_Seats_Represented",
    "BiPoll_Contested",
]


def _write_tcpd_catalogue(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=TCPD_FIELDNAMES, lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in TCPD_FIELDNAMES})


def _write_parties_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=PARTIES_FIELDNAMES, lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in PARTIES_FIELDNAMES})


def _load_parties(path: Path) -> tuple[
    dict[str, dict[str, str]], dict[str, str]
]:
    """Mirror the tool's ``_load_parties_csv`` shape from a fixture path."""
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    by_pid: dict[str, dict[str, str]] = {}
    claimed: dict[str, str] = {}
    for r in rows:
        pid = (r.get("party_id") or "").strip()
        if not pid:
            continue
        by_pid[pid] = r
        short = (r.get("short") or "").upper().strip()
        if short:
            claimed[short] = pid
        for a in (r.get("aliases") or "").split("|"):
            v = a.strip().upper()
            if v:
                claimed[v] = pid
    return by_pid, claimed


def _tcpd_row(
    *,
    party_id: str,
    party_name: str,
    state_name: str = "All_States",
    party_type: str = "Local Party",
    frequent_abbrev: str = "",
    last_abbrev: str = "",
    abbreviations: str = "",
    start_year: str = "2010",
    last_year: str = "2015",
    assembly: str = "Vidhan_Sabha",
) -> dict[str, str]:
    """Minimal TCPD row builder for fixtures."""
    return {
        "Assembly": assembly,
        "State_Name": state_name,
        "Party_Name": party_name,
        "Party_Type": party_type,
        "Party_ID": party_id,
        "Frequent_Abbreviation": frequent_abbrev,
        "Last_Abbreviation": last_abbrev or frequent_abbrev,
        "Abbreviations": abbreviations or frequent_abbrev,
        "Start_Year": start_year,
        "Last_Year": last_year,
    }


def _decide_args(
    tcpd_csv: Path, parties_csv: Path,
) -> dict[str, object]:
    """Build the kwargs dict for ``decide(...)`` from on-disk fixtures."""
    pid_to_record, full_to_pids, abbr_to_pids = (
        build_tcpd_catalogue_indexes(tcpd_csv)
    )
    by_pid_row, claimed_aliases = _load_parties(parties_csv)
    return {
        "pid_to_record": pid_to_record,
        "full_to_pids": full_to_pids,
        "abbr_to_pids": abbr_to_pids,
        "by_pid_row": by_pid_row,
        "claimed_aliases": claimed_aliases,
        "slug_to_iso": {"madhya-pradesh": "IN-MP", "punjab": "IN-PB"},
    }


# --- Test 1: B1 full-name singleton ----------------------------------------


def test_b1_full_name_unique_pid_resolves_to_mint(tmp_path: Path) -> None:
    """B1 hit on Party_Name + no parties.csv bridge -> mint-new."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99001",
            party_name="TEST PARTY ALPHA",
            frequent_abbrev="TPA",
        ),
    ])
    _write_parties_csv(parties_csv, [])

    rec = UnkLabel(
        label="TEST PARTY ALPHA",
        publisher_label="TEST PARTY ALPHA",
        n_rows=3,
        states={"madhya-pradesh"},
        years={2015},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.bucket == "B1"
    assert verdict.action == "mint-new"
    assert verdict.tcpd_party_id == "99001"
    assert verdict.proposed_party_id == "parties.IN.TPA"
    assert verdict.tcpd_state_disambiguation == "singleton"


def test_b1_full_name_unique_pid_resolves_to_alias_when_bridged(
    tmp_path: Path,
) -> None:
    """B1 hit + existing parties.csv carries the abbreviation -> alias-add."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99002",
            party_name="TEST PARTY BETA",
            frequent_abbrev="TPB",
        ),
    ])
    _write_parties_csv(parties_csv, [
        {"party_id": "parties.IN.TPB", "short": "TPB", "full": "Test Party Beta"},
    ])

    rec = UnkLabel(
        label="TEST PARTY BETA",
        publisher_label="Test Party Beta",
        n_rows=2,
        states={"madhya-pradesh"},
        years={2015},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.bucket == "B1"
    assert verdict.action == "alias-add"
    assert verdict.proposed_party_id == "parties.IN.TPB"


# --- Test 2: B2 abbreviation singleton -------------------------------------


def test_b2_abbreviation_unique_pid_resolves(tmp_path: Path) -> None:
    """B2 hit on Frequent_Abbreviation -> resolves to TCPD pid."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99003",
            party_name="X Y Z PARTY",
            frequent_abbrev="XYZ",
        ),
    ])
    _write_parties_csv(parties_csv, [])

    rec = UnkLabel(
        label="XYZ",
        publisher_label="XYZ",
        n_rows=5,
        states={"madhya-pradesh"},
        years={2018},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.bucket == "B2"
    assert verdict.action == "mint-new"
    assert verdict.tcpd_party_id == "99003"
    assert verdict.proposed_party_id == "parties.IN.XYZ"
    assert verdict.tcpd_party_name == "X Y Z PARTY"


# --- Test 3: NA'S placeholder collision ------------------------------------


def test_collision_with_nas_placeholder_picks_real_party(
    tmp_path: Path,
) -> None:
    """When 2 TCPD pids share abbreviation but one is NA'S -> pick the other."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99004",
            party_name="NA'S",
            frequent_abbrev="PP",
        ),
        _tcpd_row(
            party_id="99005",
            party_name="PRAJA PARISHAD",
            frequent_abbrev="PP",
        ),
    ])
    _write_parties_csv(parties_csv, [])

    rec = UnkLabel(
        label="PP",
        publisher_label="PP",
        n_rows=4,
        states={"madhya-pradesh"},
        years={2012},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    # The NA'S pid is filtered before disambiguation; the real party wins.
    assert verdict.bucket == "B2"
    assert verdict.action == "mint-new"
    assert verdict.tcpd_party_id == "99005"
    assert verdict.tcpd_party_name == "PRAJA PARISHAD"
    assert verdict.tcpd_state_disambiguation == "singleton"
    assert verdict.proposed_party_id == "parties.IN.PP"


def test_collision_all_placeholders_skips(tmp_path: Path) -> None:
    """When ALL TCPD candidates are NA'S placeholders -> skip with reason."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(party_id="99006", party_name="NA'S", frequent_abbrev="QQ"),
        _tcpd_row(party_id="99007", party_name="NA'S", frequent_abbrev="QQ"),
    ])
    _write_parties_csv(parties_csv, [])

    rec = UnkLabel(
        label="QQ",
        publisher_label="QQ",
        n_rows=1,
        states={"madhya-pradesh"},
        years={2014},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.action == ""  # skipped
    assert verdict.skip_reason == "tcpd-placeholder-only"


# --- Test 4: state disambiguation ------------------------------------------


def test_collision_state_disambiguation(tmp_path: Path) -> None:
    """2 TCPD pids share abbreviation; OUR state covered by only one -> resolve."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99008",
            party_name="RASHTRIYA JANPRIYA PARTY",
            state_name="Uttar_Pradesh",
            frequent_abbrev="RTJP",
        ),
        _tcpd_row(
            party_id="99009",
            party_name="RASHTRIYA JANSABHA PARTY",
            state_name="Madhya_Pradesh",
            frequent_abbrev="RTJP",
        ),
    ])
    _write_parties_csv(parties_csv, [])

    rec = UnkLabel(
        label="RTJP",
        publisher_label="RTJP",
        n_rows=3,
        states={"madhya-pradesh"},  # matches pid 99009 only
        years={2013},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.bucket == "B2"
    assert verdict.action == "mint-new"
    assert verdict.tcpd_party_id == "99009"
    assert verdict.tcpd_state_disambiguation == "state-match"


# --- Test 5: collision unresolved ------------------------------------------


def test_collision_unresolved_emits_skip(tmp_path: Path) -> None:
    """2 TCPD pids share abbreviation + cover OUR state + overlap years -> skip."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99010",
            party_name="ALPHA MOST BIG",
            state_name="Madhya_Pradesh",
            frequent_abbrev="AMB",
            start_year="2010",
            last_year="2015",
        ),
        _tcpd_row(
            party_id="99011",
            party_name="ANOTHER MIGHTY BLOC",
            state_name="Madhya_Pradesh",
            frequent_abbrev="AMB",
            start_year="2010",
            last_year="2015",
        ),
    ])
    _write_parties_csv(parties_csv, [])

    rec = UnkLabel(
        label="AMB",
        publisher_label="AMB",
        n_rows=3,
        states={"madhya-pradesh"},
        years={2012},  # both pids cover 2012
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.action == ""  # skipped
    assert verdict.skip_reason == "tcpd-state-year-collision"


# --- Test 6: year disambiguation -------------------------------------------


def test_collision_year_disambiguation(tmp_path: Path) -> None:
    """2 TCPD pids share abbreviation + state; year window picks one."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99012",
            party_name="OLDER PARTY",
            state_name="Madhya_Pradesh",
            frequent_abbrev="OOO",
            start_year="2008",
            last_year="2010",
        ),
        _tcpd_row(
            party_id="99013",
            party_name="NEWER PARTY",
            state_name="Madhya_Pradesh",
            frequent_abbrev="OOO",
            start_year="2018",
            last_year="2020",
        ),
    ])
    _write_parties_csv(parties_csv, [])

    rec = UnkLabel(
        label="OOO",
        publisher_label="OOO",
        n_rows=2,
        states={"madhya-pradesh"},
        years={2019},  # matches NEWER PARTY only
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.bucket == "B2"
    assert verdict.action == "mint-new"
    assert verdict.tcpd_party_id == "99013"
    assert verdict.tcpd_state_disambiguation == "year-match"


# --- Test 7: existing-canonical collision with disambiguated mint ----------


def test_existing_canonical_collision_disambiguates_mint(
    tmp_path: Path,
) -> None:
    """Slug collision with incompatible full -> mint disambiguated slug.

    Mirrors the live ADS case: TCPD pid 17049 has Frequent_Abbreviation=ADS
    but parties.IN.ADS already exists for a DIFFERENT party (Apna Dal
    (Soneylal)). The disambiguated mint produces parties.IN.ADS_<state>.
    """
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99014",
            party_name="AKALI DAL - SANT FATEH SINGH GROUP",
            state_name="Punjab",
            frequent_abbrev="ADS",
            start_year="1967",
            last_year="1968",
        ),
    ])
    _write_parties_csv(parties_csv, [
        {
            "party_id": "parties.IN.ADS",
            "short": "AD(S)",
            "full": "Apna Dal (Soneylal)",
            "aliases": "ADAL",
        },
    ])

    rec = UnkLabel(
        label="ADS",
        publisher_label="ADS",
        n_rows=4,
        states={"punjab"},  # single state -> state-based disambig slug
        years={1967},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.bucket == "B2"
    assert verdict.action == "mint-new"
    assert verdict.tcpd_party_id == "99014"
    # Basic slug parties.IN.ADS would collide with existing canonical;
    # disambiguator falls back to ADS_<state-iso>.
    assert verdict.proposed_party_id == "parties.IN.ADS_IN_PB"


def test_basic_slug_collision_compatible_full_aliases_in(
    tmp_path: Path,
) -> None:
    """Slug pre-exists with compatible full BUT bridge_keys miss -> alias-add.

    Exercises the slug-coincidence fallback: parties.csv has a row whose
    party_id matches the slug we would mint from TCPD's frequent_abbrev,
    but the row's short / aliases do not carry that abbreviation (e.g.
    short was renamed away in a prior dedupe). The slug coincidence IS
    the bridge.
    """
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99015",
            party_name="Sapaks Party",
            frequent_abbrev="SPAKP",
        ),
    ])
    # parties.IN.SPAKP exists with the right full, but short=DIFFSHORT
    # carries no SPAKP key in short / aliases. Only the party_id slug
    # bridges to TCPD.
    _write_parties_csv(parties_csv, [
        {
            "party_id": "parties.IN.SPAKP",
            "short": "DIFFSHORT",
            "full": "Sapaks Party",
            "aliases": "",
        },
    ])

    rec = UnkLabel(
        label="SPAKP",  # publisher label matches TCPD's frequent abbrev
        publisher_label="SPAKP",
        n_rows=4,
        states={"madhya-pradesh"},
        years={2018},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.bucket == "B2"
    assert verdict.action == "alias-add"
    assert verdict.proposed_party_id == "parties.IN.SPAKP"


# --- Test 8: not in TCPD ---------------------------------------------------


def test_not_in_tcpd_catalogue_skips(tmp_path: Path) -> None:
    """Label absent from TCPD -> skip with reason `not-in-tcpd-catalogue`."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(party_id="99016", party_name="OTHER PARTY", frequent_abbrev="OPP"),
    ])
    _write_parties_csv(parties_csv, [])

    rec = UnkLabel(
        label="NOTINUS",
        publisher_label="NotInUs",
        n_rows=1,
        states={"madhya-pradesh"},
        years={2020},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.action == ""
    assert verdict.skip_reason == "not-in-tcpd-catalogue"


# --- Test 9: All_States covers any state ----------------------------------


def test_all_states_pid_covers_any_state(tmp_path: Path) -> None:
    """TCPD pid with State_Name=All_States must match any OUR state."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99017",
            party_name="NATIONAL OUTFIT",
            state_name="All_States",
            party_type="National Party",
            frequent_abbrev="NTO",
        ),
        _tcpd_row(
            party_id="99018",
            party_name="LOCAL OUTFIT",
            state_name="Punjab",
            frequent_abbrev="NTO",
        ),
    ])
    _write_parties_csv(parties_csv, [])

    # OUR state is madhya-pradesh; only the All_States pid covers it.
    rec = UnkLabel(
        label="NTO",
        publisher_label="NTO",
        n_rows=2,
        states={"madhya-pradesh"},
        years={2015},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.tcpd_party_id == "99017"
    assert verdict.tcpd_state_disambiguation == "state-match"


# --- Test 10: B1 whitespace normalisation ----------------------------------


def test_b1_whitespace_normalisation(tmp_path: Path) -> None:
    """B1 lookup must tolerate internal whitespace variation (collapse runs)."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99019",
            party_name="Bahujan Samaj Party  (Ambedkar)",  # 2 spaces
            frequent_abbrev="BSPA",
        ),
    ])
    _write_parties_csv(parties_csv, [])

    rec = UnkLabel(
        label="BAHUJAN SAMAJ PARTY (AMBEDKAR)",  # single space (variant)
        publisher_label="Bahujan Samaj Party (Ambedkar)",
        n_rows=12,
        states={"madhya-pradesh"},
        years={2018},
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.bucket == "B1"
    assert verdict.action == "mint-new"
    assert verdict.tcpd_party_id == "99019"


# --- Test 11: post-2021 year handling --------------------------------------


def test_post_2021_year_still_resolves(tmp_path: Path) -> None:
    """TCPD ``last_year == 2021`` -> still-active; post-2021 election year OK."""
    tcpd_csv = tmp_path / "tcpd.csv"
    parties_csv = tmp_path / "parties.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99020",
            party_name="STILL ACTIVE",
            state_name="Madhya_Pradesh",
            frequent_abbrev="STA",
            start_year="2010",
            last_year="2021",
        ),
        _tcpd_row(
            party_id="99021",
            party_name="OLD DEAD",
            state_name="Madhya_Pradesh",
            frequent_abbrev="STA",
            start_year="1990",
            last_year="1999",
        ),
    ])
    _write_parties_csv(parties_csv, [])

    rec = UnkLabel(
        label="STA",
        publisher_label="STA",
        n_rows=3,
        states={"madhya-pradesh"},
        years={2024},  # post-catalogue; pid 99020 should still cover
    )
    verdict = decide(rec, **_decide_args(tcpd_csv, parties_csv))

    assert verdict.bucket == "B2"
    assert verdict.action == "mint-new"
    assert verdict.tcpd_party_id == "99020"
    assert verdict.tcpd_state_disambiguation == "year-match"


# --- Test 12: meta integrity ----------------------------------------------


def test_index_collapse_picks_most_recent_row(tmp_path: Path) -> None:
    """Multiple TCPD rows per Party_ID -> canonical = max (Last_Year, Start_Year)."""
    tcpd_csv = tmp_path / "tcpd.csv"
    _write_tcpd_catalogue(tcpd_csv, [
        _tcpd_row(
            party_id="99022",
            party_name="EARLY",
            frequent_abbrev="EAR",
            start_year="1990",
            last_year="1995",
        ),
        _tcpd_row(
            party_id="99022",
            party_name="LATE",
            frequent_abbrev="LAT",
            start_year="2010",
            last_year="2020",
        ),
    ])
    pid_to_record, _, _ = build_tcpd_catalogue_indexes(tcpd_csv)
    record = pid_to_record["99022"]
    # most-recent (Last_Year=2020) -> "LATE"
    assert record.party_name == "LATE"
    assert record.frequent_abbrev == "LAT"
    # year-window is union: min start, max last
    assert record.start_year == 1990
    assert record.last_year == 2020


# --- regression: backward-compat with PR #952's apply tool -----------------


def test_verdict_csv_has_pr952_columns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """verdict.csv carries every column the existing apply tool reads."""
    from tools.correlate_unk_via_tcpd_catalogue.__main__ import VERDICT_FIELDS
    pr952_required = {
        "party_short_raw",
        "state",
        "tcpd_party_type",
        "tcpd_party_name",
        "tcpd_frequent_abbrev",
        "proposed_party_id",
        "action",
    }
    missing = pr952_required - set(VERDICT_FIELDS)
    assert not missing, f"verdict.csv missing PR #952 apply-tool columns: {missing}"
