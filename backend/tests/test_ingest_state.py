"""Tests for the committed year-checkpoint receipt (Row 2 / plan D4).

Covers the three Row 2 gates -- skip iff raw-hash equal, a changed hash on an
OLD year forces re-process, a skip advances the staleness field -- plus the
load/write round-trip and schema stamping. Per the CLAUDE.md anti-pattern these
never touch the real corpus; every root is a ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from yen_gov.canonical.ingest import state
from yen_gov.core.schema_registry import schema_version

_SLUG = "rbi-handbook"
_T0 = "2026-01-01T00:00:00Z"
_T1 = "2026-02-01T00:00:00Z"
_T2 = "2026-03-01T00:00:00Z"


def _raw(year: int) -> bytes:
    return f"raw-payload-{year}".encode("utf-8")


def _build_receipt(years: range, *, last_checked: str = _T0) -> dict:
    """A completed checkpoint covering ``years`` (each hashed from ``_raw``)."""
    cp = state.empty_checkpoint(_SLUG, spec_version="v1")
    for year in years:
        cp = state.advance_year(
            cp,
            year=year,
            raw_payload=_raw(year),
            completed=True,
            last_checked=last_checked,
        )
    return cp


# --------------------------------------------------------------------------- #
# Skip predicate                                                              #
# --------------------------------------------------------------------------- #


def test_skip_when_raw_hash_unchanged():
    cp = _build_receipt(range(2018, 2023))
    assert state.should_skip_year(cp, 2019, _raw(2019)) is True


def test_no_skip_when_raw_hash_changed():
    cp = _build_receipt(range(2018, 2023))
    assert state.should_skip_year(cp, 2019, b"raw-payload-2019-REVISED") is False


def test_no_skip_for_new_year():
    cp = _build_receipt(range(2018, 2023))
    assert state.should_skip_year(cp, 2023, _raw(2023)) is False


def test_no_skip_for_incomplete_year_resume():
    """A failed mid-run leaves completed=False -> --resume re-processes it."""
    cp = state.empty_checkpoint(_SLUG, spec_version="v1")
    cp = state.advance_year(
        cp, year=2020, raw_payload=_raw(2020), completed=False, last_checked=_T0
    )
    assert state.should_skip_year(cp, 2020, _raw(2020)) is False


# --------------------------------------------------------------------------- #
# Re-open on revision                                                         #
# --------------------------------------------------------------------------- #


def test_changed_hash_reopens_and_records_new_hash():
    cp = _build_receipt(range(2018, 2023))
    old_hash = state.find_year(cp, 2019)["raw_sha256"]

    # Publisher revised 2019: the predicate refuses to skip, caller re-processes.
    assert state.should_skip_year(cp, 2019, b"raw-payload-2019-REVISED") is False
    cp = state.advance_year(
        cp,
        year=2019,
        raw_payload=b"raw-payload-2019-REVISED",
        completed=True,
        last_checked=_T2,
        estimate_status="revised",
    )
    entry = state.find_year(cp, 2019)
    assert entry["raw_sha256"] == state.hash_payload(b"raw-payload-2019-REVISED")
    assert entry["raw_sha256"] != old_hash
    assert entry["estimate_status"] == "revised"


# --------------------------------------------------------------------------- #
# Staleness advances on a skip                                                #
# --------------------------------------------------------------------------- #


def test_touch_advances_staleness_without_touching_hash():
    cp = _build_receipt(range(2018, 2023), last_checked=_T0)
    before = state.find_year(cp, 2019)
    cp = state.touch_year(cp, year=2019, last_checked=_T1)
    after = state.find_year(cp, 2019)

    assert after["last_checked"] == _T1
    assert after["last_checked"] > before["last_checked"]
    # the payload identity is untouched by a skip
    assert after["raw_sha256"] == before["raw_sha256"]
    assert after["completed"] is True


def test_touch_unknown_year_raises():
    cp = _build_receipt(range(2018, 2023))
    try:
        state.touch_year(cp, year=1999, last_checked=_T1)
    except ValueError as exc:
        assert "1999" in str(exc)
    else:  # pragma: no cover - the raise is the contract
        raise AssertionError("touch_year on an unrecorded year must raise")


def test_mutators_do_not_mutate_input():
    cp = _build_receipt(range(2018, 2023))
    snapshot = json.dumps(cp, sort_keys=True)
    state.advance_year(cp, year=2019, raw_payload=b"x", completed=True, last_checked=_T1)
    state.touch_year(cp, year=2019, last_checked=_T1)
    assert json.dumps(cp, sort_keys=True) == snapshot


# --------------------------------------------------------------------------- #
# Oracle: receipt for {2018..2022}; 2019 skipped on match, forced on change,   #
# staleness still advances on a skip.                                          #
# --------------------------------------------------------------------------- #


def test_oracle_2019_skip_reopen_and_staleness(tmp_path: Path):
    cp = _build_receipt(range(2018, 2023), last_checked=_T0)

    # (a) hash MATCH -> 2019 is skipped; the skip still advances staleness.
    assert state.should_skip_year(cp, 2019, _raw(2019)) is True
    before = state.find_year(cp, 2019)["last_checked"]
    cp = state.touch_year(cp, year=2019, last_checked=_T1)
    after = state.find_year(cp, 2019)
    assert after["last_checked"] == _T1 and after["last_checked"] > before
    assert after["raw_sha256"] == state.hash_payload(_raw(2019))  # unchanged
    # other years are untouched by the 2019 skip
    assert state.find_year(cp, 2020)["last_checked"] == _T0

    # (b) hash CHANGE on the OLD year 2019 -> forced re-process (no skip).
    assert state.should_skip_year(cp, 2019, b"raw-payload-2019-REVISED") is False
    cp = state.advance_year(
        cp,
        year=2019,
        raw_payload=b"raw-payload-2019-REVISED",
        completed=True,
        last_checked=_T2,
    )
    assert state.find_year(cp, 2019)["raw_sha256"] == state.hash_payload(
        b"raw-payload-2019-REVISED"
    )

    # exactly the five years, in ascending order
    assert [e["year"] for e in cp["years"]] == [2018, 2019, 2020, 2021, 2022]


# --------------------------------------------------------------------------- #
# Round-trip + schema stamping                                                #
# --------------------------------------------------------------------------- #


def test_load_absent_returns_empty_scaffold(tmp_path: Path):
    cp = state.load("never-run", tmp_path)
    assert cp == {"adapter_slug": "never-run", "spec_version": "", "years": []}


def test_write_then_load_round_trips(tmp_path: Path):
    cp = _build_receipt(range(2018, 2021))
    path = state.write(cp, tmp_path)
    assert path == state.checkpoint_path(_SLUG, tmp_path)
    assert path.is_file()

    reloaded = state.load(_SLUG, tmp_path)
    assert reloaded["adapter_slug"] == _SLUG
    assert reloaded["spec_version"] == "v1"
    assert [e["year"] for e in reloaded["years"]] == [2018, 2019, 2020]


def test_write_stamps_schema_and_validates(tmp_path: Path):
    cp = _build_receipt(range(2018, 2023))
    path = state.write(cp, tmp_path)
    written = json.loads(path.read_text(encoding="utf-8"))

    assert written["$schema"] == "./ingest-state.schema.json"
    assert written["$schema_version"] == schema_version("ingest-state.schema.json")

    schema = json.loads(
        (
            Path(state.__file__).resolve().parents[4]
            / "datasets"
            / "schemas"
            / "ingest-state.schema.json"
        ).read_text(encoding="utf-8")
    )
    assert list(Draft202012Validator(schema).iter_errors(written)) == []


def test_written_path_uses_posix_separators(tmp_path: Path):
    cp = _build_receipt(range(2018, 2020))
    path = state.write(cp, tmp_path)
    rel = path.relative_to(tmp_path).as_posix()
    assert rel == "datasets/_ops/ingest-state/rbi-handbook.json"
    assert "\\" not in rel
