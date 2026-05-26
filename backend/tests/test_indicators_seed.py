"""Tier-A tests for ``yen_gov.canonical.indicators_seed``.

Per CLAUDE.md §15: operates on ``tmp_path``, never walks real corpus.
Asserts the D29 parent/child contract + D30 id-pattern enforcement.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical.indicators_seed import compile_to_parquet


_PARENT_BASE = {
    "indicator_id": "state-installed-capacity-mw",
    "label_short": "Installed capacity (MW)",
    "label_long": "State installed electricity generation capacity (MW)",
    "description_short": "Installed generation capacity by state, broken down by fuel type (children).",
    "unit": "MW",
    "cadence": "monthly_cy",
    "family": "energy",
    "pillar": "infrastructure",
    "value_kind": "absolute",
    "direction": "neutral",
    "attribution_geography": "where_produced",
    "comparability": "comparable_across_states_and_time",
    "parent_indicator_id": None,
    "entity_kinds": ["state"],
    "default_entity_kind": "state",
}


_CHILD_BASE = {
    "indicator_id": "state-installed-capacity-coal-mw",
    "label_short": "Coal capacity (MW)",
    "label_long": "State installed coal-fired electricity generation capacity (MW)",
    "description_short": "Coal-fired installed capacity by state.",
    "unit": "MW",
    "cadence": "monthly_cy",
    "family": "energy",
    "pillar": "infrastructure",
    "value_kind": "absolute",
    "direction": "neutral",
    "attribution_geography": "where_produced",
    "comparability": "comparable_across_states_and_time",
    "parent_indicator_id": "state-installed-capacity-mw",
    "dimension_values": {"fuel_type": "coal"},
    "source_id": "src-000000000001",
    "entity_kinds": ["state"],
    "default_entity_kind": "state",
}


def _write_fixture(tmp_path: Path, indicators: list[dict]) -> Path:
    p = tmp_path / "indicators.json"
    p.write_text(json.dumps({"indicators": indicators}), encoding="utf-8")
    return p


def _read(parquet: Path) -> list[tuple]:
    con = duckdb.connect()
    try:
        return con.execute(
            f"SELECT * FROM read_parquet('{parquet.as_posix()}') ORDER BY indicator_id"
        ).fetchall()
    finally:
        con.close()


def test_compile_writes_parent_and_child(tmp_path):
    out = tmp_path / "ind.parquet"
    n = compile_to_parquet(_write_fixture(tmp_path, [_PARENT_BASE, _CHILD_BASE]), out)
    assert n == 2
    rows = _read(out)
    assert len(rows) == 2
    # Sort is by indicator_id PK
    child = rows[0]
    parent = rows[1]
    assert child[0] == "state-installed-capacity-coal-mw"
    assert parent[0] == "state-installed-capacity-mw"


def test_compile_is_deterministic(tmp_path):
    p_in = _write_fixture(tmp_path, [_PARENT_BASE, _CHILD_BASE])
    out1 = tmp_path / "1.parquet"
    out2 = tmp_path / "2.parquet"
    compile_to_parquet(p_in, out1)
    compile_to_parquet(p_in, out2)
    assert out1.read_bytes() == out2.read_bytes()


def test_d29_parent_with_dimension_values_fails(tmp_path):
    """D29: parent (parent_indicator_id IS NULL) must not carry dimension_values."""
    bad_parent = {**_PARENT_BASE, "dimension_values": {"fuel_type": "coal"}}
    with pytest.raises(ValueError, match="parent row must not carry dimension_values"):
        compile_to_parquet(_write_fixture(tmp_path, [bad_parent]), tmp_path / "x.parquet")


def test_d29_child_without_dimension_values_fails(tmp_path):
    """D29: child (parent_indicator_id non-null) MUST carry dimension_values."""
    bad_child = {**_CHILD_BASE, "dimension_values": None}
    with pytest.raises(
        ValueError, match="child row .* must carry dimension_values"
    ):
        compile_to_parquet(
            _write_fixture(tmp_path, [_PARENT_BASE, bad_child]),
            tmp_path / "x.parquet",
        )


def test_d29_child_without_source_id_fails(tmp_path):
    """D29: child must carry source_id (siblings can have different upstreams)."""
    bad_child = {**_CHILD_BASE, "source_id": None}
    with pytest.raises(ValueError, match="child row must carry source_id"):
        compile_to_parquet(
            _write_fixture(tmp_path, [_PARENT_BASE, bad_child]),
            tmp_path / "x.parquet",
        )


def test_d30_rejects_uppercase_id(tmp_path):
    """D30: id pattern is kebab-case lowercase + digits only."""
    bad = {**_PARENT_BASE, "indicator_id": "State-Installed-Capacity-MW"}
    with pytest.raises(Exception):
        compile_to_parquet(_write_fixture(tmp_path, [bad]), tmp_path / "x.parquet")


def test_d30_rejects_id_over_60_chars(tmp_path):
    """D30: id max length 60."""
    long_id = "a" + "-aaaa" * 13  # 1 + 13*5 = 66 chars
    assert len(long_id) > 60
    bad = {**_PARENT_BASE, "indicator_id": long_id}
    with pytest.raises(Exception):
        compile_to_parquet(_write_fixture(tmp_path, [bad]), tmp_path / "x.parquet")


def test_dimension_values_serialised_to_json_string(tmp_path):
    """Catalogue parquet's dimension_values column is JSON-string for flatness."""
    out = tmp_path / "ind.parquet"
    compile_to_parquet(_write_fixture(tmp_path, [_PARENT_BASE, _CHILD_BASE]), out)
    con = duckdb.connect()
    try:
        rows = con.execute(
            f"SELECT indicator_id, dimension_values_json FROM read_parquet('{out.as_posix()}') ORDER BY indicator_id"
        ).fetchall()
    finally:
        con.close()
    child = next(r for r in rows if r[0] == "state-installed-capacity-coal-mw")
    parent = next(r for r in rows if r[0] == "state-installed-capacity-mw")
    assert child[1] == '{"fuel_type":"coal"}'
    assert parent[1] is None


