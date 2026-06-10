"""Tests for B2a.6 entities/electoral.csv emitter (sub-plan)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.electoral_csv import FILE_CLASS, emit


def _stage(path: Path, key: str, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: entries}), encoding="utf-8")


def _state(**overrides) -> dict:
    base = {
        "lgd_state_id": 32,
        "lgd_name": "Tamil Nadu",
        "lgd_name_short": "Tamil Nadu",
        "iso_alpha": "IN-TN",
        "slug": "tamil-nadu",
        "eci_st_code": "S22",
    }
    base.update(overrides)
    return base


def _pc(**overrides) -> dict:
    base = {
        "lgd_pc_id": 500,
        "lgd_state_id": 32,
        "pc_name": "Chennai South",
        "slug": "chennai-south",
    }
    base.update(overrides)
    return base


def _ac(**overrides) -> dict:
    base = {
        "lgd_ac_id": 4000,
        "lgd_state_id": 32,
        "lgd_pc_id": 500,
        "ac_name": "Mylapore",
        "slug": "mylapore",
    }
    base.update(overrides)
    return base


def _stage_triple(
    tmp_path: Path,
    states: list[dict],
    pcs: list[dict],
    acs: list[dict],
) -> tuple[Path, Path, Path]:
    s = tmp_path / "lgd_states.json"
    p = tmp_path / "lgd_pcs.json"
    a = tmp_path / "lgd_acs.json"
    _stage(s, "states", states)
    _stage(p, "pcs", pcs)
    _stage(a, "acs", acs)
    return s, a, p


def test_emit_minimal_pc_and_ac(tmp_path):
    s, a, p = _stage_triple(tmp_path, [_state()], [_pc()], [_ac()])
    out = tmp_path / "datasets" / "data" / "entities" / "electoral.csv"
    emit(lgd_states_json=s, lgd_acs_json=a, lgd_pcs_json=p, out_path=out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation"
    # 1 PC + 1 AC = 2 rows
    assert len(lines) == 3
    body = "\n".join(lines[1:])
    # The legacy taxonomy emitter leaves eci_no + aliases empty (filled only by
    # the B2b.5.0c snapshot emitter); it is retired in 0d-del.
    assert "IN-AC-2008-tamil-nadu-4000,Mylapore,ac,2008,tamil-nadu,IN-PC-2008-tamil-nadu-500,,," in body
    assert "IN-PC-2008-tamil-nadu-500,Chennai South,pc,2008,tamil-nadu,tamil-nadu,,," in body


def test_emit_disambiguates_ac_slug_collision_within_state(tmp_path):
    """Real-world: 12 ``(lgd_state_id, slug)`` AC duplicates exist; integer
    lgd_ac_id in the id guarantees uniqueness."""
    pcs = [_pc()]
    acs = [
        _ac(lgd_ac_id=10, slug="shahpura"),
        _ac(lgd_ac_id=11, slug="shahpura"),
    ]
    s, a, p = _stage_triple(tmp_path, [_state()], pcs, acs)
    out = tmp_path / "out.csv"
    emit(lgd_states_json=s, lgd_acs_json=a, lgd_pcs_json=p, out_path=out)
    body = out.read_text(encoding="utf-8")
    assert "IN-AC-2008-tamil-nadu-10," in body
    assert "IN-AC-2008-tamil-nadu-11," in body


def test_emit_rejects_unknown_state_fk_on_pc(tmp_path):
    s, a, p = _stage_triple(tmp_path, [_state()], [_pc(lgd_state_id=999)], [])
    with pytest.raises(ValueError, match="pc 500 references unknown lgd_state_id"):
        emit(lgd_states_json=s, lgd_acs_json=a, lgd_pcs_json=p, out_path=tmp_path / "out.csv")


def test_emit_rejects_unknown_state_fk_on_ac(tmp_path):
    s, a, p = _stage_triple(tmp_path, [_state()], [_pc()], [_ac(lgd_state_id=999)])
    with pytest.raises(ValueError, match="ac 4000 references unknown lgd_state_id"):
        emit(lgd_states_json=s, lgd_acs_json=a, lgd_pcs_json=p, out_path=tmp_path / "out.csv")


def test_emit_rejects_unknown_pc_fk_on_ac(tmp_path):
    s, a, p = _stage_triple(tmp_path, [_state()], [_pc()], [_ac(lgd_pc_id=999)])
    with pytest.raises(ValueError, match="ac 4000 references unknown lgd_pc_id"):
        emit(lgd_states_json=s, lgd_acs_json=a, lgd_pcs_json=p, out_path=tmp_path / "out.csv")


def test_emit_rejects_missing_pc_name(tmp_path):
    bad = _pc()
    bad.pop("pc_name")
    s, a, p = _stage_triple(tmp_path, [_state()], [bad], [])
    with pytest.raises(ValueError, match="missing 'pc_name'"):
        emit(lgd_states_json=s, lgd_acs_json=a, lgd_pcs_json=p, out_path=tmp_path / "out.csv")


def test_emit_rejects_duplicate_pc_id(tmp_path):
    s, a, p = _stage_triple(tmp_path, [_state()], [_pc(), _pc()], [])
    with pytest.raises(ValueError, match="duplicate pc entity_id"):
        emit(lgd_states_json=s, lgd_acs_json=a, lgd_pcs_json=p, out_path=tmp_path / "out.csv")


def test_emit_rejects_double_underscore_in_state_slug(tmp_path):
    s, a, p = _stage_triple(
        tmp_path,
        [_state(slug="bad__slug")],
        [_pc()],
        [],
    )
    with pytest.raises(ValueError, match="must not contain '__'"):
        emit(lgd_states_json=s, lgd_acs_json=a, lgd_pcs_json=p, out_path=tmp_path / "out.csv")


def test_emitted_csv_passes_validator_with_geo_fk_closure(tmp_path):
    """End-to-end: emit a tiny geo.csv (FK predecessor) + electoral.csv and
    confirm the cross-file FK validator accepts the pair (sub-row gate
    `fk-validator`).

    PR-E-R (2026-06-10): the B2a.6 legacy emitter (this module) does not
    populate ``reservation``; the new Tier-B rule
    ``_check_electoral_reservation_populated`` correctly rejects the
    emitted file. The B2b.5.0c emitter is the in-force writer for the
    real electoral.csv on disk + the PR-E-R reservation backfill is
    applied via ``_run_electoral_reservation_backfill``. This test now
    confirms the FK validator path works END-TO-END EXCEPT for the new
    reservation requirement (which is enforced separately by the Tier-A
    regression test_electoral_reservation_populated).
    """
    from yen_gov.canonical.seed.geo_csv import emit as geo_emit
    from yen_gov.canonical.csv_validator import CsvValidationError

    repo_root = tmp_path
    states_src = tmp_path / "lgd_states.json"
    districts_src = tmp_path / "lgd_districts.json"
    states_src.parent.mkdir(parents=True, exist_ok=True)
    states_src.write_text(
        json.dumps({"states": [_state()]}), encoding="utf-8"
    )
    districts_src.write_text(json.dumps({"districts": []}), encoding="utf-8")
    geo_out = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo_emit(
        lgd_states_json=states_src,
        lgd_districts_json=districts_src,
        out_path=geo_out,
    )

    s, a, p = _stage_triple(tmp_path, [_state()], [_pc()], [_ac()])
    out = repo_root / "datasets" / "data" / "entities" / "electoral.csv"
    emit(lgd_states_json=s, lgd_acs_json=a, lgd_pcs_json=p, out_path=out)
    # The legacy emitter writes NULL reservation; the new Tier-B rule
    # rejects this. The structural fix lives in
    # _run_electoral_reservation_backfill (PR-E-R), not in this legacy
    # emitter. Assert the rejection IS surfaced so a future agent can
    # see the contract gap.
    with pytest.raises(CsvValidationError, match="missing reservation"):
        validate_csv(path=out, file_class=FILE_CLASS, repo_root=repo_root)


def test_emit_pc_sort_deterministic(tmp_path):
    """Writer sorts by PK (entity_id). PCs interleave with ACs alphabetically
    because both share the same PK column; this confirms determinism."""
    s, a, p = _stage_triple(
        tmp_path,
        [_state()],
        [_pc(lgd_pc_id=2, pc_name="B"), _pc(lgd_pc_id=1, pc_name="A")],
        [],
    )
    out = tmp_path / "out.csv"
    emit(lgd_states_json=s, lgd_acs_json=a, lgd_pcs_json=p, out_path=out)
    body = out.read_text(encoding="utf-8").splitlines()[1:]
    # IN-PC-2008-tamil-nadu-1 sorts before -2 lexicographically.
    assert body[0].startswith("IN-PC-2008-tamil-nadu-1,")
    assert body[1].startswith("IN-PC-2008-tamil-nadu-2,")
