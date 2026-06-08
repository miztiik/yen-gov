"""Tests for the B2b.5.0b state_codes.csv emitter + the ISO transcription seed.

No mocks (Holy Law #7): the emitter runs against tmp_path fixtures shaped like
the real committed inputs (the LGD snapshot states.csv + the ISO seed). One test
also runs the emitter against the REAL committed inputs to lock the
iso-seed-coverage invariant on the live 36-state set.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.state_codes_csv import FILE_CLASS, emit

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_SNAPSHOT = REPO_ROOT / "datasets" / "reference" / "lgd" / "states.csv"
REAL_ISO_SEED = REPO_ROOT / "datasets" / "data" / "entities" / "state_iso_seed.csv"


def _write(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow(r)
    return path


def _fixture_inputs(tmp_path: Path) -> tuple[Path, Path]:
    snapshot = _write(
        tmp_path / "states.csv",
        ["lgd_state_code", "state_name", "state_name_local",
         "census_2001_code", "census_2011_code", "kind"],
        [
            ["28", "Andhra Pradesh", "ANDHRA PRADESH", "28", "28", "state"],
            # post-2011 entity: empty census (did not exist at either census)
            ["36", "Telangana", "TELANGANA", "", "", "state"],
            ["4", "Chandigarh", "CHANDIGARH", "4", "4", "ut"],
        ],
    )
    iso_seed = _write(
        tmp_path / "state-iso-seed.csv",
        ["lgd_state_code", "iso_3166_2", "slug", "aliases"],
        [
            ["28", "IN-AP", "andhra-pradesh", ""],
            ["36", "IN-TG", "telangana", ""],
            ["4", "IN-CH", "chandigarh", ""],
        ],
    )
    return snapshot, iso_seed


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_emits_one_row_per_state_joined_on_lgd_code(tmp_path):
    snapshot, iso_seed = _fixture_inputs(tmp_path)
    out = tmp_path / "state_codes.csv"
    emit(lgd_snapshot_states_csv=snapshot, state_iso_seed_csv=iso_seed, out_path=out)
    rows = _read(out)
    assert len(rows) == 3
    by_id = {r["lgd_state_id"]: r for r in rows}
    ap = by_id["28"]
    assert ap["lgd_name"] == "Andhra Pradesh"
    assert ap["iso_3166_2"] == "IN-AP"
    assert ap["kind"] == "state"
    assert ap["slug"] == "andhra-pradesh"
    assert ap["census_2011_code"] == "28"


def test_post_2011_entity_carries_empty_census(tmp_path):
    """Telangana (2014) has empty census codes - never a literal 0 that a JOIN matches."""
    snapshot, iso_seed = _fixture_inputs(tmp_path)
    out = tmp_path / "state_codes.csv"
    emit(lgd_snapshot_states_csv=snapshot, state_iso_seed_csv=iso_seed, out_path=out)
    tg = {r["lgd_state_id"]: r for r in _read(out)}["36"]
    assert tg["census_2001_code"] == ""
    assert tg["census_2011_code"] == ""


def test_iso_seed_coverage_mismatch_fails_loud(tmp_path):
    """A snapshot state with no ISO seed row fails (iso-seed-coverage gate)."""
    snapshot = _write(
        tmp_path / "states.csv",
        ["lgd_state_code", "state_name", "state_name_local",
         "census_2001_code", "census_2011_code", "kind"],
        [["28", "Andhra Pradesh", "ANDHRA PRADESH", "28", "28", "state"],
         ["99", "Newland", "NEWLAND", "", "", "ut"]],
    )
    iso_seed = _write(
        tmp_path / "state-iso-seed.csv",
        ["lgd_state_code", "iso_3166_2", "slug", "aliases"],
        [["28", "IN-AP", "andhra-pradesh", ""]],
    )
    out = tmp_path / "state_codes.csv"
    with pytest.raises(ValueError, match="iso-seed-coverage"):
        emit(lgd_snapshot_states_csv=snapshot, state_iso_seed_csv=iso_seed, out_path=out)


def test_emitter_output_is_deterministic(tmp_path):
    snapshot, iso_seed = _fixture_inputs(tmp_path)
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    emit(lgd_snapshot_states_csv=snapshot, state_iso_seed_csv=iso_seed, out_path=a)
    emit(lgd_snapshot_states_csv=snapshot, state_iso_seed_csv=iso_seed, out_path=b)
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.skipif(
    not (REAL_SNAPSHOT.exists() and REAL_ISO_SEED.exists()),
    reason="real committed inputs absent",
)
def test_real_inputs_emit_and_validate(tmp_path):
    """The real 36-state snapshot + ISO seed emit a contract-valid file (live iso-seed-coverage)."""
    out = tmp_path / "state_codes.csv"
    emit(
        lgd_snapshot_states_csv=REAL_SNAPSHOT,
        state_iso_seed_csv=REAL_ISO_SEED,
        out_path=out,
    )
    validate_csv(path=out, file_class=FILE_CLASS, repo_root=REPO_ROOT)
    rows = _read(out)
    assert len(rows) == 36
    # Post-2011 entities carry empty census (never a literal 0).
    by_id = {r["lgd_state_id"]: r for r in rows}
    for new_state in ("36", "37", "38"):  # Telangana, Ladakh, DNH-DD
        assert by_id[new_state]["census_2011_code"] == ""
    # Every row carries a non-empty ISO code + slug + kind.
    for r in rows:
        assert r["iso_3166_2"].startswith("IN-")
        assert r["slug"]
        assert r["kind"] in ("state", "ut")
