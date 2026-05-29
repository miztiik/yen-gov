"""Unit tests for tools.boundaries.snapshot ac_no_rewrite + additional_filters.

Phase A.1.a (S01 AP LGD swap, 2026-05-29). Per CLAUDE.md section 15 +
Holy Law section 7: real fixtures (hand-built feature dicts + a synthetic
SoT JSON under tmp_path), no mocks. No py7zr dependency.

The `apply_additional_filters` directive lets a single keep-filter spec
(today: `(State_LGD=28 AND st_name='ANDHRA PRADESH')`) be expressed as a
list of single-property filters chained sequentially. Each filter raises
on empty-kept (same fail-loud discipline as `apply_state_filter`).

The `apply_ac_no_rewrite_by_name` directive projects upstream LGD
legacy `ac_no` onto SoT `eci_no` via case/diacritic/reservation-suffix-
folded name matching. Per LGD-golden doctrine
(TODO/20260529-boundary-rip-and-replace-plan.md), the original LGD
`ac_no`, `AC_ID`, and `st_name` are preserved on the feature as
`lgd_legacy_ac_no`, `lgd_ac_id`, `lgd_st_name` so the snapshot is
auditable and reversible if a future PR migrates to LGD `AC_ID` as
the primary join key.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "boundaries"))

import snapshot  # noqa: E402  (after sys.path manipulation)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _feat(
    *,
    state_lgd: int,
    st_name: str,
    ac_no: int,
    ac_name: str,
    ac_id: str,
) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "State_LGD": state_lgd,
            "st_name": st_name,
            "ac_no": ac_no,
            "ac_name": ac_name,
            "AC_ID": ac_id,
        },
        "geometry": {"type": "Point", "coordinates": [80.0, 16.0]},
    }


@pytest.fixture
def ap_lgd_slice() -> list[dict]:
    """Simulated `State_LGD=28` slice from the LGD release.

    Contains 5 features:
    - 3 AP post-2014 names at LGD's legacy pre-bifurcation ac_no (175 / 176 / 294)
    - 1 placeholder at ac_no=0 (empty name)
    - 1 Yanam enclave at st_name='PUDUCHERRY' that the `additional_filters`
      step must drop (Yanam appears under State_LGD=28 because the LGD
      release records it under AP's State_LGD even though st_name is
      Puducherry; mirrors actual LGD behaviour per
      notes/2026-05-29-phase-b-verdict-correction.md).
    """
    return [
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=175, ac_name="Ichchapuram", ac_id="ID-ICH",
        ),
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=176, ac_name="Palasa", ac_id="ID-PAL",
        ),
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=294, ac_name="Kuppam", ac_id="ID-KUP",
        ),
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=0, ac_name="", ac_id="ID-EMPTY",
        ),
        _feat(
            state_lgd=28, st_name="PUDUCHERRY",
            ac_no=2, ac_name="Yanam", ac_id="ID-YAN",
        ),
    ]


@pytest.fixture
def sot_ap(tmp_path: Path) -> Path:
    """Hand-built S01 AP SoT under tmp_path."""
    sot = {
        "$schema_version": "4.1",
        "state": "S01",
        "body": "AC",
        "status": "provisional",
        "constituencies": [
            {"eci_no": 1, "name": "Ichchapuram", "reservation": "GEN"},
            {"eci_no": 2, "name": "Palasa", "reservation": "GEN"},
            {"eci_no": 175, "name": "Kuppam", "reservation": "GEN"},
        ],
    }
    sot_path = (
        tmp_path
        / "datasets"
        / "reference"
        / "in"
        / "states"
        / "S01"
        / "constituencies.json"
    )
    sot_path.parent.mkdir(parents=True, exist_ok=True)
    sot_path.write_text(json.dumps(sot), encoding="utf-8")
    return tmp_path  # repo_root


# ---------------------------------------------------------------------------
# apply_additional_filters
# ---------------------------------------------------------------------------


def test_additional_filters_chains_single_property_specs(
    ap_lgd_slice: list[dict],
) -> None:
    """Two-spec chain narrows State_LGD=28 then st_name='ANDHRA PRADESH'.

    Yanam (PUDUCHERRY) drops at the second spec; the 4 AP features survive.
    """
    # First spec is a no-op here (slice already State_LGD=28); second
    # drops Yanam. This shape mirrors the real S01 pipeline.json entry.
    kept, dropped_per_filter = snapshot.apply_additional_filters(
        ap_lgd_slice,
        [
            {"property": "State_LGD", "equals": 28},
            {"property": "st_name", "equals": "ANDHRA PRADESH"},
        ],
    )
    assert len(kept) == 4
    assert len(dropped_per_filter) == 2
    assert len(dropped_per_filter[0]) == 0  # already State_LGD=28
    assert len(dropped_per_filter[1]) == 1  # Yanam dropped
    assert dropped_per_filter[1][0]["properties"]["ac_name"] == "Yanam"
    assert all(f["properties"]["st_name"] == "ANDHRA PRADESH" for f in kept)


def test_additional_filters_raises_on_intermediate_empty() -> None:
    """If any spec narrows to zero kept, raise (fail-loud config error)."""
    features = [
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=1, ac_name="A", ac_id="X",
        ),
    ]
    with pytest.raises(ValueError, match="state_filter"):
        snapshot.apply_additional_filters(
            features,
            [{"property": "st_name", "equals": "TELANGANA"}],
        )


def test_additional_filters_empty_specs_is_noop(ap_lgd_slice: list[dict]) -> None:
    """An empty list of specs is a valid no-op (caller didn't request any)."""
    kept, dropped_per_filter = snapshot.apply_additional_filters(
        ap_lgd_slice, []
    )
    assert kept == ap_lgd_slice
    assert dropped_per_filter == []


# ---------------------------------------------------------------------------
# apply_ac_no_rewrite_by_name
# ---------------------------------------------------------------------------


def test_rewrite_projects_ac_no_to_sot_eci_no(
    ap_lgd_slice: list[dict], sot_ap: Path,
) -> None:
    """Three named features in slice map to SoT eci_no 1 / 2 / 175.

    The empty-placeholder ac_no=0 and Yanam (not in SoT) get dropped.
    The 3 retained features get `ac_no` rewritten + LGD provenance preserved.
    """
    # Use only the 3 AP features + 1 empty placeholder (drop Yanam upstream
    # via additional_filters in the real pipeline; here we exercise the
    # rewrite step in isolation).
    ap_only = [f for f in ap_lgd_slice if f["properties"]["st_name"] == "ANDHRA PRADESH"]
    kept, dropped = snapshot.apply_ac_no_rewrite_by_name(
        ap_only,
        {
            "method": "by_name_to_sot_eci_no",
            "sot_ref": "datasets/reference/in/states/S01/constituencies.json",
        },
        repo_root=sot_ap,
    )
    assert len(kept) == 3
    assert len(dropped) == 1  # empty placeholder
    by_name = {f["properties"]["ac_name"]: f for f in kept}
    assert by_name["Ichchapuram"]["properties"]["ac_no"] == 1
    assert by_name["Palasa"]["properties"]["ac_no"] == 2
    assert by_name["Kuppam"]["properties"]["ac_no"] == 175
    # LGD provenance preserved on every retained feature
    ich = by_name["Ichchapuram"]["properties"]
    assert ich["lgd_legacy_ac_no"] == 175
    assert ich["lgd_ac_id"] == "ID-ICH"
    assert ich["lgd_st_name"] == "ANDHRA PRADESH"
    kup = by_name["Kuppam"]["properties"]
    assert kup["lgd_legacy_ac_no"] == 294
    assert kup["lgd_ac_id"] == "ID-KUP"


def test_rewrite_folds_case_and_reservation_suffix(
    sot_ap: Path,
) -> None:
    """Snap name 'ICHCHAPURAM' (no suffix -> GEN) should match SoT
    'Ichchapuram' (reservation=GEN) after case-fold."""
    features = [
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=175, ac_name="ICHCHAPURAM", ac_id="ID-ICH",
        ),
    ]
    kept, dropped = snapshot.apply_ac_no_rewrite_by_name(
        features,
        {
            "method": "by_name_to_sot_eci_no",
            "sot_ref": "datasets/reference/in/states/S01/constituencies.json",
        },
        repo_root=sot_ap,
    )
    assert len(kept) == 1
    assert len(dropped) == 0
    assert kept[0]["properties"]["ac_no"] == 1


