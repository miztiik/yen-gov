"""Tests for B2b.5.0c-2 electoral.csv + electoral_district_membership.csv emitters.

No mocks (Holy Law #7): tmp_path fixtures shaped like the real committed inputs
(LGD snapshot constituencies + membership, state_codes, geo). A real-inputs test
locks the FK contract on the live snapshot.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed import electoral_csv_from_snapshot as electoral
from yen_gov.canonical.seed import electoral_district_membership_csv as membership

REPO_ROOT = Path(__file__).resolve().parents[2]
ENTITIES = REPO_ROOT / "datasets" / "data" / "entities"
SNAPSHOT = REPO_ROOT / "datasets" / "reference" / "lgd"


def _write(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow(r)
    return path


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _state_codes(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "state_codes.csv",
        ["lgd_state_id", "lgd_name", "iso_3166_2", "census_2001_code", "census_2011_code", "kind", "slug", "aliases"],
        [["28", "Andhra Pradesh", "IN-AP", "28", "28", "state", "andhra-pradesh", ""]],
    )


def _constituencies(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "constituencies.csv",
        ["lgd_state_code", "kind", "lgd_code", "eci_code", "name", "parent_pc_lgd_code"],
        [
            ["28", "pc", "411", "9", "Amalapuram", ""],
            ["28", "ac", "3166", "163", "Amalapuram", "411"],
            ["28", "ac", "3167", "165", "Gannavaram", "411"],
        ],
    )


# --------------------------------------------------------------------------- #
# electoral.csv                                                                #
# --------------------------------------------------------------------------- #

def test_electoral_folds_eci_no_and_parent_pc(tmp_path):
    out = tmp_path / "electoral.csv"
    electoral.emit(
        constituencies_csv=_constituencies(tmp_path),
        state_codes_csv=_state_codes(tmp_path),
        out_path=out,
    )
    by_id = {r["entity_id"]: r for r in _read(out)}
    pc = by_id["IN-PC-2008-andhra-pradesh-411"]
    assert pc["entity_kind"] == "pc"
    assert pc["eci_no"] == "9"
    assert pc["parent"] == "andhra-pradesh"
    ac = by_id["IN-AC-2008-andhra-pradesh-3166"]
    assert ac["entity_kind"] == "ac"
    assert ac["eci_no"] == "163"  # folded ECI ballot serial (DIRECT from PRI)
    assert ac["parent"] == "IN-PC-2008-andhra-pradesh-411"
    assert ac["state"] == "andhra-pradesh"


def test_electoral_entity_id_is_lgd_native(tmp_path):
    """entity_id suffix is the LGD register code, never state_code*1000+eci_no."""
    out = tmp_path / "electoral.csv"
    electoral.emit(
        constituencies_csv=_constituencies(tmp_path),
        state_codes_csv=_state_codes(tmp_path),
        out_path=out,
    )
    ids = {r["entity_id"] for r in _read(out)}
    assert "IN-AC-2008-andhra-pradesh-3166" in ids  # lgd_ac_id
    # the arithmetic scheme would have produced 28000+163 = 28163; it must NOT appear
    assert "IN-AC-2008-andhra-pradesh-28163" not in ids


def test_electoral_rejects_unknown_state(tmp_path):
    cons = _write(
        tmp_path / "constituencies.csv",
        ["lgd_state_code", "kind", "lgd_code", "eci_code", "name", "parent_pc_lgd_code"],
        [["99", "ac", "1", "1", "Nowhere", ""]],
    )
    with pytest.raises(ValueError, match="unknown lgd_state_code"):
        electoral.emit(
            constituencies_csv=cons,
            state_codes_csv=_state_codes(tmp_path),
            out_path=tmp_path / "out.csv",
        )


# --------------------------------------------------------------------------- #
# electoral_district_membership.csv                                           #
# --------------------------------------------------------------------------- #

def _geo(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "geo.csv",
        ["entity_id", "name", "parent", "entity_kind", "aliases", "census_2001_code", "census_2011_code"],
        [
            ["andhra-pradesh", "Andhra Pradesh", "IN", "state", "IN-AP|lgd:28", "28", "28"],
            ["andhra-pradesh/konaseema", "Konaseema", "andhra-pradesh", "district", "lgd:747", "", ""],
            ["andhra-pradesh/krishna", "Krishna", "andhra-pradesh", "district", "lgd:510", "16", "547"],
        ],
    )


def _membership_snapshot(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "constituency_district_membership.csv",
        ["lgd_state_code", "ac_lgd_code", "lgd_district_code", "village_count", "is_primary"],
        [
            ["28", "3167", "747", "2", "true"],
            ["28", "3167", "510", "1", "false"],
        ],
    )


def test_membership_maps_to_geo_and_is_primary(tmp_path):
    out = tmp_path / "membership.csv"
    membership.emit(
        membership_snapshot_csv=_membership_snapshot(tmp_path),
        state_codes_csv=_state_codes(tmp_path),
        geo_csv=_geo(tmp_path),
        source_id="src-test",
        lgd_snapshot="2026-06-05",
        out_path=out,
    )
    rows = _read(out)
    by_district = {r["lgd_district_id"]: r for r in rows}
    primary = by_district["andhra-pradesh/konaseema"]
    assert primary["electoral_id"] == "IN-AC-2008-andhra-pradesh-3167"
    assert primary["is_primary"] == "true"
    assert primary["source_id"] == "src-test"
    assert primary["lgd_snapshot"] == "2026-06-05"
    assert by_district["andhra-pradesh/krishna"]["is_primary"] == "false"


def test_membership_rejects_unmapped_district(tmp_path):
    snap = _write(
        tmp_path / "constituency_district_membership.csv",
        ["lgd_state_code", "ac_lgd_code", "lgd_district_code", "village_count", "is_primary"],
        [["28", "3167", "999", "1", "true"]],
    )
    with pytest.raises(ValueError, match="no geo.csv entity"):
        membership.emit(
            membership_snapshot_csv=snap,
            state_codes_csv=_state_codes(tmp_path),
            geo_csv=_geo(tmp_path),
            source_id="src-test",
            lgd_snapshot="2026-06-05",
            out_path=tmp_path / "out.csv",
        )


# --------------------------------------------------------------------------- #
# Real-inputs FK lock                                                          #
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(
    not (
        (SNAPSHOT / "constituencies.csv").exists()
        and (ENTITIES / "electoral.csv").exists()
        and (ENTITIES / "electoral_district_membership.csv").exists()
    ),
    reason="real committed inputs absent",
)
def test_real_committed_files_validate():
    """The committed electoral + membership files pass the FK validator."""
    validate_csv(
        path=ENTITIES / "electoral.csv",
        file_class=electoral.FILE_CLASS,
        repo_root=REPO_ROOT,
    )
    validate_csv(
        path=ENTITIES / "electoral_district_membership.csv",
        file_class=membership.FILE_CLASS,
        repo_root=REPO_ROOT,
    )
    # eci_no is folded on every constituency row that the snapshot carried one for.
    el = _read(ENTITIES / "electoral.csv")
    assert any(r["eci_no"] for r in el), "eci_no must be folded onto electoral rows"
