"""Tier-A contract tests for the ac_crosswalk schema (Row A1, ADR-0049).

Per CLAUDE.md section 15: tmp_path only, no mocks, no corpus walk. Pins
the v1.0 ac-crosswalk contract + the constituency 4.2 additive bump:

1. The schema loads, is a valid Draft 2020-12 schema, and its changelog
   tail matches x-version.
2. A documented example row validates.
3. ``additionalProperties: false`` rejects unknown fields; required
   fields are enforced; ``lgd_ac_id`` accepts integer-or-null; the
   ``match_method`` enum rejects unknown values.

The constituency.schema.json lgd_ac_id bump is deferred to the SoT
backfill PR (it must restamp on-disk files in the same change), so it is
not asserted here.

See also:
    - datasets/schemas/ac-crosswalk.schema.json
    - docs/architecture/decisions/0049-canonical-ac-join-key.md
    - TODO/20260530-eci-to-lgd-acid-migration-plan.md Row A1
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from yen_gov.core.schema_registry import schema_version

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "datasets" / "schemas"
CROSSWALK_SCHEMA = SCHEMA_DIR / "ac-crosswalk.schema.json"


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _example_row() -> dict:
    return {
        "state_code": "S22",
        "eci_no": 167,
        "lgd_ac_id": 28167,
        "ac_id": "IN-S22-AC-2008-167",
        "ac_name": "Mylapore",
        "delim_year": 2008,
        "match_method": "lgd_direct",
        "source_id": "src-example",
    }


def test_crosswalk_schema_loads_and_changelog_matches_current_version() -> None:
    schema = _load(CROSSWALK_SCHEMA)
    assert schema["x-version"] == schema_version("ac-crosswalk.schema.json")
    assert schema["x-changelog"][-1]["version"] == schema["x-version"]
    Draft202012Validator.check_schema(schema)


def test_crosswalk_schema_accepts_documented_example() -> None:
    v = Draft202012Validator(_load(CROSSWALK_SCHEMA))
    assert list(v.iter_errors(_example_row())) == []


def test_crosswalk_schema_accepts_unmapped_null_row() -> None:
    v = Draft202012Validator(_load(CROSSWALK_SCHEMA))
    row = _example_row()
    row["lgd_ac_id"] = None
    row["match_method"] = "unmapped"
    assert list(v.iter_errors(row)) == []


def test_crosswalk_schema_rejects_unknown_field() -> None:
    v = Draft202012Validator(_load(CROSSWALK_SCHEMA))
    row = _example_row()
    row["surprise"] = "nope"
    assert list(v.iter_errors(row)) != []


def test_crosswalk_schema_rejects_missing_required() -> None:
    v = Draft202012Validator(_load(CROSSWALK_SCHEMA))
    row = _example_row()
    del row["lgd_ac_id"]
    assert list(v.iter_errors(row)) != []


def test_crosswalk_schema_rejects_unknown_match_method() -> None:
    v = Draft202012Validator(_load(CROSSWALK_SCHEMA))
    row = _example_row()
    row["match_method"] = "guessed"
    assert list(v.iter_errors(row)) != []


def test_crosswalk_schema_rejects_string_lgd_ac_id() -> None:
    v = Draft202012Validator(_load(CROSSWALK_SCHEMA))
    row = _example_row()
    row["lgd_ac_id"] = "28167"
    assert list(v.iter_errors(row)) != []