def test_rewrite_uses_compound_name_reservation_key(tmp_path: Path) -> None:
    """Two LGD features with the same normalised name but different
    parenthesised reservation suffixes ('Gannavaram' GEN vs
    'Gannavaram (SC)' SC) map to DIFFERENT SoT eci_no values via the
    compound (name, reservation) key.

    This mirrors the actual S01 AP case: LGD's pre-bifurcation slice has
    Gannavaram (Krishna district, no suffix -> GEN) AND Gannavaram (SC)
    (East Godavari district); post-2014 SoT has eci_no=71 Gannavaram
    (GEN) AND eci_no=46 Gannavaram (SC).
    """
    sot = {
        "$schema_version": "4.1",
        "state": "S01",
        "body": "AC",
        "status": "provisional",
        "constituencies": [
            {"eci_no": 46, "name": "Gannavaram", "reservation": "SC"},
            {"eci_no": 71, "name": "Gannavaram", "reservation": "GEN"},
        ],
    }
    sot_path = (
        tmp_path / "datasets" / "reference" / "in" / "states" / "S01"
        / "constituencies.json"
    )
    sot_path.parent.mkdir(parents=True, exist_ok=True)
    sot_path.write_text(json.dumps(sot), encoding="utf-8")
    features = [
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=190, ac_name="Gannavaram", ac_id="ID-A",
        ),
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=165, ac_name="Gannavaram (SC)", ac_id="ID-B",
        ),
    ]
    kept, dropped = snapshot.apply_ac_no_rewrite_by_name(
        features,
        {
            "method": "by_name_to_sot_eci_no",
            "sot_ref": "datasets/reference/in/states/S01/constituencies.json",
        },
        repo_root=tmp_path,
    )
    assert len(kept) == 2
    assert len(dropped) == 0
    by_legacy = {f["properties"]["lgd_legacy_ac_no"]: f for f in kept}
    assert by_legacy[190]["properties"]["ac_no"] == 71  # GEN
    assert by_legacy[165]["properties"]["ac_no"] == 46  # SC


