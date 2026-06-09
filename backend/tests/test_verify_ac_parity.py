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
    path = root / "datasets" / "data" / "entities" / "boundaries_sot" / eci / "constituencies.json"
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
        root
        / "datasets"
        / "boundaries"
        / "electoral"
        / "delim=2008"
        / "ac"
        / f"state=in_{eci.lower()}"
        / "all.geojson"
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


# ---------------------------------------------------------------------------
# --threshold flag (PR #_pending_, D.7 universal LGD swap)
# ---------------------------------------------------------------------------


def test_verify_state_accepts_relaxed_threshold(tmp_path: Path) -> None:
    """4 ACs; 2 names match -> 50% parity. Default (0.95) fails; 0.5 passes.

    Mirrors the Assam S03 case where upstream LGD transliterations diverge
    from ECI SoT on ~15% of constituencies (PR #270 D.1 recon).
    """
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
    # Default threshold (0.95) -> fail.
    ok_default, _, _ = vap.verify_state(tmp_path, eci)
    assert not ok_default
    # Relaxed threshold (0.50) -> pass.
    ok_relaxed, errors, stats = vap.verify_state(tmp_path, eci, threshold=0.5)
    assert ok_relaxed, errors
    assert stats["name_parity"] == pytest.approx(0.5)


def test_verify_state_strict_threshold_fails_near_perfect(tmp_path: Path) -> None:
    """20 ACs; 19 match -> 95% parity. Strict (1.0) fails; default (0.95) passes."""
    eci = "S99"
    sot = {n: f"AC{n}" for n in range(1, 21)}
    _write_sot(tmp_path, eci, sot)
    feats = [{"ac_no": n, "ac_name": f"AC{n}"} for n in range(1, 20)]
    feats.append({"ac_no": 20, "ac_name": "DIFFERENT"})
    _write_geojson(tmp_path, eci, feats)
    ok_default, _, _ = vap.verify_state(tmp_path, eci)
    assert ok_default
    ok_strict, errors, _ = vap.verify_state(tmp_path, eci, threshold=1.0)
    assert not ok_strict
    assert any("name parity 95.0% < 100%" in e for e in errors)


def test_main_threshold_flag_relaxes_pass_floor(tmp_path: Path) -> None:
    """CLI surface: --threshold 0.50 lets a 50%-parity state pass with exit 0."""
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
    assert vap.main(["--state", eci, "--root", str(tmp_path)]) == 1
    assert vap.main(
        ["--state", eci, "--root", str(tmp_path), "--threshold", "0.5"],
    ) == 0


def test_main_rejects_out_of_range_threshold(tmp_path: Path) -> None:
    """--threshold must be in [0.0, 1.0]; otherwise return exit code 2."""
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A"})
    _write_geojson(tmp_path, eci, [{"ac_no": 1, "ac_name": "A"}])
    assert vap.main(
        ["--state", eci, "--root", str(tmp_path), "--threshold", "1.5"],
    ) == 2
    assert vap.main(
        ["--state", eci, "--root", str(tmp_path), "--threshold", "-0.1"],
    ) == 2


# ---------------------------------------------------------------------------
# --allow-extras flag (PR #_pending_, D.7 universal LGD swap)
# ---------------------------------------------------------------------------


def test_extras_block_by_default(tmp_path: Path) -> None:
    """Without --allow-extras, snapshot with MORE ac_no than SoT fails.

    Mirrors the LGD-vs-SoT count drift case (e.g. Tamil Nadu S22 LGD 235
    vs SoT 234 — 1 extra pre-bifurcation residue feature).
    """
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A", 2: "B"})
    _write_geojson(
        tmp_path,
        eci,
        [
            {"ac_no": 1, "ac_name": "A"},
            {"ac_no": 2, "ac_name": "B"},
            {"ac_no": 3, "ac_name": "C"},
        ],
    )
    ok, errors, _ = vap.verify_state(tmp_path, eci)
    assert not ok
    assert any("count mismatch" in e for e in errors)
    assert any("ac_no(s) in snapshot but not in SoT" in e for e in errors)


def test_extras_allowed_with_flag(tmp_path: Path) -> None:
    """With allow_extras=True, snapshot may carry +N pre-bifurcation residue.

    These render as no-fill polygons in the citizen-facing map (no ECI election
    result joins to them), which is the explicit D.7 user-accepted concession
    for getting LGD/BharatMaps citation consistency across all 30 elective AC
    states.
    """
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A", 2: "B"})
    _write_geojson(
        tmp_path,
        eci,
        [
            {"ac_no": 1, "ac_name": "A"},
            {"ac_no": 2, "ac_name": "B"},
            {"ac_no": 3, "ac_name": "C"},
        ],
    )
    ok, errors, stats = vap.verify_state(tmp_path, eci, allow_extras=True)
    assert ok, errors
    assert stats["snap_count"] == 3
    assert stats["sot_count"] == 2


