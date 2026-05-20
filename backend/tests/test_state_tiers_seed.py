"""Tier-A tests for ``yen_gov.canonical.state_tiers_seed``.

Per CLAUDE.md §15, this is a Tier-A "code-correctness" test — it
operates on a ``tmp_path`` fixture, never walks the real corpus, and
asserts the seed's projection logic, not the on-disk data quality.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.state_tiers_seed import (
    STATE_TIERS_ROW_SCHEMA_VERSION,
    compile_to_parquet,
)


def _write_fixture(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "state_tiers.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _read(parquet: Path) -> list[tuple]:
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT * FROM read_parquet('{parquet.as_posix()}') ORDER BY tier_id, state_code"
        ).fetchall()
    finally:
        con.close()


def test_compile_denormalises_to_one_row_per_member(tmp_path):
    """A 2-tier, 5-state fixture denormalises to 5 rows."""
    payload = {
        "$schema": "./state-tiers.schema.json",
        "$schema_version": "1.0",
        "tiers": [
            {
                "id": "south",
                "label": "Southern states",
                "definition_kind": "geographic",
                "definition": "Five large peninsular states.",
                "authority": "yen-gov editorial",
                "members": ["S22", "S11", "S10", "S29", "S07"],
            },
            {
                "id": "tier_a",
                "label": "Tier A (large)",
                "definition_kind": "fc_derived",
                "definition": "Finance Commission derived population tier.",
                "authority": "Finance Commission of India",
                "members": ["S22"],
                "notes": "Tamil Nadu only in this fixture.",
            },
        ],
    }
    out = tmp_path / "state_tiers.parquet"
    n = compile_to_parquet(_write_fixture(tmp_path, payload), out)
    assert n == 6
    rows = _read(out)
    # tier 'south' has 5 members; tier 'tier_a' has 1
    south_rows = [r for r in rows if r[0] == "south"]
    assert len(south_rows) == 5
    tier_a = [r for r in rows if r[0] == "tier_a"]
    assert len(tier_a) == 1
    # Tier_a row carries notes verbatim
    assert tier_a[0][-1] == "Tamil Nadu only in this fixture."


def test_compile_rejects_unknown_definition_kind(tmp_path):
    """Schema enum is the contract surface — extras fail fast."""
    payload = {
        "tiers": [
            {
                "id": "x",
                "label": "x",
                "definition_kind": "not_a_real_kind",
                "definition": "d",
                "authority": "a",
                "members": ["S01"],
            }
        ]
    }
    out = tmp_path / "x.parquet"
    with pytest.raises(Exception):
        compile_to_parquet(_write_fixture(tmp_path, payload), out)


def test_compile_is_deterministic(tmp_path):
    """Same input -> byte-identical parquet output."""
    payload = {
        "tiers": [
            {
                "id": "south",
                "label": "Southern states",
                "definition_kind": "geographic",
                "definition": "Five large peninsular states.",
                "authority": "yen-gov editorial",
                "members": ["S22", "S11"],
            }
        ]
    }
    p_in = _write_fixture(tmp_path, payload)
    out1 = tmp_path / "1.parquet"
    out2 = tmp_path / "2.parquet"
    compile_to_parquet(p_in, out1)
    compile_to_parquet(p_in, out2)
    assert out1.read_bytes() == out2.read_bytes()


def test_schema_version_constant():
    """The constant is the seed's contract version; pin it."""
    assert STATE_TIERS_ROW_SCHEMA_VERSION == "1.0"