def test_rewrite_reservation_mismatch_drops_feature(tmp_path: Path) -> None:
    """If LGD ac_name carries '(SC)' but SoT only has the name as GEN, the
    compound key (name, SC) does not match (name, GEN); feature drops.

    Real-world case: pre-2014 reservation tag differs from post-2014.
    Dropping is the honest behaviour (the constituency boundary is no
    longer applicable to the same eci_no)."""
    sot = {
        "$schema_version": "4.1",
        "state": "S01",
        "body": "AC",
        "status": "provisional",
        "constituencies": [
            {"eci_no": 1, "name": "Madakasira", "reservation": "GEN"},
        ],
    }
    sot_path = (
        tmp_path / "datasets" / "reference" / "in" / "states" / "S01"
        / "constituencies.json"
    )
    sot_path.parent.mkdir(parents=True, exist_ok=True)
    sot_path.write_text(json.dumps(sot), encoding="utf-8")
    features = [
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=275, ac_name="Madakasira (SC)", ac_id="ID-X",
        ),
    ]
    with pytest.raises(ValueError, match="zero matches"):
        snapshot.apply_ac_no_rewrite_by_name(
            features,
            {
                "method": "by_name_to_sot_eci_no",
                "sot_ref": "datasets/reference/in/states/S01/constituencies.json",
            },
            repo_root=tmp_path,
        )


