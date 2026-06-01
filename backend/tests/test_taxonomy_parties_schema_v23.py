"""Tier-A schema fixtures for taxonomy-parties.schema.json v2.3.

Covers PR-SYM-1 (v2.2: `recognition` + `election_symbol`) and PR-SYM-4b (v2.3:
loosen `asset_path` to non-SVG, add `mime_type` enum, add optional
`wikipedia_url` and `brand_colour` per Section 11 of
TODO/20260527-party-symbol-assets-plan.md).

No real-corpus walks. Each test seeds a minimal taxonomy/parties.json in
``tmp_path`` and validates against the on-disk schema via jsonschema.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "datasets"
    / "schemas"
    / "taxonomy-parties.schema.json"
)


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def base_payload() -> dict:
    return {
        "$schema": "../schemas/taxonomy-parties.schema.json",
        "$schema_version": "2.3",
        "sources": [],
        "parties": [
            {
                "party_id": "parties.IN.BJP",
                "short_name": "BJP",
                "full_name": "Bharatiya Janata Party",
                "state_scope": ["IN"],
            }
        ],
    }


def _validate(schema: dict, payload: dict) -> None:
    Draft202012Validator(schema).validate(payload)


def _expect_invalid(schema: dict, payload: dict) -> None:
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(payload)


def test_schema_x_version_is_2_3(schema: dict) -> None:
    assert schema["x-version"] == "2.3"
    tail = schema["x-changelog"][-1]
    assert tail["version"] == "2.3", "tail changelog entry must equal x-version"


def test_existing_row_without_new_fields_still_valid(
    schema: dict, base_payload: dict
) -> None:
    _validate(schema, base_payload)


def test_recognition_accepts_all_enum_values(
    schema: dict, base_payload: dict
) -> None:
    for value in ("national", "state", "registered_unrecognised", "unknown", None):
        payload = deepcopy(base_payload)
        payload["parties"][0]["recognition"] = value
        _validate(schema, payload)


def test_recognition_rejects_unknown_value(
    schema: dict, base_payload: dict
) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["recognition"] = "not_a_real_status"
    _expect_invalid(schema, payload)


def test_election_symbol_verified_row_accepted(
    schema: dict, base_payload: dict
) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["recognition"] = "national"
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Lotus",
        "asset_path": "party-symbols/lotus.svg",
        "asset_sha256": "0" * 64,
        "source_id": "src.commons.symbols-of-political-parties-in-india.2026-06-01",
        "asset_source_kind": "commons",
        "license_label": "CC-BY-SA-3.0",
        "render_mode": "source_coloured",
        "symbol_status": "verified",
        "notes": None,
    }
    _validate(schema, payload)


def test_election_symbol_placeholder_row_accepted(
    schema: dict, base_payload: dict
) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["recognition"] = "state"
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Placeholder",
        "asset_path": "party-symbols/placeholder.svg",
        "asset_sha256": None,
        "source_id": None,
        "asset_source_kind": "editorial_placeholder",
        "license_label": "project-placeholder",
        "render_mode": "monochrome",
        "symbol_status": "placeholder",
        "notes": None,
    }
    _validate(schema, payload)


def test_election_symbol_rejects_invalid_asset_path(
    schema: dict, base_payload: dict
) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Lotus",
        "asset_path": "lotus.svg",  # missing party-symbols/ prefix
        "asset_sha256": "0" * 64,
        "source_id": "src.commons.x.2026-06-01",
        "asset_source_kind": "commons",
        "license_label": "CC-BY-SA-3.0",
        "render_mode": "monochrome",
        "symbol_status": "verified",
        "notes": None,
    }
    _expect_invalid(schema, payload)


def test_election_symbol_rejects_pascal_case_slug(
    schema: dict, base_payload: dict
) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Lotus",
        "asset_path": "party-symbols/Lotus.svg",  # PascalCase forbidden
        "asset_sha256": "0" * 64,
        "source_id": "src.commons.x.2026-06-01",
        "asset_source_kind": "commons",
        "license_label": "CC-BY-SA-3.0",
        "render_mode": "monochrome",
        "symbol_status": "verified",
        "notes": None,
    }
    _expect_invalid(schema, payload)


def test_election_symbol_rejects_bad_sha256_format(
    schema: dict, base_payload: dict
) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Lotus",
        "asset_path": "party-symbols/lotus.svg",
        "asset_sha256": "not-a-real-hash",
        "source_id": "src.commons.x.2026-06-01",
        "asset_source_kind": "commons",
        "license_label": "CC-BY-SA-3.0",
        "render_mode": "monochrome",
        "symbol_status": "verified",
        "notes": None,
    }
    _expect_invalid(schema, payload)


def test_election_symbol_rejects_unknown_render_mode(
    schema: dict, base_payload: dict
) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Lotus",
        "asset_path": "party-symbols/lotus.svg",
        "asset_sha256": "0" * 64,
        "source_id": "src.commons.x.2026-06-01",
        "asset_source_kind": "commons",
        "license_label": "CC-BY-SA-3.0",
        "render_mode": "party_coloured",  # not in enum
        "symbol_status": "verified",
        "notes": None,
    }
    _expect_invalid(schema, payload)


def test_election_symbol_rejects_unknown_symbol_status(
    schema: dict, base_payload: dict
) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Lotus",
        "asset_path": "party-symbols/lotus.svg",
        "asset_sha256": "0" * 64,
        "source_id": "src.commons.x.2026-06-01",
        "asset_source_kind": "commons",
        "license_label": "CC-BY-SA-3.0",
        "render_mode": "monochrome",
        "symbol_status": "pending_review",  # not in enum
        "notes": None,
    }
    _expect_invalid(schema, payload)


def test_election_symbol_requires_core_fields(
    schema: dict, base_payload: dict
) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Lotus",
        # missing asset_path, render_mode, symbol_status
    }
    _expect_invalid(schema, payload)


def test_election_symbol_rejects_unknown_field(
    schema: dict, base_payload: dict
) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Lotus",
        "asset_path": "party-symbols/lotus.svg",
        "asset_sha256": "0" * 64,
        "source_id": "src.commons.x.2026-06-01",
        "asset_source_kind": "commons",
        "license_label": "CC-BY-SA-3.0",
        "render_mode": "monochrome",
        "symbol_status": "verified",
        "notes": None,
        "background_color": "#ea580c",  # forbidden; colours live in colour resolver
    }
    _expect_invalid(schema, payload)


# =====================================================================
# v2.3 additions (PR-SYM-4b): mime_type, loosened asset_path, wikipedia_url, brand_colour
# =====================================================================


def test_asset_path_accepts_png_jpg_webp(schema: dict, base_payload: dict) -> None:
    for ext, mime in [(".png", "image/png"), (".jpg", "image/jpeg"), (".webp", "image/webp")]:
        payload = deepcopy(base_payload)
        payload["parties"][0]["election_symbol"] = {
            "symbol_name": "Broom",
            "asset_path": f"party-symbols/broom{ext}",
            "asset_sha256": "0" * 64,
            "source_id": "src.x.1",
            "asset_source_kind": "commons",
            "license_label": "CC-BY-SA-4.0",
            "render_mode": "source_coloured",
            "symbol_status": "verified",
            "mime_type": mime,
            "notes": None,
        }
        _validate(schema, payload)


def test_asset_path_rejects_unknown_extension(schema: dict, base_payload: dict) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Lotus",
        "asset_path": "party-symbols/lotus.gif",  # gif not allowed
        "asset_sha256": "0" * 64,
        "source_id": "src.x.1",
        "asset_source_kind": "commons",
        "license_label": "x",
        "render_mode": "source_coloured",
        "symbol_status": "verified",
        "mime_type": "image/svg+xml",
        "notes": None,
    }
    _expect_invalid(schema, payload)


def test_mime_type_enum_accepts_known_values(schema: dict, base_payload: dict) -> None:
    for mime in ("image/svg+xml", "image/png", "image/jpeg", "image/webp", None):
        payload = deepcopy(base_payload)
        payload["parties"][0]["election_symbol"] = {
            "symbol_name": "Lotus",
            "asset_path": "party-symbols/lotus.svg",
            "asset_sha256": None,
            "source_id": None,
            "asset_source_kind": "editorial_placeholder",
            "license_label": "project-placeholder",
            "render_mode": "monochrome",
            "symbol_status": "placeholder",
            "mime_type": mime,
            "notes": None,
        }
        _validate(schema, payload)


def test_mime_type_rejects_unknown_value(schema: dict, base_payload: dict) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["election_symbol"] = {
        "symbol_name": "Lotus",
        "asset_path": "party-symbols/lotus.svg",
        "asset_sha256": "0" * 64,
        "source_id": "src.x.1",
        "asset_source_kind": "commons",
        "license_label": "x",
        "render_mode": "monochrome",
        "symbol_status": "verified",
        "mime_type": "image/gif",
        "notes": None,
    }
    _expect_invalid(schema, payload)


def test_wikipedia_url_optional_absent_is_valid(schema: dict, base_payload: dict) -> None:
    _validate(schema, base_payload)


def test_wikipedia_url_accepts_en_wikipedia(schema: dict, base_payload: dict) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["wikipedia_url"] = "https://en.wikipedia.org/wiki/Bharatiya_Janata_Party"
    _validate(schema, payload)


def test_wikipedia_url_rejects_non_wikipedia(schema: dict, base_payload: dict) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["wikipedia_url"] = "https://example.com/BJP"
    _expect_invalid(schema, payload)


def test_brand_colour_optional_absent_is_valid(schema: dict, base_payload: dict) -> None:
    _validate(schema, base_payload)


def test_brand_colour_full_object_accepted(schema: dict, base_payload: dict) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["brand_colour"] = {
        "hex": "#FF9933",
        "confidence": "high",
        "source_id": "src.wikipedia.list-of-political-parties-in-india.2026-06-01",
        "source_kind": "wiki",
        "notes": None,
    }
    _validate(schema, payload)


def test_brand_colour_confidence_low_accepted(schema: dict, base_payload: dict) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["brand_colour"] = {
        "hex": "#FFB300",
        "confidence": "low",
        "source_id": "src.x.1",
        "source_kind": "wiki",
        "notes": "Faction split; ECI freezing order 2022-10-08 assigned bow-and-arrow to SHS-Shinde; UBT inherited the legacy hex.",
    }
    _validate(schema, payload)


def test_brand_colour_rejects_bad_hex(schema: dict, base_payload: dict) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["brand_colour"] = {
        "hex": "FF9933",  # missing leading #
        "confidence": "high",
        "source_id": "src.x.1",
        "source_kind": "wiki",
        "notes": None,
    }
    _expect_invalid(schema, payload)


def test_brand_colour_rejects_unknown_source_kind(schema: dict, base_payload: dict) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["brand_colour"] = {
        "hex": "#FF9933",
        "confidence": "high",
        "source_id": "src.x.1",
        "source_kind": "eci",  # not in enum (only "wiki" allowed in v2.3)
        "notes": None,
    }
    _expect_invalid(schema, payload)


def test_brand_colour_rejects_unknown_confidence(schema: dict, base_payload: dict) -> None:
    payload = deepcopy(base_payload)
    payload["parties"][0]["brand_colour"] = {
        "hex": "#FF9933",
        "confidence": "uncertain",  # not in enum
        "source_id": "src.x.1",
        "source_kind": "wiki",
        "notes": None,
    }
    _expect_invalid(schema, payload)
