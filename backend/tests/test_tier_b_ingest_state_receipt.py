"""Tier-B tests for ``tier_b_ingest_state_receipt`` (Row 2 / plan D4).

The check validates committed ``datasets/_ops/ingest-state/*.json`` receipts
against ``ingest-state.schema.json`` plus the cross-row invariants the schema
cannot express (filename stem == adapter_slug, year-unique). Per the CLAUDE.md
anti-pattern these never walk the real corpus -- every root is a ``tmp_path``
with the schema staged in and fixtures authored by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.canonical.ingest import state
from yen_gov.validate import tier_b_ingest_state_receipt

_REAL_SCHEMA = (
    Path(state.__file__).resolve().parents[4]
    / "datasets"
    / "schemas"
    / "ingest-state.schema.json"
)


def _stage_schema(root: Path) -> None:
    dest = root / "datasets" / "schemas" / "ingest-state.schema.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(_REAL_SCHEMA.read_text(encoding="utf-8"), encoding="utf-8")


def _write_receipt(root: Path, slug: str, payload: dict) -> Path:
    """Write a raw checkpoint dict verbatim (bypasses the writer's guarantees)."""
    path = root / "datasets" / "_ops" / "ingest-state" / f"{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _good_payload(slug: str = "rbi-handbook") -> dict:
    return {
        "$schema": "./ingest-state.schema.json",
        "$schema_version": "1.0",
        "adapter_slug": slug,
        "spec_version": "v1",
        "years": [
            {
                "year": 2018,
                "raw_sha256": "a" * 64,
                "completed": True,
                "last_checked": "2026-01-01T00:00:00Z",
            },
            {
                "year": 2019,
                "raw_sha256": "b" * 64,
                "completed": True,
                "last_checked": "2026-02-01T00:00:00Z",
                "estimate_status": "revised",
            },
        ],
    }


# --------------------------------------------------------------------------- #
# Good fixtures                                                               #
# --------------------------------------------------------------------------- #


def test_no_op_when_dir_absent(tmp_path: Path):
    assert tier_b_ingest_state_receipt(tmp_path) == []


def test_accepts_a_valid_receipt(tmp_path: Path):
    _stage_schema(tmp_path)
    _write_receipt(tmp_path, "rbi-handbook", _good_payload())
    assert tier_b_ingest_state_receipt(tmp_path) == []


def test_accepts_a_receipt_written_by_state_write(tmp_path: Path):
    """The writer's own output must satisfy its own Tier-B gate."""
    _stage_schema(tmp_path)
    cp = state.empty_checkpoint("nfhs", spec_version="v2")
    cp = state.advance_year(
        cp, year=2020, raw_payload=b"raw", completed=True, last_checked="2026-05-01T00:00:00Z"
    )
    state.write(cp, tmp_path)
    assert tier_b_ingest_state_receipt(tmp_path) == []


# --------------------------------------------------------------------------- #
# Malformed fixtures                                                          #
# --------------------------------------------------------------------------- #


def test_rejects_non_hex_raw_sha256(tmp_path: Path):
    _stage_schema(tmp_path)
    bad = _good_payload()
    bad["years"][0]["raw_sha256"] = "not-a-valid-sha"
    _write_receipt(tmp_path, "rbi-handbook", bad)
    failures = tier_b_ingest_state_receipt(tmp_path)
    assert failures != []
    assert any("raw_sha256" in f.message for f in failures)


def test_rejects_year_out_of_range(tmp_path: Path):
    _stage_schema(tmp_path)
    bad = _good_payload()
    bad["years"][0]["year"] = 1700  # below the schema minimum of 1850
    _write_receipt(tmp_path, "rbi-handbook", bad)
    failures = tier_b_ingest_state_receipt(tmp_path)
    assert failures != []


def test_rejects_non_bool_completed(tmp_path: Path):
    _stage_schema(tmp_path)
    bad = _good_payload()
    bad["years"][0]["completed"] = "yes"
    _write_receipt(tmp_path, "rbi-handbook", bad)
    failures = tier_b_ingest_state_receipt(tmp_path)
    assert failures != []
    assert any("completed" in f.message for f in failures)


def test_rejects_last_checked_without_z(tmp_path: Path):
    _stage_schema(tmp_path)
    bad = _good_payload()
    bad["years"][0]["last_checked"] = "2026-01-01T00:00:00+00:00"
    _write_receipt(tmp_path, "rbi-handbook", bad)
    failures = tier_b_ingest_state_receipt(tmp_path)
    assert failures != []
    assert any("last_checked" in f.message for f in failures)


def test_rejects_adapter_slug_mismatching_filename(tmp_path: Path):
    _stage_schema(tmp_path)
    payload = _good_payload(slug="some-other-slug")
    _write_receipt(tmp_path, "rbi-handbook", payload)  # file stem != adapter_slug
    failures = tier_b_ingest_state_receipt(tmp_path)
    assert failures != []
    assert any("does not match the filename stem" in f.message for f in failures)


def test_rejects_duplicate_year(tmp_path: Path):
    _stage_schema(tmp_path)
    bad = _good_payload()
    bad["years"].append(
        {
            "year": 2018,  # duplicate of the first entry
            "raw_sha256": "c" * 64,
            "completed": True,
            "last_checked": "2026-03-01T00:00:00Z",
        }
    )
    _write_receipt(tmp_path, "rbi-handbook", bad)
    failures = tier_b_ingest_state_receipt(tmp_path)
    assert failures != []
    assert any("duplicate year 2018" in f.message for f in failures)


def test_rejects_missing_required_field(tmp_path: Path):
    _stage_schema(tmp_path)
    bad = _good_payload()
    del bad["years"][0]["completed"]
    _write_receipt(tmp_path, "rbi-handbook", bad)
    failures = tier_b_ingest_state_receipt(tmp_path)
    assert failures != []


def test_reports_when_schema_missing_but_receipt_present(tmp_path: Path):
    # receipt exists, schema NOT staged -> loud, not silent
    _write_receipt(tmp_path, "rbi-handbook", _good_payload())
    failures = tier_b_ingest_state_receipt(tmp_path)
    assert failures != []
    assert any("schema is missing" in f.message for f in failures)


# --------------------------------------------------------------------------- #
# Registration                                                                #
# --------------------------------------------------------------------------- #


def test_check_is_chained_live_into_run():
    from yen_gov import validate as v

    src = Path(v.__file__).read_text(encoding="utf-8")
    assert "def tier_b_ingest_state_receipt(" in src
    assert "+ tier_b_ingest_state_receipt(root)" in src
