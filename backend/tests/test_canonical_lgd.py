"""Unit tests for ``yen_gov.canonical.lgd``.

Per CLAUDE.md §10 "no real-corpus walk in pytest" - all fixtures here
are inline 3-row dicts that mirror the ``entities.json`` shape exactly
(the same fields the loader reads). ``tmp_path`` writes the fixture to
a temporary ``entities.json`` and the test invokes the loader against
that root, never touching the real ``datasets/taxonomy/entities.json``.

Three behaviours under test:

1. happy path - given an inline 3-row entities fixture, ``resolve_district``
   returns the expected entity_id for a known LGD code;
2. miss path - a code absent from the lookup raises ``ValueError`` with
   an informative message naming the missing code AND the lookup size
   (so failures are actionable on first read);
3. filter path - ``load_district_lookup`` skips non-district entries
   (country, state, UT, block) and entries with ``lgd_code: null``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.lgd import load_district_lookup, resolve_district


def _write_entities(tmp_root: Path, entities: list[dict]) -> Path:
    """Write a 3-row entities.json fixture under tmp_root and return tmp_root."""
    taxonomy_dir = tmp_root / "datasets" / "taxonomy"
    taxonomy_dir.mkdir(parents=True)
    (taxonomy_dir / "entities.json").write_text(
        json.dumps({"$schema_version": "1.2", "entities": entities}),
        encoding="utf-8",
    )
    return tmp_root


def test_resolves_district_known_lgd_code(tmp_path: Path) -> None:
    root = _write_entities(
        tmp_path,
        [
            {
                "entity_id": "IN",
                "entity_type": "country",
                "lgd_code": None,
            },
            {
                "entity_id": "IN-S03",
                "entity_type": "state",
                "lgd_code": "18",
            },
            {
                "entity_id": "IN-S03-D280",
                "entity_type": "district",
                "lgd_code": "280",
            },
        ],
    )
    # Clear lru_cache so each test starts clean - load_district_lookup
    # is module-level memoised and tmp_path varies per test.
    load_district_lookup.cache_clear()
    lookup = load_district_lookup(root)

    assert resolve_district("280", lookup) == "IN-S03-D280"


def test_raises_value_error_on_missing_lgd_code(tmp_path: Path) -> None:
    root = _write_entities(
        tmp_path,
        [
            {
                "entity_id": "IN-S03-D280",
                "entity_type": "district",
                "lgd_code": "280",
            },
        ],
    )
    load_district_lookup.cache_clear()
    lookup = load_district_lookup(root)

    with pytest.raises(ValueError) as exc_info:
        resolve_district("999", lookup)

    msg = str(exc_info.value)
    # Error must name the missing code AND the lookup size - silent
    # misses are the bug class this module prevents.
    assert "'999'" in msg
    assert "lookup size: 1" in msg


def test_load_district_lookup_filters_non_districts_and_missing_lgd(
    tmp_path: Path,
) -> None:
    root = _write_entities(
        tmp_path,
        [
            {
                "entity_id": "IN",
                "entity_type": "country",
                "lgd_code": None,
            },
            {
                "entity_id": "IN-S03",
                "entity_type": "state",
                "lgd_code": "18",
            },
            {
                "entity_id": "IN-S03-D280",
                "entity_type": "district",
                "lgd_code": "280",
            },
            {
                "entity_id": "IN-U05-D640",
                "entity_type": "district",
                "lgd_code": "640",
            },
            {
                "entity_id": "IN-S03-D281",
                "entity_type": "district",
                "lgd_code": None,
            },
        ],
    )
    load_district_lookup.cache_clear()
    lookup = load_district_lookup(root)

    # Only the two districts WITH lgd_code survive: country / state /
    # null-coded district are all filtered.
    assert lookup == {"280": "IN-S03-D280", "640": "IN-U05-D640"}