def test_rewrite_raises_when_zero_matches(sot_ap: Path) -> None:
    """If every feature drops, raise (the slice is fundamentally wrong-shape)."""
    features = [
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=1, ac_name="NotARealName", ac_id="ID-X",
        ),
    ]
    with pytest.raises(ValueError, match="zero matches"):
        snapshot.apply_ac_no_rewrite_by_name(
            features,
            {
                "method": "by_name_to_sot_eci_no",
                "sot_ref": "datasets/reference/in/states/S01/constituencies.json",
            },
            repo_root=sot_ap,
        )


def test_rewrite_raises_on_unsupported_method(sot_ap: Path) -> None:
    features = [
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=1, ac_name="Ichchapuram", ac_id="ID-X",
        ),
    ]
    with pytest.raises(ValueError, match="not supported"):
        snapshot.apply_ac_no_rewrite_by_name(
            features,
            {
                "method": "by_some_other_method",
                "sot_ref": "datasets/reference/in/states/S01/constituencies.json",
            },
            repo_root=sot_ap,
        )


def test_rewrite_raises_when_sot_missing(tmp_path: Path) -> None:
    features = [
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=1, ac_name="Ichchapuram", ac_id="ID-X",
        ),
    ]
    with pytest.raises(FileNotFoundError, match="sot_ref not found"):
        snapshot.apply_ac_no_rewrite_by_name(
            features,
            {
                "method": "by_name_to_sot_eci_no",
                "sot_ref": "datasets/reference/in/states/S99/constituencies.json",
            },
            repo_root=tmp_path,
        )


def test_rewrite_raises_on_duplicate_sot_keys(tmp_path: Path) -> None:
    """If SoT has two entries with the same (normalised name, reservation)
    compound key, the lookup map is ambiguous; raise at SoT-load time.

    SoT models reservation as identity; (Gannavaram, GEN) is one
    constituency and (Gannavaram, SC) is another. But two entries both
    keyed (Gannavaram, GEN) is malformed."""
    sot = {
        "$schema_version": "4.1",
        "state": "S01",
        "body": "AC",
        "status": "provisional",
        "constituencies": [
            {"eci_no": 1, "name": "Ichchapuram", "reservation": "GEN"},
            {"eci_no": 2, "name": "ICHCHAPURAM", "reservation": "GEN"},
        ],
    }
    sot_path = (
        tmp_path / "datasets" / "reference" / "in" / "states" / "S01"
        / "constituencies.json"
    )
    sot_path.parent.mkdir(parents=True, exist_ok=True)
    sot_path.write_text(json.dumps(sot), encoding="utf-8")
    features = [
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=1, ac_name="Ichchapuram", ac_id="ID-X",
        ),
    ]
    with pytest.raises(ValueError, match="duplicate \\(name, reservation\\)"):
        snapshot.apply_ac_no_rewrite_by_name(
            features,
            {
                "method": "by_name_to_sot_eci_no",
                "sot_ref": "datasets/reference/in/states/S01/constituencies.json",
            },
            repo_root=tmp_path,
        )


def test_rewrite_raises_on_duplicate_snap_names_for_same_sot(
    sot_ap: Path,
) -> None:
    """If two snap features map to the same SoT eci_no (e.g. upstream
    accidentally has two 'Ichchapuram' entries), raise — we can't pick one."""
    features = [
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=175, ac_name="Ichchapuram", ac_id="ID-A",
        ),
        _feat(
            state_lgd=28, st_name="ANDHRA PRADESH",
            ac_no=176, ac_name="ICHCHAPURAM", ac_id="ID-B",
        ),
    ]
    with pytest.raises(ValueError, match="duplicate eci_no"):
        snapshot.apply_ac_no_rewrite_by_name(
            features,
            {
                "method": "by_name_to_sot_eci_no",
                "sot_ref": "datasets/reference/in/states/S01/constituencies.json",
            },
            repo_root=sot_ap,
        )
