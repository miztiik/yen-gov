"""Tier-A tests for ``tools/lgd/backfill_entities_districts.py``.

Per CLAUDE.md §15: tmp_path fixtures only; no real on-disk corpus
reads. Per CLAUDE.md §4: tests CAN import from tools (one-way; tools
still MUST NOT import backend).

The tool module is loaded via a path-prepend rather than packaged
because ``tools/`` is intentionally not a Python package — keeping it
script-shaped keeps the seam between operator tooling and backend
runtime sharp (CLAUDE.md §4 "tools MUST NOT import backend runtime
modules"; nothing prevents the inverse, but we avoid it by convention
so adapters never pick up tool-shaped state).
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / "tools" / "lgd" / "backfill_entities_districts.py"


def _load_tool_module():
    """Load the tool module by path (tools/ is not a package)."""
    spec = importlib.util.spec_from_file_location(
        "backfill_entities_districts", TOOL_PATH
    )
    assert spec and spec.loader, f"could not load {TOOL_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules["backfill_entities_districts"] = module
    spec.loader.exec_module(module)
    return module


backfill = _load_tool_module()


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _write_entities(tmp_path: Path, entities: list[dict[str, Any]]) -> Path:
    payload = {
        "$schema": "../schemas/entity.schema.json",
        "$schema_version": "1.2",
        "entities": entities,
    }
    p = tmp_path / "entities.json"
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p


def _write_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    fieldnames = [
        "S.No.",
        "State Code",
        "State Name (In English)",
        "District Code",
        "District Name(In English)",
        "Census 2001 Code",
        "Census 2011 Code",
    ]
    p = tmp_path / "districts.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def _state_tn() -> dict[str, Any]:
    return {
        "entity_id": "IN-S22",
        "entity_type": "state",
        "entity_level": "state",
        "entity_code": "S22",
        "display_name": "Tamil Nadu",
        "display_name_local": None,
        "parent_entity_id": "IN",
        "entity_valid_from": 1969,
        "entity_valid_to": None,
        "iso_3166_2": "IN-TN",
        "lgd_code": "33",
        "legacy_id": None,
        "notes": None,
    }


def _state_jk_composite() -> dict[str, Any]:
    """Historic composite J&K state (1947-2019) — entity_valid_to set."""
    return {
        "entity_id": "IN-S09",
        "entity_type": "state",
        "entity_level": "state",
        "entity_code": "S09",
        "display_name": "Jammu and Kashmir (state)",
        "display_name_local": None,
        "parent_entity_id": "IN",
        "entity_valid_from": 1947,
        "entity_valid_to": 2019,
        "iso_3166_2": None,
        "lgd_code": "01",
        "legacy_id": None,
        "notes": None,
    }


def _ut_jk_post2019() -> dict[str, Any]:
    """Successor J&K UT (2019-present)."""
    return {
        "entity_id": "IN-U08",
        "entity_type": "ut",
        "entity_level": "state",
        "entity_code": "U08",
        "display_name": "Jammu and Kashmir (UT)",
        "display_name_local": None,
        "parent_entity_id": "IN",
        "entity_valid_from": 2019,
        "entity_valid_to": None,
        "iso_3166_2": None,
        "lgd_code": "01",
        "legacy_id": None,
        "notes": None,
    }


def _existing_district_chennai() -> dict[str, Any]:
    return {
        "entity_id": "IN-S22-D503",
        "entity_type": "district",
        "entity_level": "district",
        "entity_code": "503",
        "display_name": "Chennai",
        "display_name_local": None,
        "parent_entity_id": "IN-S22",
        "entity_valid_from": 1969,
        "entity_valid_to": None,
        "iso_3166_2": None,
        "lgd_code": "503",
        "legacy_id": "CHN",
        "notes": "Headquarters: Chennai.",
    }


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


def test_compute_backfill_skips_already_present_lgd_codes(tmp_path):
    """LGD codes already on a district row must be silently skipped."""
    entities_doc = {
        "entities": [_state_tn(), _existing_district_chennai()],
    }
    csv_rows = [
        # Chennai (503) — already present → SKIP
        {
            "S.No.": "1",
            "State Code": "33",
            "State Name (In English)": "Tamil Nadu",
            "District Code": "503",
            "District Name(In English)": "Chennai",
            "Census 2001 Code": "1",
            "Census 2011 Code": "1",
        },
        # Ariyalur (610) — new → ADD
        {
            "S.No.": "2",
            "State Code": "33",
            "State Name (In English)": "Tamil Nadu",
            "District Code": "610",
            "District Name(In English)": "Ariyalur",
            "Census 2001 Code": "0",
            "Census 2011 Code": "631",
        },
    ]
    new_rows = backfill.compute_backfill(entities_doc, csv_rows)
    assert len(new_rows) == 1
    row = new_rows[0]
    assert row["entity_id"] == "IN-S22-D610"
    assert row["entity_type"] == "district"
    assert row["entity_level"] == "district"
    assert row["entity_code"] == "610"
    assert row["display_name"] == "Ariyalur"
    assert row["parent_entity_id"] == "IN-S22"
    assert row["entity_valid_from"] == 1947
    assert row["entity_valid_to"] is None
    assert row["lgd_code"] == "610"
    assert row["legacy_id"] is None
    assert row["notes"] == "LGD district. Census 2011 code: 631."


def test_compute_backfill_census_2011_zero_uses_short_notes(tmp_path):
    """Post-2011 carve-outs (Census 2011 Code = 0) get the short notes form."""
    entities_doc = {"entities": [_state_tn()]}
    csv_rows = [
        # Mayiladuthurai (628) — carved 2020, no Census 2011 ancestor
        {
            "S.No.": "1",
            "State Code": "33",
            "State Name (In English)": "Tamil Nadu",
            "District Code": "628",
            "District Name(In English)": "Mayiladuthurai",
            "Census 2001 Code": "0",
            "Census 2011 Code": "0",
        },
    ]
    new_rows = backfill.compute_backfill(entities_doc, csv_rows)
    assert len(new_rows) == 1
    assert new_rows[0]["notes"] == "LGD district."


def test_compute_backfill_routes_jk_districts_to_post2019_ut(tmp_path):
    """state_lgd=1 must map to U08 (current UT), NOT S09 (historic, valid_to=2019)."""
    entities_doc = {"entities": [_state_jk_composite(), _ut_jk_post2019()]}
    csv_rows = [
        {
            "S.No.": "1",
            "State Code": "1",  # unpadded; entities.json has "01"
            "State Name (In English)": "Jammu and Kashmir",
            "District Code": "12",
            "District Name(In English)": "Jammu",
            "Census 2001 Code": "8",
            "Census 2011 Code": "8",
        },
    ]
    new_rows = backfill.compute_backfill(entities_doc, csv_rows)
    assert len(new_rows) == 1
    assert new_rows[0]["parent_entity_id"] == "IN-U08"
    assert new_rows[0]["entity_id"] == "IN-U08-D12"


def test_compute_backfill_unknown_state_raises(tmp_path):
    """A CSV row pointing at an unknown state must loud-fail."""
    entities_doc = {"entities": [_state_tn()]}
    csv_rows = [
        {
            "S.No.": "1",
            "State Code": "99",  # not in entities.json
            "State Name (In English)": "Atlantis",
            "District Code": "999",
            "District Name(In English)": "Lost City",
            "Census 2001 Code": "0",
            "Census 2011 Code": "0",
        },
    ]
    with pytest.raises(KeyError, match="state_code 99"):
        backfill.compute_backfill(entities_doc, csv_rows)


def test_compute_backfill_sort_order_is_parent_then_lgd_int(tmp_path):
    """New rows sorted by (parent_entity_id, int(lgd_code)) — NOT lex sort."""
    entities_doc = {"entities": [_state_tn(), _state_jk_composite(), _ut_jk_post2019()]}
    csv_rows = [
        # Deliberately reverse order; numeric-text trap: "100" lex-sorts before "9"
        {
            "S.No.": "1", "State Code": "33", "State Name (In English)": "Tamil Nadu",
            "District Code": "610", "District Name(In English)": "Ariyalur",
            "Census 2001 Code": "0", "Census 2011 Code": "0",
        },
        {
            "S.No.": "2", "State Code": "1", "State Name (In English)": "Jammu and Kashmir",
            "District Code": "12", "District Name(In English)": "Jammu",
            "Census 2001 Code": "0", "Census 2011 Code": "0",
        },
        {
            "S.No.": "3", "State Code": "33", "State Name (In English)": "Tamil Nadu",
            "District Code": "100", "District Name(In English)": "FakeEarlyLgd",
            "Census 2001 Code": "0", "Census 2011 Code": "0",
        },
        {
            "S.No.": "4", "State Code": "33", "State Name (In English)": "Tamil Nadu",
            "District Code": "9", "District Name(In English)": "FakeSingleDigit",
            "Census 2001 Code": "0", "Census 2011 Code": "0",
        },
    ]
    new_rows = backfill.compute_backfill(entities_doc, csv_rows)
    ids = [r["entity_id"] for r in new_rows]
    # Group by parent then ascending int(lgd_code) within group
    # IN-S22 group: 9 < 100 < 610   ; IN-U08 group: 12
    # parent sort: IN-S22 < IN-U08 (lex)
    assert ids == ["IN-S22-D9", "IN-S22-D100", "IN-S22-D610", "IN-U08-D12"]


def test_apply_backfill_writes_entities_json_and_is_idempotent(tmp_path):
    """First apply adds rows + rewrites file; second apply is a no-op."""
    entities_path = _write_entities(tmp_path, [_state_tn()])
    csv_path = _write_csv(tmp_path, [
        {
            "S.No.": "1", "State Code": "33", "State Name (In English)": "Tamil Nadu",
            "District Code": "610", "District Name(In English)": "Ariyalur",
            "Census 2001 Code": "0", "Census 2011 Code": "631",
        },
    ])

    # First apply: 1 new row, total = 2
    added, total = backfill.apply_backfill(entities_path, csv_path)
    assert added == 1
    assert total == 2
    after_first = entities_path.read_bytes()
    on_disk = json.loads(entities_path.read_text(encoding="utf-8"))
    assert len(on_disk["entities"]) == 2
    new_district = next(e for e in on_disk["entities"] if e["entity_type"] == "district")
    assert new_district["entity_id"] == "IN-S22-D610"

    # Second apply: no new rows, file untouched
    added2, total2 = backfill.apply_backfill(entities_path, csv_path)
    assert added2 == 0
    assert total2 == 2
    assert entities_path.read_bytes() == after_first


def test_apply_backfill_is_deterministic_across_runs(tmp_path):
    """Two cold runs against identical input produce byte-identical files."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    entities_a = _write_entities(tmp_path / "a", [_state_tn()])
    entities_b = _write_entities(tmp_path / "b", [_state_tn()])
    csv_path_a = _write_csv(tmp_path / "a", [
        {
            "S.No.": "1", "State Code": "33", "State Name (In English)": "Tamil Nadu",
            "District Code": "610", "District Name(In English)": "Ariyalur",
            "Census 2001 Code": "0", "Census 2011 Code": "631",
        },
        {
            "S.No.": "2", "State Code": "33", "State Name (In English)": "Tamil Nadu",
            "District Code": "628", "District Name(In English)": "Mayiladuthurai",
            "Census 2001 Code": "0", "Census 2011 Code": "0",
        },
    ])
    csv_path_b = _write_csv(tmp_path / "b", [
        # Same content, different upstream order — should still sort to same emit
        {
            "S.No.": "2", "State Code": "33", "State Name (In English)": "Tamil Nadu",
            "District Code": "628", "District Name(In English)": "Mayiladuthurai",
            "Census 2001 Code": "0", "Census 2011 Code": "0",
        },
        {
            "S.No.": "1", "State Code": "33", "State Name (In English)": "Tamil Nadu",
            "District Code": "610", "District Name(In English)": "Ariyalur",
            "Census 2001 Code": "0", "Census 2011 Code": "631",
        },
    ])
    backfill.apply_backfill(entities_a, csv_path_a)
    backfill.apply_backfill(entities_b, csv_path_b)
    assert entities_a.read_bytes() == entities_b.read_bytes()


def test_build_state_lgd_to_eci_map_filters_historic_rows():
    """Currently-valid rows only; composite J&K (S09) excluded."""
    entities = [_state_tn(), _state_jk_composite(), _ut_jk_post2019()]
    m = backfill.build_state_lgd_to_eci_map(entities)
    assert m == {33: "S22", 1: "U08"}


def test_build_state_lgd_to_eci_map_raises_on_duplicate_active_codes():
    """Two CURRENTLY VALID entities cannot share one LGD code."""
    a = _state_tn()
    b = dict(_state_tn())
    b["entity_id"] = "IN-S99"
    b["entity_code"] = "S99"
    # Same lgd_code "33", both valid_to None → conflict
    with pytest.raises(ValueError, match="duplicate state_lgd 33"):
        backfill.build_state_lgd_to_eci_map([a, b])
