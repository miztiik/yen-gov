"""Tier-B tests for ``tier_b_no_hand_typed_source_id`` (PR-Z3b-tail-actionB dark).

Per TODO/20260526-grain-over-entity-and-storage-decoupling-plan.md §0quat
guardrail #6, ``source_id`` MUST be looked up via the forthcoming
``source_registry.resolve(nickname)`` seam (PR-A6); raw ``src-<hex>``
literals or top-level ``SOURCE_IDS = {...}`` assignments inside
``backend/yen_gov/sources/**/*.py`` are forbidden. The check ships dark
in PR-Z3b-tail-actionB (function present, NOT chained into ``run()``)
and enforces post-PR-A6.

Per CLAUDE.md anti-pattern (pytest never walks the real corpus) these
tests use ``tmp_path`` fixtures only.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.validate import tier_b_no_hand_typed_source_id


def _adapter(root: Path, rel: str, body: str) -> None:
    p = root / "backend" / "yen_gov" / "sources" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def test_no_op_when_sources_dir_missing(tmp_path):
    assert tier_b_no_hand_typed_source_id(tmp_path) == []


def test_passes_on_clean_adapter(tmp_path):
    _adapter(tmp_path, "rbi_xlsx/ingest.py",
             'from .resolver import resolve\nSID = resolve("rbi-handbook-2024-25")\n')
    assert tier_b_no_hand_typed_source_id(tmp_path) == []


def test_rejects_top_level_source_ids_hash(tmp_path):
    _adapter(tmp_path, "iced_macro/ingest.py",
             'SOURCE_IDS = {"rbi": "src-aabbccddeeff"}\n')
    failures = tier_b_no_hand_typed_source_id(tmp_path)
    # Both the SOURCE_IDS assignment AND the hex literal fire.
    assert any("SOURCE_IDS" in f.message for f in failures)
    assert any("src-aabbccddeeff" in f.message for f in failures)
    assert all("guardrail #6" in f.message for f in failures)


def test_rejects_hand_typed_hex_literal(tmp_path):
    _adapter(tmp_path, "cea_installed_capacity/parsers.py",
             'def f():\n    sid = "src-0123456789ab"\n    return sid\n')
    failures = tier_b_no_hand_typed_source_id(tmp_path)
    assert len(failures) == 1
    assert "src-0123456789ab" in failures[0].message
    assert ":2:" in failures[0].message  # line number reported


def test_only_indented_source_ids_does_not_fire(tmp_path):
    # SOURCE_IDS inside a function (indented) is not the top-level module
    # hash-table the rule targets. Hand-typed hex inside still fires
    # (separate offence), so emit a body with no hex to isolate the rule.
    _adapter(tmp_path, "iced_socio/ingest.py",
             'def make():\n    SOURCE_IDS = {}\n    return SOURCE_IDS\n')
    assert tier_b_no_hand_typed_source_id(tmp_path) == []


def test_walks_all_adapters_under_sources(tmp_path):
    _adapter(tmp_path, "a/clean.py", '"ok"\n')
    _adapter(tmp_path, "b/c/bad.py", 'X = "src-deadbeefcafe"\n')
    failures = tier_b_no_hand_typed_source_id(tmp_path)
    assert len(failures) == 1
    assert "src-deadbeefcafe" in failures[0].message


def test_check_is_dark_not_chained_into_run():
    """PR-Z3b-tail-actionB ships the check DARK -- NOT in run(). Enforced post-A6."""
    from yen_gov import validate as v

    src = Path(v.__file__).read_text(encoding="utf-8")
    assert "tier_b_no_hand_typed_source_id" in src  # function present
    assert "+ tier_b_no_hand_typed_source_id" not in src  # not chained