def test_compile_rejects_unknown_pillar(tmp_path):
    bad = {**_PARENT_BASE, "pillar": "not-a-pillar"}
    with pytest.raises(Exception):
        compile_to_parquet(_write_fixture(tmp_path, [bad]), tmp_path / "x.parquet")


def test_compile_rejects_unknown_comparability(tmp_path):
    bad = {**_PARENT_BASE, "comparability": "totally-comparable"}
    with pytest.raises(Exception):
        compile_to_parquet(_write_fixture(tmp_path, [bad]), tmp_path / "x.parquet")


# -- v2.0 (PR-B1 2026-05-26) entity_kinds + default_entity_kind tests --------


def test_v20_entity_kinds_roundtrip(tmp_path):
    """v2.0: entity_kinds + default_entity_kind survive JSON -> parquet round-trip."""
    row = {**_PARENT_BASE, "entity_kinds": ["country", "state"], "default_entity_kind": "state"}
    out = tmp_path / "ind.parquet"
    compile_to_parquet(_write_fixture(tmp_path, [row]), out)
    con = duckdb.connect()
    try:
        result = con.execute(
            f"SELECT entity_kinds, default_entity_kind FROM read_parquet('{out.as_posix()}')"
        ).fetchone()
    finally:
        con.close()
    assert list(result[0]) == ["country", "state"]
    assert result[1] == "state"


def test_v20_default_entity_kind_not_in_kinds_fails(tmp_path):
    """v2.0: default_entity_kind MUST be a member of entity_kinds."""
    bad = {**_PARENT_BASE, "entity_kinds": ["state"], "default_entity_kind": "country"}
    with pytest.raises(ValueError, match="default_entity_kind"):
        compile_to_parquet(_write_fixture(tmp_path, [bad]), tmp_path / "x.parquet")


def test_v20_entity_kinds_empty_fails(tmp_path):
    """v2.0: entity_kinds MUST be non-empty (Field(min_length=1))."""
    bad = {**_PARENT_BASE, "entity_kinds": [], "default_entity_kind": "state"}
    with pytest.raises(Exception):
        compile_to_parquet(_write_fixture(tmp_path, [bad]), tmp_path / "x.parquet")


def test_v20_entity_kind_party_and_candidate_accepted(tmp_path):
    """v2.0: party + candidate are valid entity_kinds (election-class indicators)."""
    row = {**_PARENT_BASE, "indicator_id": "party-vote-share-pct",
           "entity_kinds": ["party"], "default_entity_kind": "party"}
    n = compile_to_parquet(_write_fixture(tmp_path, [row]), tmp_path / "p.parquet")
    assert n == 1


def test_v21_parquet_schema_has_34_columns(tmp_path):
    """v2.1 (PR-Z3b-tail-actionC): DDL grows to 34 columns (update_period_days added; was 33 at v2.0)."""
    out = tmp_path / "ind.parquet"
    compile_to_parquet(_write_fixture(tmp_path, [_PARENT_BASE]), out)
    con = duckdb.connect()
    try:
        col_count = con.execute(
            f"SELECT count(*) FROM (DESCRIBE SELECT * FROM read_parquet('{out.as_posix()}'))"
        ).fetchone()[0]
    finally:
        con.close()
    assert col_count == 34

