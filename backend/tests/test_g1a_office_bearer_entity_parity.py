"""Parity oracle for G.1.a — every CM office in
``governments/dim_offices.parquet`` MUST have a matching
``office_bearer`` row in ``taxonomy/entities.parquet``.

Why
----
G.1.a (2026-05-22, Phase 2 preflight, Plan §0e.6 "G.1") lifts the 31
state CM seats into the global entities taxonomy as a new
``entity_type='office_bearer'`` slice. The fact table
``governments_office_holdings.parquet`` (359 CM term rows) already
keys on ``office_id`` which matches ``dim_offices.office_id``; the
new contract is that those office_id values are themselves
``entity_id`` values registered in the entities dim.

Once G.1.b (Phase 2 PR2) makes the holdings reader resolve
``office_id → entity_id`` against entities.parquet directly,
``dim_offices.parquet`` becomes retirement-eligible (G.1.c).
This parity test is the bisect-safe guard: it fires the moment
anything in the entities lift drifts out of step with the holdings
fact, and stays in the suite after retirement to prevent any future
seed rewrite from silently regressing the mapping.

Holy Law #7: uses the REAL on-disk Parquet — no mocks. Skipped
cleanly when either parquet is absent (fresh checkout / partial
backend-only branch).
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DIM_OFFICES = REPO_ROOT / "datasets" / "governments" / "dim_offices.parquet"
ENTITIES = REPO_ROOT / "datasets" / "taxonomy" / "entities.parquet"


@pytest.mark.skipif(
    not DIM_OFFICES.is_file(),
    reason="datasets/governments/dim_offices.parquet not on disk",
)
@pytest.mark.skipif(
    not ENTITIES.is_file(),
    reason="datasets/taxonomy/entities.parquet not on disk",
)
def test_every_dim_office_has_a_matching_office_bearer_entity() -> None:
    """For every ``office_id`` in ``dim_offices``, there MUST be a row
    in ``entities`` with ``entity_id == office_id`` AND
    ``entity_type == 'office_bearer'``."""
    con = duckdb.connect(":memory:")
    try:
        orphans = con.execute(
            f"""
            SELECT o.office_id
            FROM read_parquet('{DIM_OFFICES.as_posix()}') o
            LEFT JOIN read_parquet('{ENTITIES.as_posix()}') e
              ON e.entity_id = o.office_id
             AND e.entity_type = 'office_bearer'
            WHERE e.entity_id IS NULL
            ORDER BY o.office_id
            """
        ).fetchall()
    finally:
        con.close()
    orphan_ids = [r[0] for r in orphans]
    assert orphan_ids == [], (
        f"{len(orphan_ids)} office_id values in dim_offices.parquet have no "
        f"matching office_bearer row in entities.parquet (G.1.a parity "
        f"violation): {orphan_ids[:5]}{'...' if len(orphan_ids) > 5 else ''}"
    )


@pytest.mark.skipif(
    not DIM_OFFICES.is_file(),
    reason="datasets/governments/dim_offices.parquet not on disk",
)
@pytest.mark.skipif(
    not ENTITIES.is_file(),
    reason="datasets/taxonomy/entities.parquet not on disk",
)
def test_no_unused_office_bearer_entities() -> None:
    """Every ``office_bearer`` row in ``entities`` MUST also be present
    in ``dim_offices`` (until G.1.c retires the dim, after which this
    test becomes "every office_bearer entity_id is referenced by at
    least one holdings row" — see G.1.c handover doc)."""
    con = duckdb.connect(":memory:")
    try:
        extras = con.execute(
            f"""
            SELECT e.entity_id
            FROM read_parquet('{ENTITIES.as_posix()}') e
            LEFT JOIN read_parquet('{DIM_OFFICES.as_posix()}') o
              ON o.office_id = e.entity_id
            WHERE e.entity_type = 'office_bearer'
              AND o.office_id IS NULL
            ORDER BY e.entity_id
            """
        ).fetchall()
    finally:
        con.close()
    extra_ids = [r[0] for r in extras]
    assert extra_ids == [], (
        f"{len(extra_ids)} office_bearer entity_id values in entities.parquet "
        f"have no matching row in dim_offices.parquet "
        f"(G.1.a parity violation): {extra_ids}"
    )


@pytest.mark.skipif(
    not ENTITIES.is_file(),
    reason="datasets/taxonomy/entities.parquet not on disk",
)
def test_office_bearer_rows_have_required_shape() -> None:
    """All ``office_bearer`` rows in entities.parquet MUST have
    ``entity_level='fiscal_actor'`` AND a non-null parent_entity_id
    pointing at a state/UT.

    This is the shape that downstream frontend resolvers rely on
    (breadcrumb: state → CM office; holdings list filtered by parent
    state). A future seed change that violated either constraint would
    silently mis-render the office in the citizen UI.
    """
    con = duckdb.connect(":memory:")
    try:
        bad_level = con.execute(
            f"""
            SELECT entity_id, entity_level
            FROM read_parquet('{ENTITIES.as_posix()}')
            WHERE entity_type = 'office_bearer'
              AND entity_level <> 'fiscal_actor'
            """
        ).fetchall()
        missing_parent = con.execute(
            f"""
            SELECT entity_id
            FROM read_parquet('{ENTITIES.as_posix()}')
            WHERE entity_type = 'office_bearer'
              AND parent_entity_id IS NULL
            """
        ).fetchall()
        unresolved_parent = con.execute(
            f"""
            SELECT child.entity_id, child.parent_entity_id
            FROM read_parquet('{ENTITIES.as_posix()}') child
            LEFT JOIN read_parquet('{ENTITIES.as_posix()}') parent
              ON parent.entity_id = child.parent_entity_id
            WHERE child.entity_type = 'office_bearer'
              AND child.parent_entity_id IS NOT NULL
              AND parent.entity_id IS NULL
            """
        ).fetchall()
    finally:
        con.close()
    assert bad_level == [], (
        f"office_bearer rows with wrong entity_level: {bad_level}"
    )
    assert missing_parent == [], (
        f"office_bearer rows missing parent_entity_id: {missing_parent}"
    )
    assert unresolved_parent == [], (
        f"office_bearer rows with parent_entity_id that does not exist in "
        f"entities.parquet: {unresolved_parent}"
    )
