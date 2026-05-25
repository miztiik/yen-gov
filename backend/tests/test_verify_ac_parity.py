"""Tier-A unit tests for tools.boundaries.verify_ac_parity (Phase D.2).

Real fixtures via `tmp_path` per CLAUDE.md §15 + Holy Law #7. No mocks,
no walking the real corpus (the validator doctrine — see
[docs/architecture/backend/validator.md](../../docs/architecture/backend/validator.md)).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "boundaries"))

import verify_ac_parity as vap  # noqa: E402  (after sys.path manipulation)


def _write_sot(root: Path, eci: str, names: dict[int, str]) -> None:
    path = root / "datasets" / "reference" / "in" / "states" / eci / "constituencies.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "body": "AC",
        "constituencies": [
            {"eci_no": n, "name": name} for n, name in sorted(names.items())
        ],
    }
    path.write_text(json.dumps(doc), encoding="utf-8")


def _write_geojson(root: Path, eci: str, features_props: list[dict]) -> None:
    path = (
        root / "datasets" / "boundaries" / "in" / "ac" / f"state=in_{eci.lower()}" / "all.geojson"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": p,
                "geometry": {"type": "Point", "coordinates": [80.0, 13.0]},
            }
            for p in features_props
        ],
    }
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_normalize_name_strips_diacritics_case_and_reservation_suffix() -> None:
    assert vap.normalize_name("Ramnagar (SC)") == "ramnagar"
    assert vap.normalize_name("RAMNAGAR (SC)") == "ramnagar"
    assert vap.normalize_name("Ramnagar (ST)") == "ramnagar"
    assert vap.normalize_name("Ramnagar (Gen)") == "ramnagar"
    # NFKD diacritics fold
    assert vap.normalize_name("Pondichéry") == vap.normalize_name("Pondichery")
    # Non-string -> empty
    assert vap.normalize_name(None) == ""


def test_perfect_parity_passes(tmp_path: Path) -> None:
    eci = "S99"
    sot = {1: "Ramnagar (SC)", 2: "Bagaha", 3: "Lauriya"}
    _write_sot(tmp_path, eci, sot)
    _write_geojson(
        tmp_path,
        eci,
        [
            {"ac_no": 1, "ac_name": "RAMNAGAR (SC)", "AC_ID": "99001"},
            {"ac_no": 2, "ac_name": "BAGAHA", "AC_ID": "99002"},
            {"ac_no": 3, "ac_name": "LAURIYA", "AC_ID": "99003"},
        ],
    )
    ok, errors, stats = vap.verify_state(tmp_path, eci)
    assert ok, errors
    assert errors == []
    assert stats["snap_count"] == 3
    assert stats["name_parity"] == pytest.approx(1.0)


def test_count_mismatch_fails(tmp_path: Path) -> None:
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A", 2: "B", 3: "C"})
    _write_geojson(
        tmp_path,
        eci,
        [{"ac_no": 1, "ac_name": "A"}, {"ac_no": 2, "ac_name": "B"}],
    )
    ok, errors, _ = vap.verify_state(tmp_path, eci)
    assert not ok
    assert any("count mismatch" in e for e in errors)
    assert any("missing from snapshot" in e for e in errors)


def test_extra_ac_no_fails(tmp_path: Path) -> None:
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A", 2: "B"})
    _write_geojson(
        tmp_path,
        eci,
        [
            {"ac_no": 1, "ac_name": "A"},
            {"ac_no": 2, "ac_name": "B"},
            {"ac_no": 99, "ac_name": "Z"},
        ],
    )
    ok, errors, _ = vap.verify_state(tmp_path, eci)
    assert not ok
    assert any("not in SoT" in e for e in errors)


def test_duplicate_ac_no_fails(tmp_path: Path) -> None:
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A", 2: "B"})
    _write_geojson(
        tmp_path,
        eci,
        [
            {"ac_no": 1, "ac_name": "A"},
            {"ac_no": 1, "ac_name": "A-dup"},  # duplicate
            {"ac_no": 2, "ac_name": "B"},
        ],
    )
    ok, errors, _ = vap.verify_state(tmp_path, eci)
    assert not ok
    assert any("duplicate ac_no" in e for e in errors)


def test_name_parity_below_threshold_fails(tmp_path: Path) -> None:
    """4 ACs; only 2 names match -> 50% < 95%."""
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "Alpha", 2: "Beta", 3: "Gamma", 4: "Delta"})
    _write_geojson(
        tmp_path,
        eci,
        [
            {"ac_no": 1, "ac_name": "ALPHA"},
            {"ac_no": 2, "ac_name": "BETA"},
            {"ac_no": 3, "ac_name": "NOT-GAMMA"},
            {"ac_no": 4, "ac_name": "NOT-DELTA"},
        ],
    )
    ok, errors, stats = vap.verify_state(tmp_path, eci)
    assert not ok
    assert stats["name_parity"] == pytest.approx(0.5)
    assert any("name parity" in e for e in errors)


def test_name_parity_at_threshold_passes(tmp_path: Path) -> None:
    """20 ACs; 19 names match -> 95.0% = threshold."""
    eci = "S99"
    sot = {n: f"AC{n}" for n in range(1, 21)}
    _write_sot(tmp_path, eci, sot)
    feats = [{"ac_no": n, "ac_name": f"AC{n}"} for n in range(1, 20)]
    feats.append({"ac_no": 20, "ac_name": "DIFFERENT"})  # 1 mismatch
    _write_geojson(tmp_path, eci, feats)
    ok, _, stats = vap.verify_state(tmp_path, eci)
    assert ok
    assert stats["name_parity"] == pytest.approx(0.95)


def test_missing_snapshot_raises_descriptive(tmp_path: Path) -> None:
    _write_sot(tmp_path, "S99", {1: "A"})
    with pytest.raises(FileNotFoundError, match="snapshot geojson not found"):
        vap.verify_state(tmp_path, "S99")


def test_missing_sot_raises_descriptive(tmp_path: Path) -> None:
    _write_geojson(tmp_path, "S99", [{"ac_no": 1, "ac_name": "A"}])
    with pytest.raises(FileNotFoundError, match="SoT not found"):
        vap.verify_state(tmp_path, "S99")


def test_reservation_suffix_does_not_break_parity(tmp_path: Path) -> None:
    """SoT name is 'Ramnagar', snapshot is 'RAMNAGAR (SC)' (LGD-inlined
    reservation). normalize_name strips the suffix; parity remains 100%."""
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "Ramnagar", 2: "Bagaha"})
    _write_geojson(
        tmp_path,
        eci,
        [
            {"ac_no": 1, "ac_name": "RAMNAGAR (SC)"},
            {"ac_no": 2, "ac_name": "BAGAHA"},
        ],
    )
    ok, _, stats = vap.verify_state(tmp_path, eci)
    assert ok
    assert stats["name_parity"] == pytest.approx(1.0)


def test_main_exit_code_zero_on_pass(tmp_path: Path) -> None:
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A"})
    _write_geojson(tmp_path, eci, [{"ac_no": 1, "ac_name": "A"}])
    rc = vap.main(["--state", eci, "--root", str(tmp_path)])
    assert rc == 0


def test_main_exit_code_one_on_fail(tmp_path: Path) -> None:
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A", 2: "B"})
    _write_geojson(tmp_path, eci, [{"ac_no": 1, "ac_name": "A"}])
    rc = vap.main(["--state", eci, "--root", str(tmp_path)])
    assert rc == 1