def test_undercoverage_still_fails_with_allow_extras(tmp_path: Path) -> None:
    """allow_extras must NOT mask undercoverage (snapshot missing real ACs).

    Citizen-facing risk: if LGD lacks an AC that SoT lists, the choropleth
    would show no polygon for that constituency on a real election event —
    a hole in the map. Gujarat S06 historical case: LGD missing 18 of 182
    ACs (D.1 recon, PR #270).
    """
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A", 2: "B", 3: "C", 4: "D"})
    _write_geojson(
        tmp_path,
        eci,
        [{"ac_no": 1, "ac_name": "A"}, {"ac_no": 2, "ac_name": "B"}],
    )
    ok, errors, _ = vap.verify_state(tmp_path, eci, allow_extras=True)
    assert not ok
    assert any("undercoverage" in e for e in errors)
    assert any("missing from snapshot" in e for e in errors)


def test_main_allow_extras_flag(tmp_path: Path) -> None:
    """CLI surface: --allow-extras lets a +1-extra state pass with exit 0."""
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A", 2: "B"})
    _write_geojson(
        tmp_path,
        eci,
        [
            {"ac_no": 1, "ac_name": "A"},
            {"ac_no": 2, "ac_name": "B"},
            {"ac_no": 3, "ac_name": "C"},
        ],
    )
    # Default (no --allow-extras): fail.
    assert vap.main(["--state", eci, "--root", str(tmp_path)]) == 1
    # With --allow-extras: pass.
    assert vap.main(
        ["--state", eci, "--root", str(tmp_path), "--allow-extras"],
    ) == 0
    # --allow-extras does NOT mask undercoverage.
    _write_geojson(
        tmp_path,
        eci,
        [{"ac_no": 1, "ac_name": "A"}],
    )
    assert vap.main(
        ["--state", eci, "--root", str(tmp_path), "--allow-extras"],
    ) == 1

# ---------------------------------------------------------------------------
# --undercoverage-tolerance flag (PR #_pending_, D.7 universal LGD swap)
# ---------------------------------------------------------------------------


def test_undercoverage_tolerance_accepts_tiny_shortfall(tmp_path: Path) -> None:
    """SoT 100; snap 99 (1% shortfall); tolerance 5% with allow_extras -> pass.

    Mirrors the West Bengal S25 LGD-vs-SoT case: LGD has 293 ACs vs SoT 294
    (1 of 294 = 0.34% shortfall). The missing AC renders as a hole in the
    map for one event; tolerated under D.7 citation-consistency mandate.
    """
    eci = "S99"
    sot = {n: f"AC{n}" for n in range(1, 101)}
    _write_sot(tmp_path, eci, sot)
    feats = [{"ac_no": n, "ac_name": f"AC{n}"} for n in range(1, 100)]
    _write_geojson(tmp_path, eci, feats)
    ok, errors, _ = vap.verify_state(
        tmp_path, eci, allow_extras=True, undercoverage_tolerance=0.05,
    )
    assert ok, errors


def test_undercoverage_tolerance_rejects_big_shortfall(tmp_path: Path) -> None:
    """SoT 100; snap 80 (20% shortfall); tolerance 5% -> still fails.

    Mirrors the Gujarat S06 D.1 historical case: LGD missing 18 of 182
    ACs (~10% shortfall). Must exceed any reasonable D.7 tolerance and
    trigger the safety-net pipeline-revert decision.
    """
    eci = "S99"
    sot = {n: f"AC{n}" for n in range(1, 101)}
    _write_sot(tmp_path, eci, sot)
    feats = [{"ac_no": n, "ac_name": f"AC{n}"} for n in range(1, 81)]
    _write_geojson(tmp_path, eci, feats)
    ok, errors, _ = vap.verify_state(
        tmp_path, eci, allow_extras=True, undercoverage_tolerance=0.05,
    )
    assert not ok
    assert any("undercoverage" in e for e in errors)


def test_main_undercoverage_tolerance_flag(tmp_path: Path) -> None:
    """CLI surface: --undercoverage-tolerance 0.05 lets a 1% shortfall pass."""
    eci = "S99"
    sot = {n: f"AC{n}" for n in range(1, 101)}
    _write_sot(tmp_path, eci, sot)
    feats = [{"ac_no": n, "ac_name": f"AC{n}"} for n in range(1, 100)]
    _write_geojson(tmp_path, eci, feats)
    # Default strict (no flags): fail.
    assert vap.main(["--state", eci, "--root", str(tmp_path)]) == 1
    # With both --allow-extras and --undercoverage-tolerance 0.05: pass.
    assert vap.main(
        [
            "--state", eci, "--root", str(tmp_path),
            "--allow-extras", "--undercoverage-tolerance", "0.05",
        ],
    ) == 0


def test_main_rejects_out_of_range_undercoverage_tolerance(tmp_path: Path) -> None:
    """--undercoverage-tolerance must be in [0.0, 1.0]; otherwise exit 2."""
    eci = "S99"
    _write_sot(tmp_path, eci, {1: "A"})
    _write_geojson(tmp_path, eci, [{"ac_no": 1, "ac_name": "A"}])
    assert vap.main(
        ["--state", eci, "--root", str(tmp_path), "--undercoverage-tolerance", "1.5"],
    ) == 2
    assert vap.main(
        ["--state", eci, "--root", str(tmp_path), "--undercoverage-tolerance", "-0.01"],
    ) == 2