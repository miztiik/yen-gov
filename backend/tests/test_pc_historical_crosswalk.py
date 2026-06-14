"""Tier-A contract + unit tests for the historical PC crosswalk (EGC-B2 Phase 2).

Per CLAUDE.md section 15: no mocks, no big-corpus walk. Reads only the small
committed reference CSV + entities.json + the schema, mirroring the
ac_crosswalk Tier-A test. Pins:

1. The schema loads, is a valid Draft 2020-12 schema, changelog tail matches
   x-version, and a documented example validates; unknown fields / bad enum /
   string pc_no are rejected.
2. Every row of the committed CSV validates against the schema and the
   ``(ge_year, tcpd_state, tcpd_constituency_no)`` PK is unique.
3. The pure ``resolve_pc`` resolver maps the four reorganization families to
   the asserted modern ``(state_code, pc_no)`` and a non-conflicted seat falls
   through automatically (and is provably absent from the override table).
4. ``delim_year`` is a pure function of ``ge_year``.

See also:
    - datasets/schemas/pc-historical-crosswalk.schema.json
    - datasets/data/entities/pc_historical_crosswalk.csv
    - backend/yen_gov/canonical/adapters/eci/pc_crosswalk.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from yen_gov.canonical.adapters.eci.pc_crosswalk import (
    PcCrosswalkError,
    delim_year_for_ge,
    load_pc_crosswalk,
    resolve_pc,
)
from yen_gov.core.schema_registry import schema_version
from yen_gov.sources.eci.ls_constituencywise import load_state_code_lookup

REPO_ROOT = Path(__file__).resolve().parents[2]
DATASETS = REPO_ROOT / "datasets"
SCHEMA = DATASETS / "schemas" / "pc-historical-crosswalk.schema.json"
CSV_PATH = DATASETS / "data" / "entities" / "pc_historical_crosswalk.csv"


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _example_row() -> dict:
    return {
        "ge_year": 2009,
        "tcpd_state": "Andhra Pradesh",
        "tcpd_constituency_no": 18,
        "state_code": "S01",
        "pc_no": 1,
        "match_method": "state_split",
        "note": "Residual Andhra Pradesh seat after the 2014 Telangana split.",
    }


# --- schema ---------------------------------------------------------------


def test_schema_loads_and_changelog_matches_current_version() -> None:
    schema = _load(SCHEMA)
    assert schema["x-version"] == schema_version("pc-historical-crosswalk.schema.json")
    assert schema["x-changelog"][-1]["version"] == schema["x-version"]
    Draft202012Validator.check_schema(schema)


def test_schema_accepts_documented_example() -> None:
    v = Draft202012Validator(_load(SCHEMA))
    assert list(v.iter_errors(_example_row())) == []


def test_schema_rejects_unknown_field() -> None:
    v = Draft202012Validator(_load(SCHEMA))
    row = _example_row()
    row["surprise"] = "nope"
    assert list(v.iter_errors(row)) != []


def test_schema_rejects_unknown_match_method() -> None:
    v = Draft202012Validator(_load(SCHEMA))
    row = _example_row()
    row["match_method"] = "guessed"
    assert list(v.iter_errors(row)) != []


def test_schema_rejects_string_pc_no() -> None:
    v = Draft202012Validator(_load(SCHEMA))
    row = _example_row()
    row["pc_no"] = "1"
    assert list(v.iter_errors(row)) != []


def test_schema_rejects_bad_state_code() -> None:
    v = Draft202012Validator(_load(SCHEMA))
    row = _example_row()
    row["state_code"] = "S1"
    assert list(v.iter_errors(row)) != []


# --- committed CSV --------------------------------------------------------


def _csv_rows() -> list[dict]:
    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_committed_csv_every_row_validates_and_pk_unique() -> None:
    v = Draft202012Validator(_load(SCHEMA))
    seen: set[tuple[int, str, int]] = set()
    rows = _csv_rows()
    assert rows, "crosswalk CSV is empty"
    for raw in rows:
        typed = {
            "ge_year": int(raw["ge_year"]),
            "tcpd_state": raw["tcpd_state"],
            "tcpd_constituency_no": int(raw["tcpd_constituency_no"]),
            "state_code": raw["state_code"],
            "pc_no": int(raw["pc_no"]),
            "match_method": raw["match_method"],
            "note": raw["note"],
        }
        assert list(v.iter_errors(typed)) == [], typed
        key = (typed["ge_year"], typed["tcpd_state"], typed["tcpd_constituency_no"])
        assert key not in seen, f"duplicate PK {key}"
        seen.add(key)


def test_committed_csv_family_row_counts() -> None:
    rows = _csv_rows()
    ap = [r for r in rows if r["tcpd_state"] == "Andhra Pradesh"]
    jk = [r for r in rows if r["tcpd_state"] == "Jammu & Kashmir"]
    dd = [r for r in rows if r["tcpd_state"] in ("Daman & Diu", "Dadra & Nagar Haveli")]
    assert len(ap) == 84  # 42 seats x 2 years (2009, 2014)
    assert len(jk) == 18  # 6 seats x 3 years (2009, 2014, 2019)
    # PR-8 (TODO/20260613-party-deferred-followups-plan.md): added 8 rows
    # mapping pre-1999 DNH+DD UTs to merged-modern U03 for 1989/1991/1996/1998
    # (2 seats x 4 years), bringing the family total to 18 (was 10 for 1999-2019).
    assert len(dd) == 18  # 2 seats x 9 years (1989-2019)
    assert len(rows) == 120


# --- resolver -------------------------------------------------------------


@pytest.fixture(scope="module")
def crosswalk() -> dict:
    return load_pc_crosswalk(DATASETS)


@pytest.fixture(scope="module")
def state_lookup() -> dict:
    return load_state_code_lookup(DATASETS)


def test_delim_year_is_pure_function_of_ge_year() -> None:
    assert delim_year_for_ge(1999) == 1976
    assert delim_year_for_ge(2004) == 1976
    assert delim_year_for_ge(2009) == 2008
    assert delim_year_for_ge(2019) == 2008
    assert delim_year_for_ge(2024) == 2008
    # 1991 (and the rest of 1962-1998) joined the registry in PR-3 of
    # TODO/20260613-party-deferred-followups-plan.md. Pick a year that is
    # genuinely outside the LS GE corpus for the negative case so the
    # resolver still raises ``PcCrosswalkError`` on unknown years.
    with pytest.raises(PcCrosswalkError):
        delim_year_for_ge(1955)


def test_telangana_seat_resolves_to_s29(crosswalk, state_lookup) -> None:
    # 2009 undivided-AP cno 1 = Adilabad -> Telangana S29 pc 1.
    res = resolve_pc(2009, "Andhra_Pradesh", 1, crosswalk=crosswalk, state_lookup=state_lookup)
    assert (res.state_code, res.pc_no, res.delim_year, res.match_method) == (
        "S29",
        1,
        2008,
        "state_split",
    )


def test_residual_ap_seat_renumbers(crosswalk, state_lookup) -> None:
    # 2014 undivided-AP cno 18 = Araku -> residual AP S01 pc 1 (offset -17).
    res = resolve_pc(2014, "Andhra Pradesh", 18, crosswalk=crosswalk, state_lookup=state_lookup)
    assert (res.state_code, res.pc_no) == ("S01", 1)
    # cno 42 = Chittoor -> S01 pc 25.
    res42 = resolve_pc(2014, "Andhra Pradesh", 42, crosswalk=crosswalk, state_lookup=state_lookup)
    assert (res42.state_code, res42.pc_no) == ("S01", 25)


def test_ladakh_seat_resolves_to_u09(crosswalk, state_lookup) -> None:
    res = resolve_pc(2019, "Jammu & Kashmir", 4, crosswalk=crosswalk, state_lookup=state_lookup)
    assert (res.state_code, res.pc_no, res.match_method) == ("U09", 1, "ut_reorg")


def test_jk_seat_renumbers_to_u08(crosswalk, state_lookup) -> None:
    # Udhampur cno 5 -> U08 pc 4; Jammu cno 6 -> U08 pc 5.
    udh = resolve_pc(2014, "Jammu & Kashmir", 5, crosswalk=crosswalk, state_lookup=state_lookup)
    jmu = resolve_pc(2014, "Jammu & Kashmir", 6, crosswalk=crosswalk, state_lookup=state_lookup)
    assert (udh.state_code, udh.pc_no) == ("U08", 4)
    assert (jmu.state_code, jmu.pc_no) == ("U08", 5)


def test_dnh_and_dd_merge_to_u03(crosswalk, state_lookup) -> None:
    dd = resolve_pc(1999, "Daman & Diu", 1, crosswalk=crosswalk, state_lookup=state_lookup)
    dnh = resolve_pc(1999, "Dadra & Nagar Haveli", 1, crosswalk=crosswalk, state_lookup=state_lookup)
    assert (dd.state_code, dd.pc_no, dd.delim_year) == ("U03", 1, 1976)
    assert (dnh.state_code, dnh.pc_no, dnh.delim_year) == ("U03", 2, 1976)


def test_non_conflicted_seat_falls_through(crosswalk, state_lookup) -> None:
    # 2019 Tamil Nadu cno 1 has no override -> automatic S22 pc 1.
    res = resolve_pc(2019, "Tamil_Nadu", 1, crosswalk=crosswalk, state_lookup=state_lookup)
    assert (res.state_code, res.pc_no, res.match_method) == ("S22", 1, "automatic")
    assert (2019, "tamil nadu", 1) not in crosswalk


def test_unknown_state_fails_fast(crosswalk, state_lookup) -> None:
    with pytest.raises(PcCrosswalkError):
        resolve_pc(2019, "Atlantis", 1, crosswalk=crosswalk, state_lookup=state_lookup)
